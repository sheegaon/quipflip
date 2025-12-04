"""ThinkLink round service.

Orchestrates round lifecycle: start, submit guess, finalize.
"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.tl import (
    TLRound, TLGuess, TLAnswer, TLCluster, TLTransaction, TLPrompt
)
from backend.models.player import Player
from backend.services.tl.matching_service import TLMatchingService
from backend.services.tl.clustering_service import TLClusteringService
from backend.services.tl.scoring_service import TLScoringService
from backend.services.tl.prompt_service import TLPromptService
from backend.services.phrase_validator import get_phrase_validator
from backend.config import get_settings

logger = logging.getLogger(__name__)


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

    async def start_round(
        self,
        db: AsyncSession,
        player_id: str,
    ) -> Tuple[Optional[TLRound], Optional[str]]:
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
            (TLRound, error_message) - error_message is None on success
        """
        try:
            logger.debug(f"🎮 Starting round for player {player_id}...")

            # Get player
            result = await db.execute(
                select(Player).where(Player.player_id == player_id)
            )
            player = result.scalars().first()
            if not player:
                return None, "Player not found"

            # Check balance
            if player.tl_wallet < self.entry_cost:
                return None, "insufficient_balance"

            # Select prompt
            prompt = await self.prompt.get_random_active_prompt(db)
            if not prompt:
                return None, "no_prompts_available"

            # Get active answers for snapshot
            answers = await self.prompt.get_active_answers_for_prompt(
                db, str(prompt.prompt_id), limit=1000
            )
            logger.debug(f"📊 Snapshot: {len(answers)} active answers")

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

            # Deduct entry cost
            player.tl_wallet -= self.entry_cost
            transaction = TLTransaction(
                player_id=player_id,
                amount=-self.entry_cost,
                transaction_type='round_entry',
                round_id=str(round.round_id),
                description=f'Round entry: {prompt.text[:50]}...',
            )
            db.add(transaction)
            await db.flush()

            logger.debug(
                f"✅ Round started: {round.round_id} "
                f"(prompt: {prompt.text[:50]}..., snapshot_weight={total_weight:.2f})"
            )
            return round, None

        except Exception as e:
            logger.error(f"❌ Start round failed: {e}")
            return None, "round_start_failed"

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
        5. Check on-topic
        6. Check self-similarity to prior guesses
        7. Find matches in snapshot answers
        8. Update matched_clusters if new match
        9. Add strike if no matches
        10. End round if 3 strikes
        11. Log guess

        Validation errors (invalid_phrase, off_topic, too_similar) do NOT consume strikes.

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
            logger.debug(f"💭 Submitting guess: '{guess_text}' for round {round_id}")

            # Get round
            result = await db.execute(
                select(TLRound).where(TLRound.round_id == round_id)
            )
            round = result.scalars().first()
            if not round:
                return {}, "round_not_found", None

            if round.player_id != player_id:
                return {}, "unauthorized", None

            if round.status != 'active':
                return {}, f"round_not_active", None

            if round.strikes >= self.max_strike_count:
                return {}, "round_already_ended", None

            # Validate phrase format and dictionary compliance
            validator = get_phrase_validator()
            is_valid, error_msg = validator.validate(guess_text)
            if not is_valid:
                logger.debug(f"⏭️  Guess rejected: invalid format ({error_msg})")
                return {}, "invalid_phrase", error_msg

            # Validate phrase doesn't reuse significant words from prompt
            prompt_text = round.prompt.text if hasattr(round, 'prompt') else await self._get_prompt_text(db, round.prompt_id)
            is_valid, error_msg = await validator.validate_prompt_phrase(guess_text, prompt_text)
            if not is_valid:
                logger.debug(f"⏭️  Guess rejected: conflicts with prompt ({error_msg})")
                return {}, "invalid_phrase", error_msg

            # Generate embedding for guess
            guess_embedding = await self.matching.generate_embedding(guess_text)

            # Check on-topic
            is_on_topic, topic_sim = await self.matching.check_on_topic(
                round.prompt.text if hasattr(round, 'prompt') else await self._get_prompt_text(db, round.prompt_id),
                guess_text,
                prompt_embedding=None,  # Recompute for safety
                threshold=self.prompt_relevance_threshold,
            )
            if not is_on_topic:
                logger.debug(f"⏭️  Guess rejected: off-topic (similarity={topic_sim:.3f})")
                message = (
                    f"Not on topic (similarity {topic_sim:.2f}, "
                    f"need ≥ {self.prompt_relevance_threshold:.2f})"
                )
                return {}, "off_topic", message

            # Check self-similarity
            prior_guesses = await self._get_prior_guesses(db, round_id)
            is_too_similar, max_sim = await self.matching.check_self_similarity(
                guess_text,
                prior_guesses,
                threshold=self.self_similarity_threshold,
            )
            if is_too_similar:
                logger.debug(f"⏭️  Guess rejected: too similar to prior (similarity={max_sim:.3f})")
                similarity_note = (
                    f"Too similar to your previous guess (similarity {max_sim:.2f}, "
                    f"max allowed {self.self_similarity_threshold:.2f})"
                ) if max_sim is not None else "Too similar to a prior guess"
                return {}, "too_similar", similarity_note

            # Find matches in snapshot
            snapshot_answers = await self._build_snapshot_answers(db, round.snapshot_answer_ids)
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
                logger.debug(f"✅ Matched {len(matched_cluster_ids)} new clusters")
            else:
                # Add strike
                round.strikes += 1
                new_strikes = round.strikes
                logger.debug(f"⚠️  No matches - strike {new_strikes}/3")

                if round.strikes >= self.max_strike_count:
                    round.status = 'abandoned'  # Mark as ended due to strikes
                    logger.debug(f"🏁 Round ended - 3 strikes reached")

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

            return {
                "was_match": was_match,
                "matched_answer_count": len(matches),
                "matched_cluster_ids": matched_cluster_ids,
                "new_strikes": new_strikes,
                "current_coverage": current_coverage,
                "round_status": round.status,
            }, None, None

        except Exception as e:
            logger.error(f"❌ Submit guess failed: {e}")
            return {}, "submit_failed", None

    async def abandon_round(
        self,
        db: AsyncSession,
        round_id: str,
        player_id: str,
    ) -> Tuple[Dict, Optional[str]]:
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

            if round.player_id != player_id:
                return {}, "unauthorized"

            if round.status != 'active':
                return {}, "round_not_active"

            # Calculate refund (entry_cost - 5 penalty = 95 coins)
            penalty = 5
            refund_amount = self.entry_cost - penalty

            # Update round
            round.status = 'abandoned'
            round.ended_at = datetime.now(UTC)

            # Refund to player
            player = await db.get(Player, player_id)
            player.tl_wallet += refund_amount

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

    async def _get_prompt_text(
        self,
        db: AsyncSession,
        prompt_id: str,
    ) -> str:
        """Helper to get prompt text."""
        result = await db.execute(
            select(TLPrompt).where(TLPrompt.prompt_id == prompt_id)
        )
        prompt = result.scalars().first()
        return prompt.text if prompt else ""

    async def _get_prior_guesses(
        self,
        db: AsyncSession,
        round_id: str,
    ) -> List[str]:
        """Get all prior guesses in a round."""
        result = await db.execute(
            select(TLGuess).where(TLGuess.round_id == round_id)
        )
        guesses = result.scalars().all()
        return [g.text for g in guesses]

    async def _build_snapshot_answers(
        self,
        db: AsyncSession,
        answer_ids: List[str],
    ) -> List[Dict]:
        """Build answer data for matching from snapshot IDs."""
        if not answer_ids:
            return []

        result = await db.execute(
            select(TLAnswer).where(TLAnswer.answer_id.in_(answer_ids))
        )
        answers = result.scalars().all()

        return [
            {
                "answer_id": str(a.answer_id),
                "text": a.text,
                "embedding": a.embedding,
                "cluster_id": str(a.cluster_id) if a.cluster_id else None,
            }
            for a in answers
        ]
