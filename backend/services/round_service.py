"""Round service for managing prompt, copy, and vote rounds."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, UTC, timedelta
from typing import Optional
from uuid import UUID
import uuid
import logging

from backend.models.player import Player
from backend.models.prompt import Prompt
from backend.models.round import Round
from backend.models.phraseset import PhraseSet
from backend.models.player_abandoned_prompt import PlayerAbandonedPrompt
from backend.services.transaction_service import TransactionService
from backend.services.queue_service import QueueService
from backend.services.phrase_validator import get_phrase_validator
from backend.services.activity_service import ActivityService
from backend.config import get_settings
from backend.utils.exceptions import InvalidPhraseError, DuplicatePhraseError, RoundNotFoundError, RoundExpiredError

logger = logging.getLogger(__name__)
settings = get_settings()


class RoundService:
    """Service for managing game rounds."""

    def __init__(self, db: AsyncSession):
        self.db = db
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
            seen_prompts_subquery = (
                select(Round.prompt_id)
                .where(Round.player_id == player.player_id)
                .where(Round.round_type == "prompt")
                .where(Round.prompt_id.is_not(None))
                .distinct()
            )

            base_stmt = select(Prompt).where(Prompt.enabled == True)

            # Try to get an unseen prompt first
            prompt_stmt = base_stmt.where(Prompt.prompt_id.not_in(seen_prompts_subquery))
            result = await self.db.execute(prompt_stmt.order_by(func.random()).limit(1))
            prompt = result.scalar_one_or_none()

            # If the player has seen every prompt, allow repeats.
            if not prompt:
                result = await self.db.execute(base_stmt.order_by(func.random()).limit(1))
                prompt = result.scalar_one_or_none()

            if not prompt:
                raise ValueError("No prompts available in library")

            # Create transaction (deduct full amount immediately)
            # Use skip_lock=True since we already have the lock
            # Use auto_commit=False to defer commit until all operations complete
            await transaction_service.create_transaction(
                player.player_id,
                -settings.prompt_cost,
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
                cost=settings.prompt_cost,
                expires_at=datetime.now(UTC) + timedelta(seconds=settings.prompt_round_seconds),
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
        grace_cutoff = expires_at_aware + timedelta(seconds=settings.grace_period_seconds)
        if datetime.now(UTC) > grace_cutoff:
            raise RoundExpiredError("Round expired past grace period")

        # Validate word against prompt text
        is_valid, error = self.phrase_validator.validate_prompt_phrase(
            phrase,
            round_object.prompt_text,
        )
        if not is_valid:
            raise InvalidPhraseError(error)

        # Update round
        round_object.submitted_phrase = phrase.strip().upper()
        round_object.status = "submitted"
        round_object.phraseset_status = "waiting_copies"

        # Clear player's active round
        player.active_round_id = None

        # Add to queue
        QueueService.add_prompt_to_queue(round_object.round_id)

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
        # Retry logic: try up to 10 times to get a valid prompt
        max_attempts = 10
        prompt_round_id = None
        prompt_round = None

        for attempt in range(max_attempts):
            # Get next prompt from queue
            prompt_round_id = QueueService.get_next_prompt()
            if not prompt_round_id:
                raise ValueError("No prompts available")

            # Get prompt round
            prompt_round = await self.db.get(Round, prompt_round_id)
            if not prompt_round:
                logger.warning(f"Prompt round not found in DB: {prompt_round_id}")
                continue  # Try next prompt

            # CRITICAL: Check if player is trying to copy their own prompt
            if prompt_round.player_id == player.player_id:
                # Put back in queue and try another
                QueueService.add_prompt_to_queue(prompt_round_id)
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
                QueueService.add_prompt_to_queue(prompt_round_id)
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
                QueueService.add_prompt_to_queue(prompt_round_id)
                logger.info(f"Player {player.player_id} abandoned this prompt recently, retrying...")
                continue

            # Valid prompt found!
            break
        else:
            # Exhausted all attempts
            raise ValueError("Could not find a valid prompt after multiple attempts")

        # Get current copy cost (with discount if applicable)
        copy_cost = QueueService.get_copy_cost()
        is_discounted = copy_cost == settings.copy_cost_discount
        system_contribution = settings.copy_cost_normal - copy_cost if is_discounted else 0

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
                expires_at=datetime.now(UTC) + timedelta(seconds=settings.copy_round_seconds),
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
        grace_cutoff = expires_at_aware + timedelta(seconds=settings.grace_period_seconds)
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
        is_valid, error = self.phrase_validator.validate_copy(
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
                    "Prompt round %s already has two copy players; new submission still accepted",
                    prompt_round.round_id,
                )

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
                QueueService.add_prompt_to_queue(prompt_round.round_id)

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

        logger.info(f"Submitted phrase for copy round {round_id}: {phrase}")
        return round_object

    async def create_phraseset_if_ready(self, prompt_round: Round) -> PhraseSet | None:
        """Create phraseset when two copies submitted."""
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

        total_pool = settings.phraseset_prize_pool
        system_contribution = copy1.system_contribution + copy2.system_contribution

        phraseset = PhraseSet(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=copy1.round_id,
            copy_round_2_id=copy2.round_id,
            prompt_text=prompt_round.prompt_text,
            original_phrase=prompt_round.submitted_phrase,
            copy_phrase_1=copy1.copy_phrase,
            copy_phrase_2=copy2.copy_phrase,
            status="open",
            vote_count=0,
            total_pool=total_pool,
            system_contribution=system_contribution,
        )

        self.db.add(phraseset)
        await self.db.flush()

        QueueService.add_wordset_to_queue(phraseset.phraseset_id)
        logger.info(
            "Created phraseset %s from prompt %s",
            phraseset.phraseset_id,
            prompt_round.round_id,
        )

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
            expires_at_aware + timedelta(seconds=settings.grace_period_seconds) if expires_at_aware else None
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
            refund_amount = settings.prompt_cost - settings.abandoned_penalty

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
            refund_amount = round_object.cost - settings.abandoned_penalty

            # Create refund transaction
            await transaction_service.create_transaction(
                round_object.player_id,
                refund_amount,
                "refund",
                round_object.round_id,
            )

            # Return prompt to queue
            QueueService.add_prompt_to_queue(round_object.prompt_round_id)

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

        This queries the database for prompts waiting for copies, which is more reliable
        than relying on the queue (which may be empty after a restart).
        """
        from backend.utils import queue_client

        # Count ALL submitted prompt rounds waiting for copies (not yet in a phraseset)
        result = await self.db.execute(
            select(func.count(Round.round_id))
            .join(PhraseSet, PhraseSet.prompt_round_id == Round.round_id, isouter=True)
            .where(Round.round_type == "prompt")
            .where(Round.status == "submitted")
            .where(PhraseSet.phraseset_id == None)  # Exclude prompts that already have phrasesets
        )
        total_count = result.scalar() or 0

        if total_count == 0:
            return 0

        # Count submitted prompt rounds that belong to this player AND don't have phrasesets yet
        result = await self.db.execute(
            select(func.count(Round.round_id))
            .join(PhraseSet, PhraseSet.prompt_round_id == Round.round_id, isouter=True)
            .where(Round.player_id == player_id)
            .where(Round.round_type == "prompt")
            .where(Round.status == "submitted")
            .where(PhraseSet.phraseset_id == None)
        )
        player_prompts_count = result.scalar() or 0

        # Count prompts this player already copied that are still waiting for a second copy
        result = await self.db.execute(
            select(func.count(Round.round_id))
            .join(
                PhraseSet,
                PhraseSet.prompt_round_id == Round.prompt_round_id,
                isouter=True,
            )
            .where(Round.round_type == "copy")
            .where(Round.player_id == player_id)
            .where(Round.status == "submitted")
            .where(PhraseSet.phraseset_id == None)
        )
        already_copied_waiting = result.scalar() or 0

        # Subtract player's own prompts and any prompts they've already copied
        available_count = max(0, total_count - player_prompts_count - already_copied_waiting)

        logger.debug(
            f"Available prompts for player {player_id}: {available_count} "
            f"(total: {total_count}, player's own: {player_prompts_count}, already copied: {already_copied_waiting})"
        )

        return available_count
