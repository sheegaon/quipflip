"""Round service for managing prompt, copy, and vote rounds."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from datetime import datetime, UTC, timedelta
import asyncio
from typing import Optional
from uuid import UUID
import uuid
import logging

from backend.models.qf.player import QFPlayer
from backend.models.qf.prompt import Prompt
from backend.models.qf.round import Round
from backend.models.qf.flagged_prompt import FlaggedPrompt
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.player_abandoned_prompt import PlayerAbandonedPrompt
from backend.services.transaction_service import TransactionService
from backend.services.qf.queue_service import QueueService
from backend.services.qf.phraseset_activity_service import ActivityService
from backend.config import get_settings
from backend.utils import ensure_utc
from backend.utils.exceptions import (
    InvalidPhraseError,
    DuplicatePhraseError,
    RoundNotFoundError,
    RoundExpiredError,
    NoPromptsAvailableError,
    InsufficientBalanceError,
)
from backend.services.ai.ai_service import AIServiceError
from backend.services.qf.round_service_helpers import (
    generate_ai_hints_background,
    revalidate_ai_hints_background,
    PromptQueryBuilder,
    RoundValidationHelper,
    CostCalculationHelper,
    PhrasesetCreationHelper,
    RoundTimeoutHelper,
    QueueManagementHelper,
)

logger = logging.getLogger(__name__)


class RoundService:
    """Service for managing game rounds."""

    AVAILABLE_PROMPTS_CACHE_TTL_SECONDS = 15

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self._available_prompts_cache: dict[UUID, tuple[int, datetime]] = {}
        if self.settings.use_phrase_validator_api:
            from backend.services.phrase_validation_client import get_phrase_validation_client
            self.phrase_validator = get_phrase_validation_client()
        else:
            from backend.services.phrase_validator import get_phrase_validator
            self.phrase_validator = get_phrase_validator()
        self.activity_service = ActivityService(db)
        from backend.services import AIService
        try:
            self.ai_service = AIService(db)
        except AIServiceError:
            logger.warning(
                "AI service unavailable during RoundService initialization; disabling AI-dependent features",
            )
            self.ai_service = None

    async def start_prompt_round(self, player: QFPlayer, transaction_service: TransactionService) -> Optional[Round]:
        """
        Start a prompt round.

        - Deduct $100 immediately
        - Randomly assign prompt
        - Create round with 3-minute timer

        All operations are performed in a single atomic transaction within a distributed lock.
        """
        from backend.utils import lock_client
        import time

        # Acquire lock for the entire transaction
        lock_name = f"start_prompt_round:{player.player_id}"
        lock_start = time.perf_counter()
        with lock_client.lock(lock_name, timeout=self.settings.round_lock_timeout_seconds):
            lock_acquired = time.perf_counter()
            logger.info(f"[{player.player_id}] Lock acquired after {lock_acquired - lock_start:.3f}s")

            prompt_start = time.perf_counter()
            prompt = await self._select_prompt_for_player(player)
            prompt_end = time.perf_counter()
            logger.info(f"[{player.player_id}] _select_prompt_for_player took {prompt_end - prompt_start:.3f}s")

            create_start = time.perf_counter()
            round_object = await self._create_prompt_round(player, prompt, transaction_service)
            create_end = time.perf_counter()
            logger.info(f"[{player.player_id}] _create_prompt_round took {create_end - create_start:.3f}s")

            logger.info(f"[{player.player_id}] Total lock held time: {create_end - lock_acquired:.3f}s")

        # Invalidate dashboard cache to ensure fresh data
        from backend.utils.cache import dashboard_cache
        dashboard_cache.invalidate_player_data(player.player_id)

        logger.debug(f"Started prompt round {round_object.round_id} for player {player.player_id}")
        return round_object

    async def _create_prompt_round(
        self,
        player: QFPlayer,
        prompt: Prompt,
        transaction_service: TransactionService,
    ) -> Round:
        """Create a prompt round and commit it in a single transaction."""
        import time

        t0 = time.perf_counter()
        await transaction_service.create_transaction(
            player.player_id,
            -self.settings.prompt_cost,
            "prompt_entry",
            auto_commit=False,
            skip_lock=True,
        )
        t1 = time.perf_counter()
        logger.info(f"[{player.player_id}] create_transaction took {t1-t0:.3f}s")

        round_object = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="active",
            cost=self.settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.prompt_round_seconds),
            prompt_id=prompt.prompt_id,
            prompt_text=prompt.text,
        )
        t2 = time.perf_counter()
        logger.info(f"[{player.player_id}] Round object creation took {t2-t1:.3f}s")

        self.db.add(round_object)
        await self.db.flush()
        t3 = time.perf_counter()
        logger.info(f"[{player.player_id}] db.flush took {t3-t2:.3f}s")

        player.active_round_id = round_object.round_id
        await self._increment_prompt_usage(prompt.prompt_id)
        t4 = time.perf_counter()
        logger.info(f"[{player.player_id}] increment_prompt_usage took {t4-t3:.3f}s")

        await self.db.commit()
        t5 = time.perf_counter()
        logger.info(f"[{player.player_id}] db.commit took {t5-t4:.3f}s")

        await self.db.refresh(round_object)
        t6 = time.perf_counter()
        logger.info(f"[{player.player_id}] db.refresh took {t6-t5:.3f}s")

        return round_object

    async def _increment_prompt_usage(self, prompt_id: UUID) -> None:
        """Increment prompt usage with ORM update for atomicity."""

        update_stmt = (
            update(Prompt)
            .where(Prompt.prompt_id == prompt_id)
            .values(usage_count=Prompt.usage_count + 1)
        )
        result = await self.db.execute(update_stmt)
        if result.rowcount == 0:
            raise RuntimeError("Failed to update prompt usage count")

    async def _select_prompt_for_player(self, player: QFPlayer) -> Prompt:
        """Fetch a random prompt the player has not seen yet."""
        import time
        import random

        t0 = time.perf_counter()
        prompt_stmt = PromptQueryBuilder.build_unseen_prompts_query(player.player_id)
        t1 = time.perf_counter()
        logger.info(f"[{player.player_id}] build_unseen_prompts_query took {t1-t0:.3f}s")

        result = await self.db.execute(prompt_stmt)
        t2 = time.perf_counter()
        logger.info(f"[{player.player_id}] db.execute(prompt_stmt) took {t2-t1:.3f}s")

        # Fetch all available prompts from the batch (up to 20)
        prompts = result.scalars().all()
        t3 = time.perf_counter()
        logger.info(f"[{player.player_id}] scalars().all() returned {len(prompts)} prompts in {t3-t2:.3f}s")

        if not prompts:
            logger.debug(f"Player {player.player_id} has seen all available prompts; no unseen prompts remaining")
            raise NoPromptsAvailableError("no_unseen_prompts_available")

        # Randomly select one prompt from the batch (much faster than ORDER BY random())
        prompt = random.choice(prompts)
        t4 = time.perf_counter()
        logger.info(f"[{player.player_id}] random.choice() took {t4-t3:.3f}s")

        return prompt

    async def submit_prompt_phrase(
            self,
            round_id: UUID,
            phrase: str,
            player: QFPlayer,
            transaction_service: TransactionService,
    ) -> Optional[Round]:
        """Submit word for prompt round."""
        round_object = await self._lock_round_for_update(round_id)
        if not round_object or round_object.player_id != player.player_id:
            raise RoundNotFoundError("Round not found")

        if round_object.status != "active":
            raise ValueError("Round is not active")

        # Check grace period
        # Make grace_cutoff timezone-aware if expires_at is naive (SQLite stores naive)
        expires_at_aware = ensure_utc(round_object.expires_at)
        grace_cutoff = expires_at_aware + timedelta(seconds=self.settings.grace_period_seconds)
        now = datetime.now(UTC)

        if now > grace_cutoff:
            logger.error(
                f"Round {round_id} expired: expires_at={expires_at_aware}, "
                f"grace_cutoff={grace_cutoff}, now={now}, "
                f"grace_period={self.settings.grace_period_seconds}s, "
                f"round_seconds={self.settings.prompt_round_seconds}s, "
                f"time_since_creation={(now - ensure_utc(round_object.created_at)).total_seconds():.2f}s"
            )
            raise RoundExpiredError("Round expired past grace period")

        # Validate word against prompt text
        is_valid, error = await self.phrase_validator.validate_prompt_phrase(phrase, round_object.prompt_text)
        if not is_valid:
            raise InvalidPhraseError(error)

        # Update round
        round_object.submitted_phrase = phrase.strip().upper()
        round_object.status = "submitted"
        round_object.phraseset_status = "waiting_copies"

        # Clear player's active round
        player.active_round_id = None

        # Add to queue
        QueueService.add_prompt_round_to_queue(round_object.round_id)

        await self.activity_service.record_activity(
            activity_type="prompt_submitted",
            prompt_round_id=round_object.round_id,
            player_id=player.player_id,
            metadata={
                "prompt_text": round_object.prompt_text,
                "phrase": round_object.submitted_phrase,
            },
        )

        await self.db.commit()
        await self.db.refresh(round_object)

        # Immediately kick off AI copy generation without blocking the response
        asyncio.create_task(generate_ai_hints_background(round_object.round_id))

        # Track quest progress for round completion
        from backend.services.qf.quest_service import QuestService
        quest_service = QuestService(self.db)
        try:
            await quest_service.increment_round_completion(player.player_id)
            await quest_service.check_milestone_prompts(player.player_id)
            await quest_service.check_balanced_player(player.player_id)
        except Exception as e:
            logger.error(f"Failed to update quest progress for prompt round: {e}", exc_info=True)

        # Invalidate dashboard cache to ensure fresh data
        from backend.utils.cache import dashboard_cache
        dashboard_cache.invalidate_player_data(player.player_id)

        logger.debug(f"Submitted phrase for prompt round {round_id}: {phrase}")
        return round_object

    async def start_copy_round(
        self,
        player: QFPlayer,
        transaction_service: TransactionService,
        prompt_round_id: Optional[UUID] = None,
        *,
        force_prompt_round: bool = False,
        prompt_from_queue: bool = False,
    ) -> tuple[Optional[Round], bool]:
        """
        Start a copy round.

        - Get next prompt from queue (FIFO) OR use provided prompt_round_id for second copy
        - Check discount (>10 prompts waiting) - not applicable for second copy
        - Deduct cost immediately (2x for second copy)
        - Prevent same player from getting abandoned prompt (24h)

        Args:
            player: The player starting the copy round
            transaction_service: Transaction service for payment
            prompt_round_id: Optional prompt round ID for second copy requests

        Returns:
            Tuple of (Round object, is_second_copy flag)
        """
        logger.debug(
            f"{player.player_id=} attempting to start copy round (second_copy="
            f"{prompt_round_id is not None and not force_prompt_round}, forced={force_prompt_round})"
        )

        is_second_copy = prompt_round_id is not None and not force_prompt_round

        if is_second_copy:
            # Second copy: use the provided prompt_round_id
            prompt_round = await self.db.get(Round, prompt_round_id)
            if not prompt_round or prompt_round.round_type != "prompt":
                raise ValueError("Invalid prompt round ID for second copy")

            # Verify the second copy slot is still available
            if prompt_round.copy2_player_id is not None:
                raise ValueError("Second copy slot for this prompt is already filled")

            # Verify player has already done first copy
            existing_copies_count = (
                await self.db.execute(
                    select(func.count())
                    .select_from(Round)
                    .filter(
                        Round.player_id == player.player_id,
                        Round.round_type == "copy",
                        Round.prompt_round_id == prompt_round_id,
                        Round.status == "submitted",
                    )
                )
            ).scalar()

            if existing_copies_count == 0:
                raise ValueError("Player must complete first copy before requesting second copy")
            if existing_copies_count >= 2:
                raise ValueError("Player has already completed two copies for this prompt")

            # Second copy costs 2x the normal cost (no discount)
            copy_cost = self.settings.copy_cost_normal * 2
            system_contribution = 0

            # Remove prompt from queue since this player is taking the second copy slot
            # (prevents other players from being matched with this prompt)
            removed = QueueService.remove_prompt_round_from_queue(prompt_round_id)
            if removed:
                logger.debug(f"Removed prompt {prompt_round_id} from queue for second copy")
            else:
                logger.warning(f"Prompt {prompt_round_id} was not in queue when starting second copy")

            logger.debug(f"Starting second copy for prompt {prompt_round_id}, cost={copy_cost}")
        else:
            # First copy: either use provided prompt (party mode) or pull from queue
            if prompt_round_id and force_prompt_round:
                prompt_round = await self._get_specific_prompt_round_for_copy(
                    player, prompt_round_id, prompt_from_queue
                )
            else:
                queue_populated = await self.ensure_prompt_queue_populated()
                logger.debug(f"{queue_populated=}, queue length: {QueueService.get_prompt_rounds_waiting()}")

                prompt_round = await self._get_next_valid_prompt_round(
                    player, self.settings.copy_round_max_attempts
                )

            copy_cost, is_discounted, system_contribution = self._calculate_copy_round_cost()

        round_object = await self._create_copy_round(
            player,
            prompt_round,
            copy_cost,
            system_contribution,
            transaction_service,
        )

        from backend.utils.cache import dashboard_cache

        dashboard_cache.invalidate_player_data(player.player_id)

        logger.debug(f"Started {round_object.round_id=} for {player.player_id=}, {copy_cost=}, {is_second_copy=}")
        return round_object, is_second_copy

    def _calculate_copy_round_cost(self) -> tuple[int, bool, int]:
        """Return copy round cost, discount flag, and system contribution."""
        return CostCalculationHelper.calculate_copy_round_cost(self.settings, QueueService)

    async def _create_copy_round(
        self,
        player: QFPlayer,
        prompt_round: Round,
        copy_cost: int,
        system_contribution: int,
        transaction_service: TransactionService,
    ) -> Round:
        """Create a copy round and persist it atomically."""

        from backend.utils import lock_client

        lock_name = f"start_copy_round:{player.player_id}"
        with lock_client.lock(lock_name, timeout=self.settings.round_lock_timeout_seconds):
            await transaction_service.create_transaction(
                player.player_id,
                -copy_cost,
                "copy_entry",
                auto_commit=False,
                skip_lock=True,
            )

            round_object = Round(
                round_id=uuid.uuid4(),
                player_id=player.player_id,
                round_type="copy",
                status="active",
                cost=copy_cost,
                expires_at=datetime.now(UTC)
                + timedelta(seconds=self.settings.copy_round_seconds),
                prompt_round_id=prompt_round.round_id,
                original_phrase=prompt_round.submitted_phrase,
                system_contribution=system_contribution,
            )

            self.db.add(round_object)
            await self.db.flush()

            player.active_round_id = round_object.round_id

            await self.db.commit()
            await self.db.refresh(round_object)

        return round_object

    async def _get_next_valid_prompt_round(self, player: QFPlayer, max_attempts: int) -> Round:
        """
        Retrieve and lock the next eligible prompt round for the player.

        Uses an adaptive retry strategy:
        - Stale/not-found entries don't count fully against max_attempts
        - After 5 consecutive stale entries, triggers queue rehydration
        - This prevents the queue from containing stale IDs that block valid prompts
        """

        attempts = 0
        stale_count = 0  # Track consecutive stale/not-found entries
        candidate_prompt_round_ids: list[UUID] = []
        prefetched_rounds: dict[UUID, Round] = {}
        tried_prompt_ids: set[UUID] = set()  # Track prompts we've already tried in this request

        while attempts < max_attempts:
            if not candidate_prompt_round_ids:
                # Check if we've hit too many stale entries - trigger rehydration
                if stale_count >= 5:
                    logger.warning(f"Found {stale_count} consecutive stale entries, rehydrating queue")
                    await self.ensure_prompt_queue_populated()
                    stale_count = 0  # Reset counter after rehydration

                candidate_prompt_round_ids = await self._pop_prompt_batch(max_attempts - attempts)
                # Filter out prompts we've already tried in this request to prevent cycling.
                # Filtered prompts will be requeued at the end (success or failure).
                candidate_prompt_round_ids = [
                    pid for pid in candidate_prompt_round_ids if pid not in tried_prompt_ids]

                if not candidate_prompt_round_ids:
                    logger.warning(f"No new prompts available (attempt {attempts + 1}, tried "
                                   f"{len(tried_prompt_ids)} unique prompts), rehydrating queue")
                    await self.ensure_prompt_queue_populated()
                    candidate_prompt_round_ids = await self._pop_prompt_batch(max_attempts - attempts)
                    # Filter again after rehydration
                    candidate_prompt_round_ids = [
                        pid for pid in candidate_prompt_round_ids if pid not in tried_prompt_ids]

                    if not candidate_prompt_round_ids:
                        logger.error(
                            f"No new prompts available after rehydration. Queue length: "
                            f"{QueueService.get_prompt_rounds_waiting()}, already tried {len(tried_prompt_ids)} "
                            f"unique prompts")
                        # Requeue everything we tried before raising
                        for tried_prompt_id in tried_prompt_ids:
                            QueueService.add_prompt_round_to_queue(tried_prompt_id)
                        raise NoPromptsAvailableError("No prompts available")

                await self._prefetch_prompt_rounds(
                    candidate_prompt_round_ids, prefetched_rounds
                )

            prompt_round_id = candidate_prompt_round_ids.pop(0)
            prompt_round = prefetched_rounds.get(prompt_round_id)
            attempts += 1
            logger.debug(f"Attempt {attempts}/{max_attempts} for player {player.player_id} using prompt "
                        f"{prompt_round_id}")

            if not prompt_round:
                stale_count += 1
                logger.warning(f"Prompt round not found in DB: {prompt_round_id} ({attempts=}, {stale_count=})")
                # Don't count stale entries as heavily - only count as 0.5 attempts
                if stale_count % 2 == 1:  # Every other stale entry, don't count attempt
                    attempts -= 1
                continue

            # Reset stale counter when we find a valid DB entry
            stale_count = 0

            if prompt_round.phraseset_status in {"flagged_pending", "flagged_removed"}:
                logger.debug(f"{prompt_round_id=} is flagged (status={prompt_round.phraseset_status}), "
                             f"skipping for copy queue ({attempts=})")
                # Don't requeue flagged prompts and don't mark as tried
                continue

            # Mark this prompt as tried (after flagged check)
            tried_prompt_ids.add(prompt_round_id)

            should_skip, should_requeue = await self._should_skip_prompt_round(
                player, prompt_round
            )
            if should_skip:
                # Don't requeue immediately - we'll requeue all tried prompts at the end
                # This prevents infinite cycling through the same unavailable prompts
                continue

            locked_prompt_round = await self._lock_prompt_round_for_update(prompt_round_id)
            if not locked_prompt_round:
                # Couldn't lock this prompt, but don't requeue yet - wait until end
                continue

            logger.debug(f"Found valid prompt {prompt_round_id} for player {player.player_id} on attempt {attempts}")

            # Success! Requeue remaining candidates and all tried prompts (except the one we're using)
            tried_prompt_ids.discard(prompt_round_id)  # Don't requeue the one we're using
            for remaining_prompt_round_id in candidate_prompt_round_ids:
                QueueService.add_prompt_round_to_queue(remaining_prompt_round_id)
            for tried_prompt_id in tried_prompt_ids:
                QueueService.add_prompt_round_to_queue(tried_prompt_id)

            return locked_prompt_round

        # Failed to find a valid prompt - requeue everything we tried
        for remaining_prompt_round_id in candidate_prompt_round_ids:
            QueueService.add_prompt_round_to_queue(remaining_prompt_round_id)
        for tried_prompt_id in tried_prompt_ids:
            QueueService.add_prompt_round_to_queue(tried_prompt_id)

        logger.error(
            f"Could not find valid prompt for player {player.player_id} after {max_attempts} attempts. "
            f"{QueueService.get_prompt_rounds_waiting()=}, tried {len(tried_prompt_ids)} unique prompts, {stale_count=}"
        )
        raise NoPromptsAvailableError(
            "Could not find a valid prompt after multiple attempts"
        )

    async def _get_specific_prompt_round_for_copy(
        self,
        player: QFPlayer,
        prompt_round_id: UUID,
        prompt_from_queue: bool,
    ) -> Round:
        """
        Retrieve and lock a specific prompt round chosen outside the queue.

        Args:
            player: Player requesting the copy round
            prompt_round_id: Prompt round to lock
            prompt_from_queue: Whether the prompt originated from the global queue
        """
        prompt_round = await self.db.get(Round, prompt_round_id)
        if not prompt_round or prompt_round.round_type != "prompt":
            if prompt_from_queue:
                QueueService.add_prompt_round_to_queue(prompt_round_id)
            raise NoPromptsAvailableError("Prompt not available")

        if prompt_round.status != "submitted":
            if prompt_from_queue:
                QueueService.add_prompt_round_to_queue(prompt_round_id)
            raise NoPromptsAvailableError("Prompt no longer available")

        if prompt_round.phraseset_status in {"flagged_pending", "flagged_removed"}:
            logger.debug(f"{prompt_round_id=} is flagged, skipping forced copy assignment")
            if prompt_from_queue:
                QueueService.add_prompt_round_to_queue(prompt_round_id)
            raise NoPromptsAvailableError("Prompt not available")

        locked_prompt_round = await self._lock_prompt_round_for_update(prompt_round_id)
        if not locked_prompt_round:
            if prompt_from_queue:
                QueueService.add_prompt_round_to_queue(prompt_round_id)
            raise NoPromptsAvailableError("Prompt unavailable")

        should_skip, should_requeue = await self._should_skip_prompt_round(player, locked_prompt_round)
        if should_skip:
            if prompt_from_queue or should_requeue:
                QueueService.add_prompt_round_to_queue(prompt_round_id)
            raise NoPromptsAvailableError("Prompt not eligible")

        return locked_prompt_round

    @staticmethod
    async def _pop_prompt_batch(limit: int) -> list[UUID]:
        """Pop the next batch of prompt IDs from the queue."""

        return QueueService.get_next_prompt_round_batch(limit)

    async def _prefetch_prompt_rounds(self, prompt_ids: list[UUID], prefetched_rounds: dict[UUID, Round]) -> None:
        """Load prompt rounds for the provided IDs, updating the cache."""
        await QueueManagementHelper.prefetch_prompt_rounds(self.db, prompt_ids, prefetched_rounds)

    async def _should_skip_prompt_round(self, player: QFPlayer, prompt_round: Round) -> tuple[bool, bool]:
        """Determine if the candidate prompt should be skipped and requeued."""
        return await RoundValidationHelper.check_prompt_round_eligibility(
            self.db, player, prompt_round, self.settings.abandoned_prompt_cooldown_hours)

    async def _lock_prompt_round_for_update(self, prompt_round_id: UUID) -> Optional[Round]:
        """Lock the prompt round row to avoid assignment races."""

        result = await self.db.execute(
            select(Round)
            .where(Round.round_id == prompt_round_id)
            .with_for_update()
        )
        prompt_round = result.scalar_one_or_none()

        if not prompt_round:
            logger.warning(f"Prompt round {prompt_round_id} missing when attempting to lock")
            return None

        if prompt_round.status != "submitted":
            logger.debug(f"Prompt {prompt_round_id} no longer submitted (status={prompt_round.status}), skipping")
            return None

        if prompt_round.phraseset_status in {"flagged_pending", "flagged_removed"}:
            logger.debug(f"Prompt {prompt_round_id} flagged during locking, skipping")
            return None

        return prompt_round

    async def _lock_round_for_update(self, round_id: UUID) -> Optional[Round]:
        """Lock a round record for update to avoid concurrent submissions."""

        result = await self.db.execute(select(Round).where(Round.round_id == round_id).with_for_update())
        return result.scalar_one_or_none()

    async def submit_copy_phrase(
            self,
            round_id: UUID,
            phrase: str,
            player: QFPlayer,
            transaction_service: TransactionService,
    ) -> tuple[Optional[Round], dict]:
        """Submit phrase for copy round."""
        round_object = await self._lock_round_for_update(round_id)
        if not round_object or round_object.player_id != player.player_id:
            raise RoundNotFoundError("Round not found")

        if round_object.status != "active":
            raise ValueError("Round is not active")

        # Check grace period
        # Make grace_cutoff timezone-aware if expires_at is naive (SQLite stores naive)
        expires_at_aware = ensure_utc(round_object.expires_at)
        grace_cutoff = expires_at_aware + timedelta(seconds=self.settings.grace_period_seconds)
        now = datetime.now(UTC)

        if now > grace_cutoff:
            logger.error(
                f"Copy round {round_id} expired: expires_at={expires_at_aware}, "
                f"grace_cutoff={grace_cutoff}, now={now}, "
                f"grace_period={self.settings.grace_period_seconds}s, "
                f"round_seconds={self.settings.copy_round_seconds}s, "
                f"time_since_creation={(now - ensure_utc(round_object.created_at)).total_seconds():.2f}s"
            )
            raise RoundExpiredError("Round expired past grace period")

        # Determine if another copy already exists for duplicate/similarity checks
        other_copy_phrase = None
        if round_object.prompt_round_id:
            result = await self.db.execute(
                select(Round.copy_phrase)
                .where(Round.prompt_round_id == round_object.prompt_round_id)
                .where(Round.round_type == "copy")
                .where(Round.status == "submitted")
                .where(Round.round_id != round_id)
            )
            other_copy_phrase = result.scalars().first()

        prompt_text = None
        prompt_round = None
        if round_object.prompt_round_id:
            prompt_round = await self.db.get(Round, round_object.prompt_round_id)
            if prompt_round:
                prompt_text = prompt_round.prompt_text

        # Validate phrase (including duplicate check)
        is_valid, error = await self.phrase_validator.validate_copy(
            phrase,
            round_object.original_phrase,
            other_copy_phrase,
            prompt_text,
        )
        if not is_valid:
            if "same phrase" in error.lower():
                raise DuplicatePhraseError(error)
            raise InvalidPhraseError(error)

        # Update round
        round_object.copy_phrase = phrase.strip().upper()
        round_object.status = "submitted"

        # Clear player's active round
        player.active_round_id = None

        if prompt_round:
            is_first_copy = prompt_round.copy1_player_id is None
            if is_first_copy:
                prompt_round.copy1_player_id = player.player_id
                prompt_round.phraseset_status = "waiting_copy1"
            elif prompt_round.copy2_player_id is None:
                prompt_round.copy2_player_id = player.player_id
            else:
                logger.warning(
                    f"Prompt round {prompt_round.round_id} already has two copy players; new submission still accepted")

            await self.activity_service.record_activity(
                activity_type="copy1_submitted" if is_first_copy else "copy2_submitted",
                prompt_round_id=prompt_round.round_id,
                player_id=player.player_id,
                metadata={
                    "copy_phrase": round_object.copy_phrase,
                },
            )

            if prompt_round.copy2_player_id is None:
                # Ensure prompt stays available for a second copy
                QueueService.add_prompt_round_to_queue(prompt_round.round_id)

        await self.db.flush()

        phraseset = None
        copy_player_id = player.player_id  # Store for later notification
        if prompt_round:
            phraseset = await self.create_phraseset_if_ready(prompt_round)
            if phraseset:
                prompt_round.phraseset_status = "active"
                await self.activity_service.attach_phraseset_id(
                    prompt_round.round_id, phraseset.phraseset_id
                )

        if prompt_round and is_first_copy:
            try:
                asyncio.create_task(
                    revalidate_ai_hints_background(prompt_round.round_id)
                )
            except Exception as e:
                logger.error(
                    "Failed to revalidate AI hints after first copy submission: %s", e, exc_info=True
                )

        await self.db.commit()

        # Send notification to prompt / other copy player about copy submission (after phraseset is created)
        if phraseset and prompt_round:
            try:
                from backend.services.qf.notification_service import NotificationService
                notification_service = NotificationService(self.db)
                await notification_service.notify_copy_submission(
                    phraseset=phraseset,
                    copy_player_id=copy_player_id,
                    prompt_round=prompt_round,
                )
            except Exception as e:
                logger.error(f"Failed to send copy notification: {e}", exc_info=True)

        await self.db.refresh(round_object)
        if prompt_round:
            await self.db.refresh(prompt_round)
        if phraseset:
            await self.db.refresh(phraseset)

        # Track quest progress for round completion
        from backend.services.qf.quest_service import QuestService
        quest_service = QuestService(self.db)
        try:
            await quest_service.increment_round_completion(player.player_id)
            await quest_service.check_milestone_copies(player.player_id)
            await quest_service.check_balanced_player(player.player_id)
        except Exception as e:
            logger.error(f"Failed to update quest progress for copy round: {e}", exc_info=True)

        # Invalidate dashboard cache to ensure fresh data
        from backend.utils.cache import dashboard_cache
        dashboard_cache.invalidate_player_data(player.player_id)

        logger.debug(f"Submitted phrase for copy round {round_id}: {phrase}")

        # Check eligibility for second copy
        second_copy_info = {
            "eligible_for_second_copy": False,
            "second_copy_cost": None,
            "prompt_round_id": None,
            "original_phrase": None,
        }

        if prompt_round and is_first_copy:
            # Calculate second copy cost (2x the normal cost)
            second_copy_cost = self.settings.copy_cost_normal * 2

            # Check if player has enough wallet for second copy
            # Need to refresh player to get updated wallet after this transaction
            await self.db.refresh(player)

            if player.wallet >= second_copy_cost:
                second_copy_info = {
                    "eligible_for_second_copy": True,
                    "second_copy_cost": second_copy_cost,
                    "prompt_round_id": prompt_round.round_id,
                    "original_phrase": round_object.original_phrase,
                }
                logger.debug(f"Player {player.player_id} is eligible for second copy with wallet {player.wallet}")

        return round_object, second_copy_info

    async def get_or_generate_hints(self, round_id: UUID, player: QFPlayer, transaction_service: TransactionService
                                    ) -> list[str]:
        """Fetch cached hints for a copy round or generate and persist new ones.

        Charges the player hint_cost coins only when generating new hints (not for cached results).
        Uses the AI service's locking mechanism to prevent duplicate generation.
        """
        round_object = await self.db.get(Round, round_id)
        if not round_object:
            raise RoundNotFoundError("Round not found")

        if round_object.round_type != "copy":
            raise ValueError("Hints are only available for copy rounds")

        if round_object.status != "active":
            raise RoundExpiredError("Hints are only available for active copy rounds")

        if not round_object.prompt_round_id:
            raise RoundNotFoundError("Associated prompt round missing")

        prompt_round = await self.db.get(Round, round_object.prompt_round_id)
        if not prompt_round:
            raise RoundNotFoundError("Associated prompt round missing")

        if not prompt_round.submitted_phrase:
            raise InvalidPhraseError("Original phrase not submitted yet; hints unavailable")

        from backend.models.qf.ai_phrase_cache import QFAIPhraseCache

        # Check if phrase cache exists (which provides hints)
        result = await self.db.execute(
            select(QFAIPhraseCache)
            .where(QFAIPhraseCache.prompt_round_id == prompt_round.round_id)
        )
        phrase_cache = result.scalar_one_or_none()

        if phrase_cache and phrase_cache.validated_phrases:
            # Return cached hints for free (reuse phrases from cache)
            hints = phrase_cache.validated_phrases[:3]  # Return up to 3 hints
            # Mark cache as used for hints if not already marked
            if not phrase_cache.used_for_hints:
                phrase_cache.used_for_hints = True
                await self.db.flush()
            return hints

        # Check player wallet before generating new hints/cache
        if player.wallet < self.settings.hint_cost:
            raise InsufficientBalanceError(f"Insufficient wallet balance: {player.wallet} < {self.settings.hint_cost}")

        # Generate hints using AI service (which includes proper locking)
        if not self.ai_service:
            raise AIServiceError("AI service is not configured; cannot generate hints")

        hints = await self.ai_service.get_hints(prompt_round, count=3)

        # Charge player after successful hint generation
        await transaction_service.create_transaction(
            player_id=player.player_id,
            amount=-self.settings.hint_cost,
            trans_type="hint_purchase",
            reference_id=round_id,
            auto_commit=True,
        )

        return hints

    async def abandon_round(self, round_id: UUID, player: QFPlayer, transaction_service: TransactionService
                            ) -> tuple[Round, int, int]:
        """Abandon an active prompt, copy, or vote round and process refund."""

        from backend.utils import lock_client

        lock_name = f"abandon_round:{round_id}"
        with lock_client.lock(
            lock_name, timeout=self.settings.round_lock_timeout_seconds
        ):
            result = await self.db.execute(
                select(Round).where(Round.round_id == round_id).with_for_update()
            )
            round_object = result.scalar_one_or_none()

            if not round_object or round_object.player_id != player.player_id:
                raise RoundNotFoundError("Round not found")

            if round_object.status != "active":
                raise ValueError("Round is not active")

            # Calculate refund and penalty (same for both round types)
            penalty_kept = self.settings.abandoned_penalty
            refund_amount = max(round_object.cost - penalty_kept, 0)

            round_object.status = "abandoned"
            round_object.expires_at = datetime.now(UTC)

            if player.active_round_id == round_id:
                player.active_round_id = None

            if round_object.round_type == "prompt":
                round_object.phraseset_status = "abandoned"
            elif round_object.round_type == "copy":
                if round_object.prompt_round_id:
                    QueueService.add_prompt_round_to_queue(round_object.prompt_round_id)

                    abandonment = PlayerAbandonedPrompt(
                        id=uuid.uuid4(),
                        player_id=player.player_id,
                        prompt_round_id=round_object.prompt_round_id,
                    )
                    self.db.add(abandonment)
            else:  # vote round
                # No additional queue updates required for vote rounds
                pass

            if refund_amount > 0:
                await transaction_service.create_transaction(
                    player.player_id,
                    refund_amount,
                    "refund",
                    round_object.round_id,
                    auto_commit=False,
                    skip_lock=True,
                )

            await self.db.flush()
            await self.db.commit()
            await self.db.refresh(round_object)

        from backend.utils.cache import dashboard_cache

        dashboard_cache.invalidate_player_data(player.player_id)

        logger.debug(
            f"Round {round_id} ({round_object.round_type}) abandoned by player {player.player_id}; "
            f"refund={refund_amount} penalty={penalty_kept}"
        )

        return round_object, refund_amount, penalty_kept

    async def flag_copy_round(self, round_id: UUID, player: QFPlayer, transaction_service: TransactionService
                              ) -> FlaggedPrompt:
        """Flag an active copy round as inappropriate and abandon it."""

        round_object = await self.db.get(Round, round_id)
        if not round_object or round_object.round_type != "copy" or round_object.player_id != player.player_id:
            raise RoundNotFoundError("Round not found")

        if round_object.status != "active":
            raise ValueError("Round is not active")

        if not round_object.prompt_round_id:
            raise ValueError("Copy round missing prompt reference")

        prompt_round = await self.db.get(Round, round_object.prompt_round_id)
        if not prompt_round:
            raise ValueError("Prompt round not found for flag")

        # Remove prompt from queue so no additional copy rounds are assigned
        queue_removed = QueueService.remove_prompt_round_from_queue(prompt_round.round_id)
        previous_status = prompt_round.phraseset_status
        prompt_round.phraseset_status = "flagged_pending"

        # Abandon the copy round immediately
        round_object.status = "abandoned"
        round_object.expires_at = datetime.now(UTC)

        # Clear player's active round
        if player.active_round_id == round_object.round_id:
            player.active_round_id = None

        # Partial refund following abandoned round rules
        refund_amount = max(round_object.cost - self.settings.abandoned_penalty, 0)
        penalty_kept = max(round_object.cost - refund_amount, 0)

        if refund_amount > 0:
            await transaction_service.create_transaction(
                player.player_id,
                refund_amount,
                "refund",
                round_object.round_id,
                auto_commit=False,
            )

        flag = FlaggedPrompt(
            flag_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_id=round_object.round_id,
            reporter_player_id=player.player_id,
            prompt_player_id=prompt_round.player_id,
            original_phrase=(round_object.original_phrase or "").upper(),
            prompt_text=prompt_round.prompt_text,
            previous_phraseset_status=previous_status,
            queue_removed=queue_removed,
            round_cost=round_object.cost,
            partial_refund_amount=refund_amount,
            penalty_kept=penalty_kept,
        )
        self.db.add(flag)

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(flag)

        # Invalidate dashboard cache for involved players
        from backend.utils.cache import dashboard_cache

        dashboard_cache.invalidate_player_data(player.player_id)
        if prompt_round.player_id:
            dashboard_cache.invalidate_player_data(prompt_round.player_id)

        logger.debug(f"{round_id=} flagged by {player.player_id}; {prompt_round.round_id=} marked pending review")

        return flag

    async def create_phraseset_if_ready(self, prompt_round: Round) -> Phraseset | None:
        """
        Create phraseset when two copies submitted.

        Validates that all required denormalized data is present before creating
        the phraseset to prevent data corruption.
        """
        logger.debug(f"Attempting to create phraseset for prompt {prompt_round.round_id}")

        copy_rounds = await PhrasesetCreationHelper.get_copy_rounds_for_prompt(self.db, prompt_round.round_id)
        
        is_valid, error = PhrasesetCreationHelper.validate_phraseset_data(prompt_round, copy_rounds)
        if not is_valid:
            logger.error(f"Cannot create phraseset for prompt {prompt_round.round_id}: {error}")
            return None

        initial_pool, system_contribution, second_copy_contribution = (
            PhrasesetCreationHelper.calculate_phraseset_pool(copy_rounds, self.settings))
        
        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=copy_rounds[0].round_id,
            copy_round_2_id=copy_rounds[1].round_id,
            # Denormalized fields - explicitly copy from source rounds
            prompt_text=prompt_round.prompt_text,
            original_phrase=prompt_round.submitted_phrase.upper(),
            copy_phrase_1=copy_rounds[0].copy_phrase.upper(),
            copy_phrase_2=copy_rounds[1].copy_phrase.upper(),
            status="open",
            vote_count=0,
            total_pool=initial_pool,
            vote_contributions=0,
            vote_payouts_paid=0,
            system_contribution=system_contribution,
            second_copy_contribution=second_copy_contribution,
        )

        self.db.add(phraseset)
        await self.db.flush()

        QueueService.add_phraseset_to_queue(phraseset.phraseset_id)

        return phraseset

    async def handle_timeout(self, round_id: UUID, transaction_service: TransactionService):
        """
        Handle timeout for abandoned round.

        - Prompt: Refund $95, keep $5 penalty, remove from queue
        - Copy: Refund $95, keep $5 penalty, return prompt to queue, track cooldown
        """
        round_object = await self.db.get(Round, round_id)
        if not round_object:
            return

        expires_at_aware = ensure_utc(round_object.expires_at)
        grace_cutoff = (
            expires_at_aware + timedelta(seconds=self.settings.grace_period_seconds) if expires_at_aware else None
        )

        # Respect grace period before cleanup
        if grace_cutoff and datetime.now(UTC) <= grace_cutoff:
            return

        # If round already resolved, ensure active flag cleared and stop
        if round_object.status != "active":
            player = await self.db.get(QFPlayer, round_object.player_id)
            if player and player.active_round_id == round_id:
                player.active_round_id = None
                await self.db.commit()
            return

        # Handle timeout based on round type using helper methods
        if round_object.round_type == "prompt":
            await RoundTimeoutHelper.handle_prompt_timeout(round_object, self.settings, transaction_service)

        elif round_object.round_type == "copy":
            await RoundTimeoutHelper.handle_copy_timeout(
                self.db, round_object, self.settings, transaction_service, QueueService)

        elif round_object.round_type == "vote":
            await RoundTimeoutHelper.handle_vote_timeout(round_object, self.settings, transaction_service)

        else:
            round_object.status = "expired"

        # Clear player's active round if still set
        player = await self.db.get(QFPlayer, round_object.player_id)
        if player and player.active_round_id == round_id:
            player.active_round_id = None

        await self.db.commit()

    async def get_available_prompts_count(self, player_id: UUID) -> int:
        """
        Get count of prompts available for copy rounds, excluding player's own prompts.

        Optimized version that uses a single efficient query instead of multiple
        complex subqueries to reduce database load.

        Excludes:
        - Player's own prompts
        - Prompts the player has already submitted copies for
        - Flagged prompts
        - Prompts the player abandoned in the last 24 hours (cooldown)
        """
        now = datetime.now(UTC)

        cached = self._available_prompts_cache.get(player_id)
        if cached:
            value, expires_at = cached
            if now < expires_at:
                return value

        cutoff_time = now - timedelta(hours=self.settings.abandoned_prompt_cooldown_hours)

        result = await self.db.execute(
            PromptQueryBuilder.build_available_prompts_count_query(),
            {"player_id_clean": str(player_id).replace('-', '').lower(), "cutoff_time": cutoff_time})

        available_count = result.scalar() or 0
        self._available_prompts_cache[player_id] = (
            available_count,
            now + timedelta(seconds=self.AVAILABLE_PROMPTS_CACHE_TTL_SECONDS),
        )

        return available_count

    def invalidate_available_prompts_cache(self, player_id: UUID | None = None) -> None:
        """Invalidate cached available prompt counts."""
        if player_id:
            self._available_prompts_cache.pop(player_id, None)
        else:
            self._available_prompts_cache.clear()

    async def ensure_prompt_queue_populated(self) -> bool:
        """
        Ensure the prompt queue has items. If empty, rehydrate it from the database.

        Returns:
            True if queue has items after running, False otherwise.
        """
        if QueueService.get_prompt_rounds_waiting() > 0:
            return True

        return await self._rehydrate_prompt_queue() > 0

    async def _rehydrate_prompt_queue(self) -> int:
        """
        Rebuild the prompt queue from submitted prompt rounds waiting on copies.

        Returns:
            Number of prompts enqueued.
        """
        from backend.utils import lock_client

        # Use a shared lock so only one worker rebuilds the queue at a time.
        logger.debug("Attempting to acquire rehydration lock")
        with lock_client.lock("rehydrate_prompt_queue", timeout=5):
            # Another worker might have already filled the queue while we were waiting.
            current_queue_length = QueueService.get_prompt_rounds_waiting()
            if current_queue_length > 0:
                logger.debug(f"Queue already populated by another worker ({current_queue_length=})")
                return 0

            logger.debug("Querying database for available prompts")
            query = PromptQueryBuilder.build_queue_rehydration_query()
            result = await self.db.execute(query)
            prompt_ids = list(result.scalars().all())

            if not prompt_ids:
                logger.warning("No available prompts found in database")
                return 0

            for prompt_round_id in prompt_ids:
                QueueService.add_prompt_round_to_queue(prompt_round_id)

            logger.debug(f"Successfully rehydrated prompt queue with {len(prompt_ids)} prompts from database")
            return len(prompt_ids)
