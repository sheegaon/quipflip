"""
QuipFlip Backup Orchestrator for AI-generated copies and votes.

This module handles the backup cycle logic for QuipFlip game, finding stalled
prompt rounds and phrasesets, and generating AI copies and votes to keep the game moving.
"""

import logging
import uuid
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.phraseset_activity import PhrasesetActivity
from backend.models.qf.vote import Vote
from backend.models.qf.ai_phrase_cache import QFAIPhraseCache
from backend.models.qf.ai_metric import QFAIMetric
from backend.services.qf import QueueService
from backend.utils.model_registry import AIPlayerType

logger = logging.getLogger(__name__)

AI_PLAYER_EMAIL_DOMAIN = "@quipflip.internal"


class QFBackupOrchestrator:
    """
    Orchestrates AI backup operations for QuipFlip game.

    Handles finding stalled prompt rounds and phrasesets, and coordinates
    with AIService to generate appropriate AI responses.
    """

    def __init__(self, ai_service):
        """
        Initialize the backup orchestrator.

        Args:
            ai_service: AIService instance for generating AI responses
        """
        self.ai_service = ai_service
        self.db = ai_service.db
        self.settings = ai_service.settings

    async def _has_ai_attempted_prompt_round_recently(self, prompt_round_id: str, lookback_hours: int = 6) -> bool:
        """
        Check if AI has already attempted to generate a copy for this prompt.

        Args:
            prompt_round_id: The prompt round ID to check
            lookback_hours: How far back to look for attempts (default: 6 hours)

        Returns:
            True if AI has attempted this prompt recently, False otherwise
        """
        # Look back specified hours for attempts
        since = datetime.now(UTC) - timedelta(hours=lookback_hours)

        # Check if there are any copy generation attempts for this prompt
        # We use the prompt round ID in error messages, so we can search for it
        result = await self.db.execute(
            select(QFAIMetric.metric_id)
            .where(QFAIMetric.operation_type == "copy_generation")
            .where(QFAIMetric.created_at >= since)
            .where(QFAIMetric.error_message.contains(str(prompt_round_id)))
            .limit(1)
        )

        return result.scalar_one_or_none() is not None

    async def run_backup_cycle(self) -> None:
        """
        Run a backup cycle to provide AI copies for waiting prompts and AI votes for waiting phrasesets.

        This method:
        1. Finds prompts that have been waiting for copies longer than the backup delay
        2. Filters out prompts that AI has already attempted recently
        3. Generates AI copies for those prompts
        4. Submits the copies as the AI player
        5. Finds phrasesets that have been waiting for votes longer than the backup delay
        6. Generates AI votes for those phrasesets
        7. Submits the votes as the AI player

        Note:
            This is the main entry point for the AI backup system and manages the complete transaction lifecycle.
        """
        stats = {
            "prompts_checked": 0,
            "prompts_filtered_already_attempted": 0,
            "copies_generated": 0,
            "phrasesets_checked": 0,
            "votes_generated": 0,
            "errors": 0,
        }

        try:
            # Query for submitted prompt rounds that:
            # 1. Don't have a phraseset yet (still waiting for copies)
            # 2. Are older than the backup delay
            # 3. Don't belong to the AI player (avoid self-copies)
            # 4. Haven't been copied by the AI player already

            # Determine backup delay
            cutoff_time = datetime.now(UTC) - timedelta(minutes=self.settings.ai_backup_delay_minutes)

            # Get all prompt rounds that meet our basic criteria
            from backend.models.qf.player import QFPlayer

            result = await self.db.execute(
                select(Round)
                .join(QFPlayer, QFPlayer.player_id == Round.player_id)
                .outerjoin(PhrasesetActivity, PhrasesetActivity.prompt_round_id == Round.round_id)
                .where(Round.round_type == 'prompt')
                .where(Round.status == 'submitted')
                .where(Round.created_at <= cutoff_time)
                .where(QFPlayer.email.notlike(f"%{AI_PLAYER_EMAIL_DOMAIN}"))  # Exclude AI player
                .where(PhrasesetActivity.phraseset_id.is_(None))  # Not yet a phraseset
                .order_by(Round.created_at.asc())  # Process oldest first
                # .limit(self.settings.ai_backup_batch_size)  # Configurable batch size
            )

            waiting_quip_rounds = set(result.scalars().all())

            # Filter out quips already copied by AI (check separately to avoid complex joins)
            filtered_quip_rounds = []
            for quip_round in waiting_quip_rounds:
                ai_copy_result = await self.db.execute(
                    select(Round.round_id)
                    .join(QFPlayer, QFPlayer.player_id == Round.player_id)
                    .where(Round.prompt_round_id == quip_round.round_id)
                    .where(Round.round_type == 'copy')
                    .where(QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"))
                )

                if ai_copy_result.scalars().first() is None:
                    filtered_quip_rounds.append(quip_round)

            # Filter out prompts that already have a phrase cache with backup copies used
            # (This prevents wasting cached phrases on redundant backup attempts)
            final_quip_rounds = []
            for quip_round in filtered_quip_rounds:
                # Check if phrase cache exists and has been used for backup
                cache_result = await self.db.execute(
                    select(QFAIPhraseCache.cache_id)
                    .where(QFAIPhraseCache.prompt_round_id == quip_round.round_id)
                    .where(QFAIPhraseCache.used_for_backup_copy == True)
                )
                cache_exists = cache_result.scalar_one_or_none() is not None

                if not cache_exists:
                    final_quip_rounds.append(quip_round)
                else:
                    stats["prompts_filtered_already_attempted"] += 1
                    logger.info(f"Skipping quip {quip_round.round_id} - AI cache already used for backup")

                if len(final_quip_rounds) >= self.settings.ai_backup_batch_size:
                    break  # Limit to batch size

            stats["prompts_checked"] = len(final_quip_rounds)
            logger.info(
                f"Found {len(final_quip_rounds)} quips waiting for AI fakes "
                f"(filtered out {stats['prompts_filtered_already_attempted']} already attempted)"
            )

            # Process each waiting prompt
            for quip_round in final_quip_rounds:
                try:
                    # Try to claim the prompt in the queue so only one worker (AI or other) processes it
                    claimed = QueueService.remove_prompt_round_from_queue(quip_round.round_id)
                    if not claimed:
                        # Someone else claimed or removed it from the queue
                        logger.info(f"Skipping prompt {quip_round.round_id} - could not claim from queue")
                        continue

                    # Generate AI copy phrase with proper validation context
                    copy_phrase = await self.ai_service.get_impostor_phrase(quip_round)

                    # Create copy round for AI player
                    from backend.services import RoundService
                    round_service = RoundService(self.db)

                    # Get or create AI copy player (within transaction)
                    ai_impostor_player = await self.ai_service.get_or_create_ai_player(AIPlayerType.QF_IMPOSTOR)

                    # Start copy round for AI player
                    copy_round = Round(
                        round_id=uuid.uuid4(),
                        player_id=ai_impostor_player.player_id,
                        round_type='copy',
                        status='submitted',
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(minutes=3),  # Standard copy round time
                        cost=0,  # AI doesn't pay
                        prompt_round_id=quip_round.round_id,
                        original_phrase=quip_round.submitted_phrase,
                        copy_phrase=copy_phrase.upper(),
                        system_contribution=0,  # AI contributions are free
                    )

                    self.db.add(copy_round)
                    # Flush to ensure copy_round is visible to create_phraseset_if_ready query
                    await self.db.flush()

                    # Update prompt round copy assignment
                    if quip_round.copy1_player_id is None:
                        quip_round.copy1_player_id = ai_impostor_player.player_id
                        quip_round.phraseset_status = "waiting_copy1"
                    elif quip_round.copy2_player_id is None:
                        quip_round.copy2_player_id = ai_impostor_player.player_id
                        # Check if we now have both copies and can create phraseset
                        if quip_round.copy1_player_id is not None:
                            phraseset = await round_service.create_phraseset_if_ready(quip_round)
                            if phraseset:
                                quip_round.phraseset_status = "active"

                    stats["copies_generated"] += 1

                except Exception as e:
                    logger.error(f"Failed to generate AI copy for prompt {quip_round.round_id}: {e}")
                    stats["errors"] += 1
                    # Put the prompt back into the queue so it can be retried later
                    try:
                        QueueService.add_prompt_round_to_queue(quip_round.round_id)
                        logger.info(f"Re-enqueued prompt {quip_round.round_id} after AI failure")
                    except Exception as q_e:
                        logger.error(f"Failed to re-enqueue prompt {quip_round.round_id}: {q_e}")
                    continue

            # Query for phrasesets waiting for votes that:
            # 1. Are in "open" or "closing" status (accepting votes)
            # 2. Were created older than the backup delay
            # 3. Don't have contributions from the AI player (avoid self-votes) [disabled]
            # 4. Haven't been voted on by the AI player already (using subquery) [disabled]
            # 5. Exclude phrasesets from test players [disabled]

            # Create subquery to find phrasesets where AI has already voted
            # ai_voted_subquery = select(Vote.phraseset_id).where(Vote.player_id == ai_player.player_id)

            # Get all phrasesets that meet our basic criteria
            from backend.models.qf.player import QFPlayer

            human_vote_phrasesets_subquery = (
                select(Vote.phraseset_id)
                .join(QFPlayer, QFPlayer.player_id == Vote.player_id)
                .where(~QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"))
                .distinct()
            )

            phraseset_result = await self.db.execute(
                select(Phraseset)
                .where(Phraseset.status.in_(["open", "closing"]))
                .where(Phraseset.created_at <= cutoff_time)
                .where(Phraseset.phraseset_id.in_(human_vote_phrasesets_subquery))
                .options(
                    selectinload(Phraseset.prompt_round),
                    selectinload(Phraseset.copy_round_1),
                    selectinload(Phraseset.copy_round_2),
                )
                .order_by(Phraseset.created_at.asc())  # Process oldest first
                .limit(self.settings.ai_backup_batch_size)  # Use configured batch size
            )

            # Filter out phrasesets with activity after cutoff_time
            waiting_phrasesets = list(phraseset_result.scalars().all())
            filtered_phrasesets = []
            for phraseset in waiting_phrasesets:
                activity = await self.db.execute(
                    select(PhrasesetActivity)
                    .where(PhrasesetActivity.phraseset_id == phraseset.phraseset_id)
                    .where(PhrasesetActivity.created_at > cutoff_time)
                )
                if len(activity.scalars().all()) == 0:
                    filtered_phrasesets.append(phraseset)

            stats["phrasesets_checked"] = len(filtered_phrasesets)
            logger.info(
                f"Found {len(filtered_phrasesets)} phrasesets waiting for AI backup votes: {filtered_phrasesets}")

            # Initialize services once for all votes
            from backend.services import VoteService
            from backend.services import TransactionService
            vote_service = VoteService(self.db)
            transaction_service = TransactionService(self.db)

            # Process each waiting phraseset
            for phraseset in filtered_phrasesets:
                try:
                    # Find an AI voter who has NOT voted on this phraseset
                    # We look for players with email starting with "ai_voter"
                    # who do not have a vote record for this phraseset_id

                    # Players who HAVE voted on this phraseset
                    voted_players_subquery = (
                        select(Vote.player_id)
                        .where(Vote.phraseset_id == phraseset.phraseset_id)
                    )
                    voted_players_result = await self.db.execute(voted_players_subquery)
                    voted_players = set(voted_players_result.scalars().all())

                    # Get available AI voter
                    ai_voter_player = await self.ai_service.get_or_create_ai_player(
                        AIPlayerType.QF_VOTER,
                        excluded=[p.player_id for p in voted_players])

                    # Generate AI vote choice
                    seed = ai_voter_player.player_id.int
                    chosen_phrase = await self.ai_service.generate_vote_choice(phraseset, seed)

                    # Use VoteService for centralized voting logic
                    vote = await vote_service.submit_system_vote(
                        phraseset=phraseset,
                        player=ai_voter_player,
                        chosen_phrase=chosen_phrase,
                        transaction_service=transaction_service,
                    )

                    stats["votes_generated"] += 1
                    logger.info(
                        f"AI generated vote '{vote.voted_phrase}' for phraseset {phraseset.phraseset_id} "
                        f"({'CORRECT' if vote.correct else 'INCORRECT'}, payout: {vote.payout})"
                    )

                except Exception as e:
                    logger.error(f"Failed to generate AI vote for phraseset {phraseset.phraseset_id}: {e}")
                    stats["errors"] += 1
                    continue

            # Commit all changes
            await self.db.commit()

        except Exception as exc:
            logger.error(f"AI backup cycle failed: {exc}")
            await self.db.rollback()
            stats["errors"] += 1

        finally:
            logger.info(f"AI backup cycle completed: {stats}")
