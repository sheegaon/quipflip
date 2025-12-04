"""ThinkLink round service.

Orchestrates round lifecycle: start, submit guess, finalize.
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from backend.models.tl import TLRound, TLGuess, TLAnswer, TLTransaction, TLPrompt
from backend.models.player import Player
from backend.services.tl.matching_service import TLMatchingService
from backend.services.tl.clustering_service import TLClusteringService
from backend.services.tl.scoring_service import TLScoringService
from backend.services.tl.prompt_service import TLPromptService
from backend.services.phrase_validator import get_phrase_validator
from backend.config import get_settings

logger = logging.getLogger(__name__)


async def _get_prompt_text(db: AsyncSession, prompt_id: str) -> str:
    """Helper to get prompt text."""
    from sqlalchemy.orm import load_only
    # Use load_only to avoid loading embedding column (pgvector deserialization issue)
    result = await db.execute(
        select(TLPrompt)
        .options(load_only(TLPrompt.prompt_id, TLPrompt.text))
        .where(TLPrompt.prompt_id == prompt_id)
    )
    prompt = result.scalars().first()
    return prompt.text if prompt else ""


async def _get_prior_guesses(db: AsyncSession, round_id: str) -> List[str]:
    """Get all prior guesses in a round."""
    # Only load guess text to avoid deserializing historical embeddings that may
    # be stored as plain lists (pgvector expects vector input and would crash).
    result = await db.execute(
        select(TLGuess.text).where(TLGuess.round_id == round_id)
    )
    return [row[0] for row in result.all()]


async def _build_snapshot_answers(db: AsyncSession, answer_ids: List[str]) -> List[Dict]:
    """Build answer data for matching from snapshot IDs."""
    if not answer_ids:
        return []

    result = await db.execute(
        select(TLAnswer).where(TLAnswer.answer_id.in_(answer_ids))
    )
    answers = result.scalars().all()

    # DEBUG: Log embedding types from pgvector to diagnose conversion issues
    if answers:
        first_embedding = answers[0].embedding
        logger.info(
            f"🔬 EMBEDDING DEBUG: pgvector returned type={type(first_embedding).__name__}, "
            f"len={len(first_embedding) if hasattr(first_embedding, '__len__') else 'N/A'}, "
            f"sample_values={list(first_embedding)[:5] if hasattr(first_embedding, '__iter__') else 'N/A'}..."
        )

    return [
        {
            "answer_id": str(a.answer_id),
            "text": a.text,
            "embedding": a.embedding,
            "cluster_id": str(a.cluster_id) if a.cluster_id else None,
        }
        for a in answers
    ]


class TLRoundService:
    """Service for ThinkLink round orchestration."""

    def __init__(
        self,
        matching_service: TLMatchingService,
        clustering_service: TLClusteringService,
        scoring_service: TLScoringService,
        prompt_service: TLPromptService,
    ):
        """Initialize round service.

        Args:
            matching_service: For semantic matching
            clustering_service: For clustering operations
            scoring_service: For scoring calculations
            prompt_service: For prompt management
        """
        self.matching = matching_service
        self.clustering = clustering_service
        self.scoring = scoring_service
        self.prompt = prompt_service

        settings = get_settings()
        self.entry_cost = settings.tl_entry_cost
        self.max_strike_count = 3
        self.prompt_relevance_threshold = settings.tl_topic_threshold
        self.self_similarity_threshold = settings.tl_self_similarity_threshold

    async def start_round(self, db: AsyncSession, player_id: str
                          ) -> Tuple[Optional[TLRound], Optional[str], Optional[str]]:
        """Start a new round for a player.

        Steps:
        1. Verify player has >= entry_cost coins
        2. Select random active prompt
        3. Build snapshot (up to 1000 active answers + clusters)
        4. Deduct entry cost transaction
        5. Create TLRound record

        Args:
            db: Database session
            player_id: Player ID

        Returns:
            (round, prompt_text, error_message) - error_message is None on success
        """
        try:
            logger.info(f"🎮 Starting round for player {player_id}...")

            # Get player
            result = await db.execute(
                select(Player).where(Player.player_id == player_id)
            )
            player = result.scalars().first()
            if not player:
                return None, None, "Player not found"

            # Check balance
            tl_wallet = player.tl_player_data.wallet if player.tl_player_data else 0
            if tl_wallet < self.entry_cost:
                return None, None, "insufficient_balance"

            # Select prompt
            prompt = await self.prompt.get_random_active_prompt(db)
            if not prompt:
                return None, None, "no_prompts_available"

            # Get active answers for snapshot
            answers = await self.prompt.get_active_answers_for_prompt(
                db, str(prompt.prompt_id), limit=1000
            )
            logger.info(f"📊 Snapshot: {len(answers)} active answers")

            # Build snapshot data
            snapshot_answer_ids = [str(a.answer_id) for a in answers]
            snapshot_cluster_ids = list(set([str(a.cluster_id) for a in answers if a.cluster_id]))

            # Calculate total snapshot weight (sum of all cluster weights)
            total_weight = await self.scoring._calculate_total_weight(db, snapshot_cluster_ids)

            # Create round
            round = TLRound(
                player_id=player_id,
                prompt_id=str(prompt.prompt_id),
                snapshot_answer_ids=snapshot_answer_ids,
                snapshot_cluster_ids=snapshot_cluster_ids,
                snapshot_total_weight=total_weight,
                matched_clusters=[],
                strikes=0,
                status='active',
            )
            db.add(round)
            await db.flush()

            # Attach prompt to avoid lazy-loading with async sessions
            round.prompt = prompt

            # Deduct entry cost
            if player.tl_player_data:
                player.tl_player_data.wallet -= self.entry_cost
            transaction = TLTransaction(
                player_id=player_id,
                amount=-self.entry_cost,
                transaction_type='round_entry',
                round_id=str(round.round_id),
                description=f'Round entry: {prompt.text[:50]}...',
            )
            db.add(transaction)
            await db.flush()

            logger.info(f"✅ Round started: {round.round_id} ({prompt.text[:50]=}..., {total_weight=:.2f})")
            return round, prompt.text, None

        except Exception as e:
            logger.error(f"❌ Start round failed: {e}")
            return None, None, "round_start_failed"

    async def submit_guess(
        self,
        db: AsyncSession,
        round_id: str,
        player_id: str,
        guess_text: str,
    ) -> Tuple[Dict, Optional[str], Optional[str]]:
        """Submit a guess for an active round.

        Steps:
        1. Validate round exists and is active
        2. Validate phrase format and dictionary compliance
        3. Validate phrase doesn't reuse significant words from prompt
        4. Generate embedding
        5. Check self-similarity to prior guesses
        6. Find matches in snapshot answers
        7. Update matched_clusters if new match
        8. Add strike if no matches
        9. End round if 3 strikes
        10. Log guess
        11. Finalize round if completion conditions are met

        Validation errors (invalid_phrase, too_similar) do NOT consume strikes.

        Args:
            db: Database session
            round_id: Round ID
            player_id: Player ID (for ownership check)
            guess_text: Guess text

        Returns:
            (result_dict, error_message) where result_dict contains:
                - was_match: bool
                - matched_answer_count: int
                - matched_cluster_ids: List[str]
                - new_strikes: int
                - current_coverage: float
                - round_status: str
        """
        try:
            logger.info(f"💭 Submitting guess: '{guess_text}' for round {round_id}")

            # Get round
            result = await db.execute(
                select(TLRound)
                .options(
                    selectinload(TLRound.prompt).load_only(
                        TLPrompt.prompt_id,
                        TLPrompt.text,
                    )
                )
                .where(TLRound.round_id == round_id)
            )
            round = result.scalars().first()
            if not round:
                return {}, "round_not_found", None

            if str(round.player_id) != str(player_id):
                return {}, "unauthorized", None

            if round.status != 'active':
                return {}, f"round_not_active", None

            if round.strikes >= self.max_strike_count:
                return {}, "round_already_ended", None

            prompt_text = round.prompt.text if round.prompt else await _get_prompt_text(db, round.prompt_id)

            # Defensive: ensure inputs are strings before validation
            if not isinstance(guess_text, str):
                logger.warning(f"🔎 guess_text not a string: "
                               f"type={type(guess_text).__name__} {guess_text=} {round_id=} {player_id=}")
                return {}, "invalid_phrase", "Guess must be text"

            if not isinstance(prompt_text, str):
                logger.error(
                    f"⚠️ Prompt text not string; coercing. type={type(prompt_text).__name__} "
                    f"round={round_id} prompt_id={round.prompt_id} value={prompt_text!r}"
                )
                prompt_text = str(prompt_text) if prompt_text is not None else ""

            # Validate phrase format and dictionary compliance
            validator = get_phrase_validator()
            is_valid, error_msg = validator.validate(guess_text)
            if not is_valid:
                logger.info(
                    f"⏭️  Guess rejected (validation): {error_msg} | round={round_id} player={player_id} guess='{guess_text}'"
                )
                return {}, "invalid_phrase", error_msg

            # Validate phrase doesn't reuse significant words from prompt
            is_valid, error_msg = await validator.validate_prompt_phrase(guess_text, prompt_text)
            if not is_valid:
                logger.info(
                    f"⏭️  Guess rejected (prompt conflict): {error_msg} | round={round_id} player={player_id} guess='{guess_text}'"
                )
                return {}, "invalid_phrase", error_msg

            # Generate embedding for guess
            guess_embedding = await self.matching.generate_embedding(guess_text)

            # Check self-similarity
            prior_guesses = await _get_prior_guesses(db, round_id)
            is_too_similar, max_sim = await self.matching.check_self_similarity(guess_text, prior_guesses)
            if is_too_similar:
                logger.info(f"⏭️  Guess rejected: too similar to prior (similarity={max_sim:.3f})")
                similarity_note = (
                    f"Too similar to your previous guess (similarity {max_sim:.2f}, "
                    f"max allowed {self.self_similarity_threshold:.2f})"
                ) if max_sim is not None else "Too similar to a prior guess"
                return {}, "too_similar", similarity_note

            # Find matches in snapshot
            snapshot_answers = await _build_snapshot_answers(db, round.snapshot_answer_ids)
            matches = await self.matching.find_matches(
                guess_text,
                guess_embedding,
                snapshot_answers,
            )

            # Process matches
            was_match = len(matches) > 0
            matched_cluster_ids = list(set([m["cluster_id"] for m in matches if m["cluster_id"]]))
            new_strikes = 0

            if was_match:
                # Update matched clusters
                current_matched = round.matched_clusters or []
                round.matched_clusters = list(set(current_matched + matched_cluster_ids))
                logger.info(f"✅ Matched {len(matched_cluster_ids)} new clusters")
            else:
                # Add strike
                round.strikes += 1
                new_strikes = round.strikes
                logger.info(f"⚠️  No matches - strike {new_strikes}/3")

            # Log guess
            guess = TLGuess(
                round_id=str(round.round_id),
                text=guess_text,
                embedding=guess_embedding,
                was_match=was_match,
                matched_answer_ids=[m["answer_id"] for m in matches],
                matched_cluster_ids=matched_cluster_ids,
                caused_strike=not was_match,
            )
            db.add(guess)
            await db.flush()

            # Calculate current coverage
            current_coverage = await self.scoring.calculate_coverage(
                db,
                round.matched_clusters or [],
                round.snapshot_cluster_ids,
                str(round.prompt_id),
            )

            # Check for round completion conditions and finalize if needed
            should_finalize = False
            
            if round.strikes >= self.max_strike_count:
                # Round ended due to strikes
                round.status = 'completed'  # Change from 'abandoned' to 'completed'
                should_finalize = True
                logger.info(f"🏁 Round ended - 3 strikes reached, finalizing...")
            elif current_coverage >= 0.95:  # 95% coverage threshold for auto-completion
                # Round completed due to high coverage
                round.status = 'completed'
                should_finalize = True
                logger.info(f"🎉 Round completed - high coverage achieved ({current_coverage:.1%}), finalizing...")

            # Finalize round if completion conditions are met
            if should_finalize:
                await self._finalize_round(db, round, current_coverage, player_id)

            return {
                "was_match": was_match,
                "matched_answer_count": len(matches),
                "matched_cluster_ids": matched_cluster_ids,
                "new_strikes": new_strikes,
                "current_coverage": current_coverage,
                "round_status": round.status,
            }, None, None

        except Exception as e:
            logger.exception(f"❌ Submit guess failed: {e}")
            return {}, "submit_failed", None

    async def _finalize_round(self, db: AsyncSession, round: TLRound, coverage: float, player_id: str) -> None:
        """Finalize a completed round with payouts and statistics.
        
        Args:
            db: Database session
            round: The round to finalize
            coverage: Final coverage percentage (0-1)
            player_id: Player ID for transactions
        """
        try:
            # Import the standalone function
            from backend.services.tl.scoring_service import finalize_round
            
            # Calculate payouts
            wallet_award, vault_award, gross_payout = self.scoring.calculate_payout(coverage)
            
            # Get player
            player = await db.get(Player, player_id)
            if not player or not player.tl_player_data:
                logger.error(f"❌ Player or TL data not found for finalization: {player_id}")
                return
                
            # Apply wallet award
            if wallet_award > 0:
                player.tl_player_data.wallet += wallet_award
                wallet_transaction = TLTransaction(
                    player_id=player_id,
                    amount=wallet_award,
                    transaction_type='round_payout_wallet',
                    round_id=str(round.round_id),
                    description=f'Round payout - wallet ({coverage:.1%} coverage)',
                )
                db.add(wallet_transaction)
                
            # Apply vault award
            if vault_award > 0:
                player.tl_player_data.vault += vault_award
                vault_transaction = TLTransaction(
                    player_id=player_id,
                    amount=vault_award,
                    transaction_type='round_payout_vault',
                    round_id=str(round.round_id),
                    description=f'Round payout - vault ({coverage:.1%} coverage)',
                )
                db.add(vault_transaction)
            
            # Finalize the round using the standalone function
            await finalize_round(
                db, round, wallet_award, vault_award, gross_payout, coverage
            )
            
            logger.info(
                f"✅ Round finalized: {round.round_id} | coverage={coverage:.1%} | "
                f"wallet_award={wallet_award} | vault_award={vault_award} | gross={gross_payout}"
            )
            
        except Exception as e:
            logger.error(f"❌ Round finalization failed: {e}")
            raise

    async def abandon_round(self, db: AsyncSession, round_id: str, player_id: str) -> Tuple[Dict, Optional[str]]:
        """Abandon an active round with partial refund.

        Refund: entry_cost - 5 (95 coins)

        Args:
            db: Database session
            round_id: Round ID
            player_id: Player ID (for ownership check)

        Returns:
            (result_dict, error_message)
        """
        try:
            logger.debug(f"🚪 Abandoning round {round_id}...")

            # Get round
            result = await db.execute(
                select(TLRound).where(TLRound.round_id == round_id)
            )
            round = result.scalars().first()
            if not round:
                return {}, "round_not_found"

            # Ownership check can be tripped by UUID vs string mismatches;
            # log both representations to debug any session/identity drift.
            if str(round.player_id) != str(player_id):
                logger.warning(
                    f"🔒 Abandon unauthorized: round belongs to {round.player_id} "
                    f"(type={type(round.player_id).__name__}), request for {player_id} "
                    f"(type={type(player_id).__name__})"
                )
                return {}, "unauthorized"

            if round.status != 'active':
                return {}, "round_not_active"

            # Disallow abandoning once any guess has been submitted
            guess_present = await db.execute(
                select(TLGuess.guess_id).where(TLGuess.round_id == round_id).limit(1)
            )
            if guess_present.first():
                logger.debug(f"⏭️  Abandon blocked: guesses already submitted | {round_id=} {player_id=}")
                return {}, "round_has_guesses"

            # Calculate refund (entry_cost - 5 penalty = 95 coins)
            penalty = 5
            refund_amount = self.entry_cost - penalty

            # Update round
            round.status = 'abandoned'
            round.ended_at = datetime.now(UTC)

            # Refund to player
            player = await db.get(Player, player_id)
            if player and player.tl_player_data:
                player.tl_player_data.wallet += refund_amount

            # Log transaction
            transaction = TLTransaction(
                player_id=player_id,
                amount=refund_amount,
                transaction_type='round_abandon_refund',
                round_id=str(round.round_id),
                description=f'Abandoned round - refund ({penalty} coin penalty)',
            )
            db.add(transaction)
            await db.flush()

            logger.debug(f"✅ Round abandoned: refund {refund_amount} coins")
            return {
                "round_id": str(round.round_id),
                "status": "abandoned",
                "refund_amount": refund_amount,
            }, None

        except Exception as e:
            logger.error(f"❌ Abandon round failed: {e}")
            return {}, "abandon_failed"
