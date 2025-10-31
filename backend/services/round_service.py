"""Round service for managing prompt, copy, and vote rounds."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, or_, union, bindparam
from sqlalchemy.types import DateTime, String
from sqlalchemy.orm import aliased
from datetime import datetime, UTC, timedelta
from typing import Optional
from uuid import UUID
import uuid
import logging

from backend.models.player import Player
from backend.models.prompt import Prompt
from backend.models.round import Round
from backend.models.flagged_prompt import FlaggedPrompt
from backend.models.phraseset import Phraseset
from backend.models.player_abandoned_prompt import PlayerAbandonedPrompt
from backend.services.transaction_service import TransactionService
from backend.services.queue_service import QueueService
from backend.services.activity_service import ActivityService
from backend.config import get_settings
from backend.utils.exceptions import (
    InvalidPhraseError,
    DuplicatePhraseError,
    RoundNotFoundError,
    RoundExpiredError,
    NoPromptsAvailableError,
)

logger = logging.getLogger(__name__)


class RoundService:
    """Service for managing game rounds."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        if self.settings.use_phrase_validator_api:
            from backend.services.phrase_validation_client import get_phrase_validation_client
            self.phrase_validator = get_phrase_validation_client()
        else:
            from backend.services.phrase_validator import get_phrase_validator
            self.phrase_validator = get_phrase_validator()
        self.activity_service = ActivityService(db)

    async def start_prompt_round(self, player: Player, transaction_service: TransactionService) -> Optional[Round]:
        """
        Start a prompt round.

        - Deduct $100 immediately
        - Randomly assign prompt
        - Create round with 3-minute timer

        All operations are performed in a single atomic transaction within a distributed lock.
        """
        from backend.utils import lock_client

        # Acquire lock for the entire transaction
        lock_name = f"start_prompt_round:{player.player_id}"
        with lock_client.lock(lock_name, timeout=10):
            # Get random enabled prompt (inside lock to keep session consistent)
            # Prefer prompts the player has not yet seen to avoid repeats until
            # all prompts have been exhausted.
            copy_round_alias = aliased(Round)
            copy_prompt_round_alias = aliased(Round)
            vote_round_alias = aliased(Round)
            vote_prompt_round_alias = aliased(Round)
            phraseset_alias = aliased(Phraseset)

            prompt_round_seen = (
                select(Round.prompt_id)
                .where(Round.player_id == player.player_id)
                .where(Round.prompt_id.is_not(None))
            )

            copy_round_seen = (
                select(copy_prompt_round_alias.prompt_id)
                .select_from(copy_round_alias)
                .join(
                    copy_prompt_round_alias,
                    copy_round_alias.prompt_round_id == copy_prompt_round_alias.round_id,
                )
                .where(copy_round_alias.player_id == player.player_id)
                .where(copy_round_alias.round_type == "copy")
                .where(copy_prompt_round_alias.prompt_id.is_not(None))
            )

            vote_round_seen = (
                select(vote_prompt_round_alias.prompt_id)
                .select_from(vote_round_alias)
                .join(
                    phraseset_alias,
                    vote_round_alias.phraseset_id == phraseset_alias.phraseset_id,
                )
                .join(
                    vote_prompt_round_alias,
                    phraseset_alias.prompt_round_id == vote_prompt_round_alias.round_id,
                )
                .where(vote_round_alias.player_id == player.player_id)
                .where(vote_round_alias.round_type == "vote")
                .where(vote_prompt_round_alias.prompt_id.is_not(None))
            )

            seen_prompts_subquery = (
                union(
                    prompt_round_seen,
                    copy_round_seen,
                    vote_round_seen,
                ).subquery()
            )

            base_stmt = select(Prompt).where(Prompt.enabled == True)

            prompt_stmt = (
                base_stmt.outerjoin(
                    seen_prompts_subquery,
                    seen_prompts_subquery.c.prompt_id == Prompt.prompt_id,
                )
                .where(seen_prompts_subquery.c.prompt_id.is_(None))
            )

            result = await self.db.execute(prompt_stmt.order_by(func.random()).limit(1))
            prompt = result.scalar_one_or_none()

            if not prompt:
                logger.info(
                    "Player %s has seen all available prompts; no unseen prompts remaining",
                    player.player_id,
                )
                raise NoPromptsAvailableError("no_unseen_prompts_available")

            # Create transaction (deduct full amount immediately)
            # Use skip_lock=True since we already have the lock
            # Use auto_commit=False to defer commit until all operations complete
            await transaction_service.create_transaction(
                player.player_id,
                -self.settings.prompt_cost,
                "prompt_entry",
                auto_commit=False,
                skip_lock=True,
            )

            # Create round
            round_object = Round(
                round_id=uuid.uuid4(),
                player_id=player.player_id,
                round_type="prompt",
                status="active",
                cost=self.settings.prompt_cost,
                expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.prompt_round_seconds),
                # Prompt-specific fields
                prompt_id=prompt.prompt_id,
                prompt_text=prompt.text,
            )

            # Add round to session BEFORE setting foreign key reference
            self.db.add(round_object)
            await self.db.flush()

            # Set player's active round (after adding round to session)
            player.active_round_id = round_object.round_id

            # Increment usage count while prompt remains attached to this session for atomic commit.
            # SQLite stores UUID strings inconsistently (with/without hyphens) depending on how the data was seeded,
            # so match on both representations to keep deployments healthy.
            prompt_id_hex = prompt.prompt_id.hex
            prompt_id_str = str(prompt.prompt_id)
            result = await self.db.execute(
                text(
                    "UPDATE prompts "
                    "SET usage_count = usage_count + 1 "
                    "WHERE prompt_id IN (:prompt_id_hex, :prompt_id_str)"
                ),
                {"prompt_id_hex": prompt_id_hex, "prompt_id_str": prompt_id_str},
            )
            if result.rowcount == 0:
                raise RuntimeError("Failed to update prompt usage count")

            # Commit all changes atomically INSIDE the lock
            await self.db.commit()

            await self.db.refresh(round_object)

        # Invalidate dashboard cache to ensure fresh data
        from backend.utils.cache import dashboard_cache
        dashboard_cache.invalidate_player_data(player.player_id)

        logger.info(f"Started prompt round {round_object.round_id} for player {player.player_id}")
        return round_object

    async def submit_prompt_phrase(
            self,
            round_id: UUID,
            phrase: str,
            player: Player,
            transaction_service: TransactionService,
    ) -> Optional[Round]:
        """Submit word for prompt round."""
        # Get round
        round_object = await self.db.get(Round, round_id)
        if not round_object or round_object.player_id != player.player_id:
            raise RoundNotFoundError("Round not found")

        if round_object.status != "active":
            raise ValueError("Round is not active")

        # Check grace period
        # Make grace_cutoff timezone-aware if expires_at is naive (SQLite stores naive)
        expires_at_aware = round_object.expires_at.replace(
            tzinfo=UTC) if round_object.expires_at.tzinfo is None else round_object.expires_at
        grace_cutoff = expires_at_aware + timedelta(seconds=self.settings.grace_period_seconds)
        if datetime.now(UTC) > grace_cutoff:
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
            activity_type="prompt_created",
            prompt_round_id=round_object.round_id,
            player_id=player.player_id,
            metadata={
                "prompt_text": round_object.prompt_text,
                "phrase": round_object.submitted_phrase,
            },
        )

        await self.db.commit()
        await self.db.refresh(round_object)

        # Track quest progress for round completion
        from backend.services.quest_service import QuestService
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

        logger.info(f"Submitted phrase for prompt round {round_id}: {phrase}")
        return round_object

    async def start_copy_round(self, player: Player, transaction_service: TransactionService) -> Optional[Round]:
        """
        Start a copy round.

        - Get next prompt from queue (FIFO)
        - Check discount (>10 prompts waiting)
        - Deduct cost immediately
        - Prevent same player from getting abandoned prompt (24h)
        """
        # Ensure prompt queue is hydrated before we try to pop from it
        await self.ensure_prompt_queue_populated()

        # Retry logic: try up to 10 times to get a valid prompt
        max_attempts = 10
        prompt_round_id = None
        prompt_round = None

        for attempt in range(max_attempts):
            # Get next prompt from queue
            prompt_round_id = QueueService.get_next_prompt_round()
            if not prompt_round_id:
                await self.ensure_prompt_queue_populated()
                prompt_round_id = QueueService.get_next_prompt_round()
                if not prompt_round_id:
                    raise NoPromptsAvailableError("No prompts available")

            # Get prompt round
            prompt_round = await self.db.get(Round, prompt_round_id)
            if not prompt_round:
                logger.warning(f"Prompt round not found in DB: {prompt_round_id}")
                continue  # Try next prompt

            if prompt_round.phraseset_status in {"flagged_pending", "flagged_removed"}:
                logger.info(
                    "Prompt %s is flagged (status=%s), skipping for copy queue",
                    prompt_round_id,
                    prompt_round.phraseset_status,
                )
                continue

            # CRITICAL: Check if player is trying to copy their own prompt
            if prompt_round.player_id == player.player_id:
                # Put back in queue and try another
                QueueService.add_prompt_round_to_queue(prompt_round_id)
                logger.info(f"Player {player.player_id} got their own prompt, retrying...")
                continue

            # Prevent player from submitting multiple copies for the same prompt
            existing_copy_result = await self.db.execute(
                select(Round.round_id)
                .where(Round.round_type == "copy")
                .where(Round.prompt_round_id == prompt_round_id)
                .where(Round.player_id == player.player_id)
            )
            if existing_copy_result.scalar_one_or_none():
                QueueService.add_prompt_round_to_queue(prompt_round_id)
                logger.info(
                    f"Player {player.player_id} already submitted a copy for prompt {prompt_round_id}, retrying..."
                )
                continue

            # Check if player abandoned this prompt in last 24h
            cutoff = datetime.now(UTC) - timedelta(hours=24)
            result = await self.db.execute(
                select(PlayerAbandonedPrompt)
                .where(PlayerAbandonedPrompt.player_id == player.player_id)
                .where(PlayerAbandonedPrompt.prompt_round_id == prompt_round_id)
                .where(PlayerAbandonedPrompt.abandoned_at > cutoff)
            )
            if result.scalar_one_or_none():
                # Put back in queue and try another
                QueueService.add_prompt_round_to_queue(prompt_round_id)
                logger.info(f"Player {player.player_id} abandoned this prompt recently, retrying...")
                continue

            # Valid prompt found!
            break
        else:
            # Exhausted all attempts
            raise NoPromptsAvailableError("Could not find a valid prompt after multiple attempts")

        # Get current copy cost (with discount if applicable)
        copy_cost = QueueService.get_copy_cost()
        is_discounted = copy_cost == self.settings.copy_cost_discount
        system_contribution = self.settings.copy_cost_normal - copy_cost if is_discounted else 0

        # Acquire lock for the entire transaction
        from backend.utils import lock_client
        lock_name = f"start_copy_round:{player.player_id}"
        with lock_client.lock(lock_name, timeout=10):
            # Create transaction
            # Use skip_lock=True since we already have the lock
            # Use auto_commit=False to defer commit until all operations complete
            await transaction_service.create_transaction(
                player.player_id,
                -copy_cost,
                "copy_entry",
                auto_commit=False,
                skip_lock=True,
            )

            # Create round
            round_object = Round(
                round_id=uuid.uuid4(),
                player_id=player.player_id,
                round_type="copy",
                status="active",
                cost=copy_cost,
                expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.copy_round_seconds),
                # Copy-specific fields
                prompt_round_id=prompt_round_id,
                original_phrase=prompt_round.submitted_phrase,
                system_contribution=system_contribution,
            )

            # Add round to session BEFORE setting foreign key reference
            self.db.add(round_object)
            await self.db.flush()

            # Set player's active round (after adding round to session)
            player.active_round_id = round_object.round_id

            # Commit all changes atomically INSIDE the lock
            await self.db.commit()
            await self.db.refresh(round_object)

        # Invalidate dashboard cache to ensure fresh data
        from backend.utils.cache import dashboard_cache
        dashboard_cache.invalidate_player_data(player.player_id)

        logger.info(
            f"Started copy round {round_object.round_id} for player {player.player_id}, "
            f"cost=${copy_cost}, discount={is_discounted}"
        )
        return round_object

    async def submit_copy_phrase(
            self,
            round_id: UUID,
            phrase: str,
            player: Player,
            transaction_service: TransactionService,
    ) -> Optional[Round]:
        """Submit phrase for copy round."""
        # Get round
        round_object = await self.db.get(Round, round_id)
        if not round_object or round_object.player_id != player.player_id:
            raise RoundNotFoundError("Round not found")

        if round_object.status != "active":
            raise ValueError("Round is not active")

        # Check grace period
        # Make grace_cutoff timezone-aware if expires_at is naive (SQLite stores naive)
        expires_at_aware = round_object.expires_at.replace(
            tzinfo=UTC) if round_object.expires_at.tzinfo is None else round_object.expires_at
        grace_cutoff = expires_at_aware + timedelta(seconds=self.settings.grace_period_seconds)
        if datetime.now(UTC) > grace_cutoff:
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
        if prompt_round:
            phraseset = await self.create_phraseset_if_ready(prompt_round)
            if phraseset:
                prompt_round.phraseset_status = "active"
                await self.activity_service.attach_phraseset_id(
                    prompt_round.round_id, phraseset.phraseset_id
                )

        await self.db.commit()

        await self.db.refresh(round_object)
        if prompt_round:
            await self.db.refresh(prompt_round)
        if phraseset:
            await self.db.refresh(phraseset)

        # Track quest progress for round completion
        from backend.services.quest_service import QuestService
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

        logger.info(f"Submitted phrase for copy round {round_id}: {phrase}")
        return round_object

    async def abandon_round(
            self,
            round_id: UUID,
            player: Player,
            transaction_service: TransactionService,
    ) -> tuple[Round, int, int]:
        """Abandon an active prompt or copy round and process refund."""

        from backend.utils import lock_client

        lock_name = f"abandon_round:{round_id}"
        with lock_client.lock(lock_name, timeout=10):
            result = await self.db.execute(
                select(Round).where(Round.round_id == round_id).with_for_update()
            )
            round_object = result.scalar_one_or_none()

            if not round_object or round_object.player_id != player.player_id:
                raise RoundNotFoundError("Round not found")

            if round_object.status != "active":
                raise ValueError("Round is not active")

            if round_object.round_type not in {"prompt", "copy"}:
                raise ValueError("Only prompt or copy rounds can be abandoned")

            # Calculate refund and penalty (same for both round types)
            penalty_kept = self.settings.abandoned_penalty
            refund_amount = max(round_object.cost - penalty_kept, 0)

            round_object.status = "abandoned"
            round_object.expires_at = datetime.now(UTC)

            if player.active_round_id == round_id:
                player.active_round_id = None

            if round_object.round_type == "prompt":
                round_object.phraseset_status = "abandoned"
            else:  # copy round
                if round_object.prompt_round_id:
                    QueueService.add_prompt_round_to_queue(round_object.prompt_round_id)

                    abandonment = PlayerAbandonedPrompt(
                        id=uuid.uuid4(),
                        player_id=player.player_id,
                        prompt_round_id=round_object.prompt_round_id,
                    )
                    self.db.add(abandonment)

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

        logger.info(
            "Round %s (%s) abandoned by player %s; refund=%s penalty=%s",
            round_id,
            round_object.round_type,
            player.player_id,
            refund_amount,
            penalty_kept,
        )

        return round_object, refund_amount, penalty_kept

    async def flag_copy_round(
            self,
            round_id: UUID,
            player: Player,
            transaction_service: TransactionService,
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

        logger.info(
            "Copy round %s flagged by player %s; prompt %s marked pending review",
            round_id,
            player.player_id,
            prompt_round.round_id,
        )

        return flag

    async def create_phraseset_if_ready(self, prompt_round: Round) -> Phraseset | None:
        """
        Create phraseset when two copies submitted.

        Validates that all required denormalized data is present before creating
        the phraseset to prevent data corruption.
        """
        result = await self.db.execute(
            select(Round)
            .where(Round.prompt_round_id == prompt_round.round_id)
            .where(Round.round_type == "copy")
            .where(Round.status == "submitted")
            .order_by(Round.created_at.asc())
        )
        copy_rounds = list(result.scalars().all())

        if len(copy_rounds) < 2 or not prompt_round.submitted_phrase:
            return None

        copy1, copy2 = copy_rounds[0], copy_rounds[1]

        # Validate denormalized data exists before creating phraseset
        if not prompt_round.prompt_text:
            logger.error(f"Cannot create phraseset: prompt_round {prompt_round.round_id} missing prompt_text")
            return None

        if not prompt_round.submitted_phrase:
            logger.error(f"Cannot create phraseset: prompt_round {prompt_round.round_id} missing submitted_phrase")
            return None

        if not copy1.copy_phrase:
            logger.error(f"Cannot create phraseset: copy_round {copy1.round_id} missing copy_phrase")
            return None

        if not copy2.copy_phrase:
            logger.error(f"Cannot create phraseset: copy_round {copy2.round_id} missing copy_phrase")
            return None

        # Note: system contribution is implicitly included in the prize pool base, it is only tracked for transparency
        system_contribution = copy1.system_contribution + copy2.system_contribution
        initial_pool = self.settings.prize_pool_base

        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=copy1.round_id,
            copy_round_2_id=copy2.round_id,
            # Denormalized fields - explicitly copy from source rounds
            prompt_text=prompt_round.prompt_text,
            original_phrase=prompt_round.submitted_phrase.upper(),
            copy_phrase_1=copy1.copy_phrase.upper(),
            copy_phrase_2=copy2.copy_phrase.upper(),
            status="open",
            vote_count=0,
            total_pool=initial_pool,
            vote_contributions=0,
            vote_payouts_paid=0,
            system_contribution=system_contribution,
        )

        self.db.add(phraseset)
        await self.db.flush()

        QueueService.add_phraseset_to_queue(phraseset.phraseset_id)
        logger.info(f"Created phraseset {phraseset.phraseset_id} from prompt {prompt_round.round_id}")

        return phraseset

    async def handle_timeout(
            self,
            round_id: UUID,
            transaction_service: TransactionService,
    ):
        """
        Handle timeout for abandoned round.

        - Prompt: Refund $95, keep $5 penalty, remove from queue
        - Copy: Refund $95, keep $5 penalty, return prompt to queue, track cooldown
        """
        round_object = await self.db.get(Round, round_id)
        if not round_object:
            return

        expires_at = round_object.expires_at
        expires_at_aware = (
            expires_at.replace(tzinfo=UTC) if expires_at and expires_at.tzinfo is None else expires_at
        )
        grace_cutoff = (
            expires_at_aware + timedelta(seconds=self.settings.grace_period_seconds) if expires_at_aware else None
        )

        # Respect grace period before cleanup
        if grace_cutoff and datetime.now(UTC) <= grace_cutoff:
            return

        # If round already resolved, ensure active flag cleared and stop
        if round_object.status != "active":
            player = await self.db.get(Player, round_object.player_id)
            if player and player.active_round_id == round_id:
                player.active_round_id = None
                await self.db.commit()
            return

        # Mark as expired/abandoned
        if round_object.round_type == "prompt":
            round_object.status = "expired"
            round_object.phraseset_status = "abandoned"
            refund_amount = self.settings.prompt_cost - self.settings.abandoned_penalty

            # Create refund transaction
            await transaction_service.create_transaction(
                round_object.player_id,
                refund_amount,
                "refund",
                round_object.round_id,
            )

            logger.info(f"Prompt round {round_id} expired, refunded ${refund_amount}")

        elif round_object.round_type == "copy":
            round_object.status = "abandoned"
            refund_amount = round_object.cost - self.settings.abandoned_penalty

            # Create refund transaction
            await transaction_service.create_transaction(
                round_object.player_id,
                refund_amount,
                "refund",
                round_object.round_id,
            )

            # Return prompt to queue
            QueueService.add_prompt_round_to_queue(round_object.prompt_round_id)

            # Track abandonment for cooldown
            abandonment = PlayerAbandonedPrompt(
                id=uuid.uuid4(),
                player_id=round_object.player_id,
                prompt_round_id=round_object.prompt_round_id,
            )
            self.db.add(abandonment)

            logger.info(
                f"Copy round {round_id} abandoned, refunded ${refund_amount}, "
                f"returned prompt {round_object.prompt_round_id} to queue"
            )
        else:
            round_object.status = "expired"
            logger.info(f"Round {round_id} of type {round_object.round_type} expired")

        # Clear player's active round if still set
        player = await self.db.get(Player, round_object.player_id)
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
        # Use a single query with proper joins to count available prompts
        # This is much more efficient than the previous multiple-query approach
        cutoff_time = datetime.now(UTC) - timedelta(hours=self.settings.abandoned_prompt_cooldown_hours)

        query = text("""
                WITH player_prompt_rounds AS (
                    SELECT r.round_id
                    FROM rounds r
                    WHERE LOWER(REPLACE(CAST(r.player_id AS TEXT), '-', '')) = :player_id_clean
                    AND r.round_type = 'prompt'
                    AND r.status = 'submitted'
                ),
                player_copy_rounds AS (
                    SELECT r.prompt_round_id
                    FROM rounds r
                    WHERE LOWER(REPLACE(CAST(r.player_id AS TEXT), '-', '')) = :player_id_clean
                    AND r.round_type = 'copy'
                    AND r.status = 'submitted'
                ),
                player_abandoned_cooldown AS (
                    SELECT pap.prompt_round_id
                    FROM player_abandoned_prompts pap
                    WHERE LOWER(REPLACE(CAST(pap.player_id AS TEXT), '-', '')) = :player_id_clean
                    AND pap.abandoned_at > :cutoff_time
                ),
                all_available_prompts AS (
                    SELECT r.round_id
                    FROM rounds r
                    LEFT JOIN phrasesets p ON p.prompt_round_id = r.round_id
                    WHERE r.round_type = 'prompt'
                    AND r.status = 'submitted'
                    AND (r.phraseset_status IS NULL OR r.phraseset_status NOT IN ('flagged_pending','flagged_removed'))
                    AND p.phraseset_id IS NULL
                )
                SELECT COUNT(*) as available_count
                FROM all_available_prompts a
                WHERE a.round_id NOT IN (SELECT round_id FROM player_prompt_rounds)
                AND a.round_id NOT IN (SELECT prompt_round_id FROM player_copy_rounds WHERE prompt_round_id IS NOT NULL)
                AND a.round_id NOT IN (SELECT prompt_round_id FROM player_abandoned_cooldown WHERE prompt_round_id IS NOT NULL)
            """)
        query = query.bindparams(
            bindparam("player_id_clean", type_=String),
            bindparam("cutoff_time", type_=DateTime(timezone=True)),
        )

        result = await self.db.execute(
            query,
            {
                "player_id_clean": str(player_id).replace('-', '').lower(),
                "cutoff_time": cutoff_time,
            },
        )

        available_count = result.scalar() or 0

        logger.debug(f"Available prompts for player {player_id}: {available_count}")
        return available_count

    async def ensure_prompt_queue_populated(self) -> bool:
        """
        Ensure the prompt queue has items. If empty, rehydrate it from the database.

        Returns:
            True if queue has items after running, False otherwise.
        """
        if QueueService.get_prompt_rounds_waiting() > 0:
            return True

        rehydrated = await self._rehydrate_prompt_queue()
        return rehydrated > 0

    async def _rehydrate_prompt_queue(self) -> int:
        """
        Rebuild the prompt queue from submitted prompt rounds waiting on copies.

        Returns:
            Number of prompts enqueued.
        """
        from backend.utils import lock_client

        # Use a shared lock so only one worker rebuilds the queue at a time.
        with lock_client.lock("rehydrate_prompt_queue", timeout=5):
            # Another worker might have already filled the queue while we were waiting.
            if QueueService.get_prompt_rounds_waiting() > 0:
                return 0

            result = await self.db.execute(
                select(Round.round_id)
                .join(Phraseset, Phraseset.prompt_round_id == Round.round_id, isouter=True)
                .where(Round.round_type == "prompt")
                .where(Round.status == "submitted")
                .where(
                    or_(
                        Round.phraseset_status.is_(None),
                        Round.phraseset_status.notin_(["flagged_pending", "flagged_removed"]),
                    )
                )
                .where(Phraseset.phraseset_id.is_(None))  # Use proper NULL check
                .order_by(Round.created_at.asc())
            )
            prompt_ids = list(result.scalars().all())

            if not prompt_ids:
                return 0

            for prompt_round_id in prompt_ids:
                QueueService.add_prompt_round_to_queue(prompt_round_id)

            logger.info(f"Rehydrated prompt queue with {len(prompt_ids)} prompts from database")
            return len(prompt_ids)
