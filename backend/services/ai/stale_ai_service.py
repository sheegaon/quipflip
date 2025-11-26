"""Service for handling stale prompts and phrasesets with AI assistance."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.player_base import PlayerBase
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.round import Round
from backend.models.qf.vote import Vote
from backend.services.ai.ai_service import AIService
from backend.utils.model_registry import GameType, AIPlayerType
from backend.services import TransactionService


logger = logging.getLogger(__name__)


class StaleAIService:
    """Provide AI-generated copies and votes for stale game content."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.ai_service = AIService(db)

    async def _get_or_create_stale_player(
        self, ai_player_type: AIPlayerType, excluded: List[UUID] | None = None
    ) -> PlayerBase:
        """Fetch or create an AI player using the shared AI service helper."""

        return await self.ai_service.get_or_create_ai_player(
            ai_player_type, excluded=excluded
        )

    async def _find_stale_prompts(self) -> List[Round]:
        """
        Locate prompt rounds that have been waiting for copies beyond the stale threshold.

        Returns prompts that:
        1. Are older than the stale threshold
        2. Don't have a phraseset yet
        3. Have at least one empty copy slot (copy1 or copy2)
        """
        cutoff_time = datetime.now(UTC) - timedelta(days=self.settings.ai_stale_threshold_days)

        result = await self.db.execute(
            select(Round)
            .where(Round.round_type == "prompt")
            .where(Round.status == "submitted")
            .where(Round.created_at <= cutoff_time)
            .outerjoin(Phraseset, Phraseset.prompt_round_id == Round.round_id)
            .where(Phraseset.phraseset_id.is_(None))
            # Find prompts with at least one empty copy slot
            .where(
                (Round.copy1_player_id.is_(None)) | (Round.copy2_player_id.is_(None))
            )
            .order_by(Round.created_at.asc())
        )

        return list(result.scalars().all())

    async def _find_stale_phrasesets(self) -> List[Phraseset]:
        """
        Locate phrasesets that have been waiting for votes beyond the stale threshold.

        Returns phrasesets that:
        1. Are older than the stale threshold
        2. Are still open or closing (not resolved)
        3. Have fewer votes than the minimum threshold needed for resolution

        This allows stale AI to provide multiple votes until the phraseset can be resolved.
        """
        cutoff_time = datetime.now(UTC) - timedelta(days=self.settings.ai_stale_threshold_days)

        # Get the minimum votes needed (from settings or default to 3)
        min_votes_needed = getattr(self.settings, 'min_votes_for_resolution', 3)

        result = await self.db.execute(
            select(Phraseset)
            .where(Phraseset.status.in_(["open", "closing"]))
            .where(Phraseset.created_at <= cutoff_time)
            .where(Phraseset.vote_count < min_votes_needed)
            .options(
                selectinload(Phraseset.prompt_round),
                selectinload(Phraseset.copy_round_1),
                selectinload(Phraseset.copy_round_2),
            )
            .order_by(Phraseset.created_at.asc())
        )

        return list(result.scalars().all())

    async def run_stale_cycle(self) -> None:
        """
        Process stale prompts and phrasesets with AI-generated participation.

        Uses multiple AI players (similar to backup service) to legitimately fill
        multiple copy slots and provide multiple votes per phraseset.
        """

        stats = {
            "stale_prompts_found": 0,
            "stale_prompts_processed": 0,
            "stale_copies_generated": 0,
            "stale_phrasesets_found": 0,
            "stale_phrasesets_processed": 0,
            "stale_votes_generated": 0,
            "errors": 0,
        }

        try:
            from backend.services.qf.round_service import QFRoundService

            # Find stale content first (don't need player IDs for queries anymore)
            stale_prompts = await self._find_stale_prompts()
            stats["stale_prompts_found"] = len(stale_prompts)

            round_service = QFRoundService(self.db)

            # Process each stale prompt with a different AI player for each copy slot
            for prompt_round in stale_prompts:
                try:
                    initial_slot = None
                    if prompt_round.copy1_player_id is None:
                        initial_slot = "copy1"
                    elif prompt_round.copy2_player_id is None:
                        initial_slot = "copy2"

                    if initial_slot is None:
                        phraseset = await round_service.create_phraseset_if_ready(prompt_round)
                        if phraseset:
                            prompt_round.phraseset_status = "active"
                        continue

                    handler_exclusions = [
                        player_id
                        for player_id in [
                            prompt_round.copy1_player_id,
                            prompt_round.copy2_player_id,
                        ]
                        if player_id is not None
                    ]
                    stale_handler = await self._get_or_create_stale_player(
                        AIPlayerType.QF_IMPOSTOR, excluded=handler_exclusions
                    )

                    copy_phrase = await self.ai_service.get_impostor_phrase(prompt_round)

                    copy_round = Round(
                        round_id=uuid.uuid4(),
                        player_id=stale_handler.player_id,
                        round_type="copy",
                        status="submitted",
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(minutes=3),
                        cost=0,
                        prompt_round_id=prompt_round.round_id,
                        original_phrase=prompt_round.submitted_phrase,
                        copy_phrase=copy_phrase.upper(),
                        system_contribution=0,
                    )

                    current_slot = None
                    if prompt_round.copy1_player_id is None:
                        current_slot = "copy1"
                    elif prompt_round.copy2_player_id is None:
                        current_slot = "copy2"

                    if current_slot is None:
                        # Slot was taken by another participant after generation; skip saving the copy.
                        continue

                    self.db.add(copy_round)
                    # Flush to ensure copy_round is visible to create_phraseset_if_ready query
                    await self.db.flush()

                    if current_slot == "copy1":
                        prompt_round.copy1_player_id = stale_handler.player_id
                        prompt_round.phraseset_status = "waiting_copy1"
                    else:
                        prompt_round.copy2_player_id = stale_handler.player_id
                        if prompt_round.copy1_player_id is not None:
                            phraseset = await round_service.create_phraseset_if_ready(prompt_round)
                            if phraseset:
                                prompt_round.phraseset_status = "active"

                    stats["stale_prompts_processed"] += 1
                    stats["stale_copies_generated"] += 1

                    # Record successful copy generation metrics
                    await self.ai_service.metrics_service.record_operation(
                        operation_type="stale_copy",
                        provider=self.ai_service.provider,
                        model=self.ai_service.ai_model,
                        success=True,
                        error_message=None,
                        prompt_length=len(prompt_round.submitted_phrase) if prompt_round.submitted_phrase else 0,
                        response_length=len(copy_phrase),
                        validation_passed=True,
                    )

                except Exception as exc:
                    logger.error(
                        f"Failed to process stale prompt {getattr(prompt_round, 'round_id', 'unknown')}: {exc}"
                    )
                    stats["errors"] += 1

                    # Record failed copy generation metrics
                    try:
                        await self.ai_service.metrics_service.record_operation(
                            operation_type="stale_copy",
                            provider=self.ai_service.provider,
                            model=self.ai_service.ai_model,
                            success=False,
                            error_message=str(exc),
                            validation_passed=False,
                        )
                    except Exception as metrics_exc:
                        logger.warning(f"Failed to record metrics for failed copy: {metrics_exc}")

                    # Re-enqueue the prompt so it can be retried later
                    try:
                        from backend.services.qf.queue_service import QFQueueService
                        QFQueueService.add_prompt_round_to_queue(prompt_round.round_id)
                        logger.info(f"Re-enqueued prompt {prompt_round.round_id} after stale AI failure")
                    except Exception as queue_exc:
                        logger.error(f"Failed to re-enqueue prompt {prompt_round.round_id}: {queue_exc}")

            # Find stale phrasesets that need votes
            stale_phrasesets = await self._find_stale_phrasesets()
            stats["stale_phrasesets_found"] = len(stale_phrasesets)

            from backend.services.qf.vote_service import QFVoteService
            vote_service = QFVoteService(self.db)
            transaction_service = TransactionService(self.db, game_type=GameType.QF)

            # Process each stale phraseset with a different AI voter
            for phraseset in stale_phrasesets:
                try:
                    # Check if phraseset is still open (race condition protection)
                    await self.db.refresh(phraseset)
                    if phraseset.status not in ["open", "closing"]:
                        logger.info(
                            f"Skipping phraseset {phraseset.phraseset_id} - status changed to {phraseset.status}"
                        )
                        continue

                    # Select a different AI voter based on current vote count
                    # This ensures we use different players for each vote
                    voted_players_result = await self.db.execute(
                        select(Vote.player_id).where(
                            Vote.phraseset_id == phraseset.phraseset_id
                        )
                    )
                    voted_player_ids = list(voted_players_result.scalars().all())

                    stale_voter = await self._get_or_create_stale_player(
                        AIPlayerType.QF_VOTER, excluded=voted_player_ids
                    )

                    seed = stale_voter.player_id.int
                    chosen_phrase = await self.ai_service.generate_vote_choice(phraseset, seed)

                    await vote_service.submit_system_vote(
                        phraseset=phraseset,
                        player=stale_voter,
                        chosen_phrase=chosen_phrase,
                        transaction_service=transaction_service,
                    )

                    stats["stale_votes_generated"] += 1
                    stats["stale_phrasesets_processed"] += 1

                    # Record successful vote generation metrics
                    await self.ai_service.metrics_service.record_operation(
                        operation_type="stale_vote",
                        provider=self.ai_service.provider,
                        model=self.ai_service.ai_model,
                        success=True,
                        error_message=None,
                        prompt_length=len(phraseset.prompt_text) if phraseset.prompt_text else 0,
                        response_length=len(chosen_phrase),
                    )

                except Exception as exc:
                    logger.error(
                        f"Failed to process stale phraseset {getattr(phraseset, 'phraseset_id', 'unknown')}: {exc}"
                    )
                    stats["errors"] += 1

                    # Record failed vote generation metrics
                    try:
                        await self.ai_service.metrics_service.record_operation(
                            operation_type="stale_vote",
                            provider=self.ai_service.provider,
                            model=self.ai_service.ai_model,
                            success=False,
                            error_message=str(exc),
                        )
                    except Exception as metrics_exc:
                        logger.warning(f"Failed to record metrics for failed vote: {metrics_exc}")

            await self.db.commit()

            logger.info(
                "Stale AI cycle completed: "
                f"{stats['stale_prompts_processed']}/{stats['stale_prompts_found']} prompts processed, "
                f"{stats['stale_phrasesets_processed']}/{stats['stale_phrasesets_found']} phrasesets processed, "
                f"{stats['errors']} errors"
            )

        except Exception as exc:
            logger.error(f"Stale AI cycle failed: {exc}")
            await self.db.rollback()
            raise
