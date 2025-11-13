"""Vote service for managing voting rounds and finalization."""
import asyncio
import random
import time
import uuid
import logging
from datetime import datetime, UTC, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from backend.utils.exceptions import (
    NoPhrasesetsAvailableError,
    AlreadyVotedError,
    RoundExpiredError,
    InvalidPhraseError,
    SelfVotingError,
)
from backend.utils.datetime_helpers import ensure_utc

from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.vote import Vote
from backend.models.result_view import ResultView
from backend.services.transaction_service import TransactionService
from backend.services.scoring_service import ScoringService
from backend.services.helpers import upsert_result_view
from backend.services.phraseset_activity_service import ActivityService
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VoteService:
    """Service for managing voting."""

    _finalization_lock: asyncio.Lock | None = None
    _last_finalization_check: float = 0.0

    def __init__(self, db: AsyncSession):
        self.db = db
        self.activity_service = ActivityService(db)

    @classmethod
    def _get_finalization_lock(cls) -> asyncio.Lock:
        """Lazily create the lock used to throttle finalization checks."""

        if cls._finalization_lock is None:
            cls._finalization_lock = asyncio.Lock()
        return cls._finalization_lock

    async def _load_available_phrasesets_for_player(self, player_id: UUID) -> list[Phraseset]:
        """Load phrasesets the player can vote on (excludes contributors and already-voted)."""

        missing_relationships_clause = or_(
            Phraseset.prompt_round_id.is_(None),
            Phraseset.copy_round_1_id.is_(None),
            Phraseset.copy_round_2_id.is_(None),
        )

        # Log phrasesets with missing relationships so data issues remain visible in production
        missing_relationships = await self.db.execute(
            select(
                Phraseset.phraseset_id,
                Phraseset.prompt_round_id,
                Phraseset.copy_round_1_id,
                Phraseset.copy_round_2_id,
            )
            .where(Phraseset.status.in_(["open", "closing"]))
            .where(missing_relationships_clause)
        )
        for phraseset_id, prompt_round_id, copy_round_1_id, copy_round_2_id in missing_relationships.all():
            logger.warning(
                "Skipping phraseset "
                f"{phraseset_id} with missing relationships: "
                f"prompt_round={prompt_round_id is not None}, "
                f"copy_round_1={copy_round_1_id is not None}, "
                f"copy_round_2={copy_round_2_id is not None}"
            )

        contributor_exists = (
            select(1)
            .select_from(Round)
            .where(Round.player_id == player_id)
            .where(
                or_(
                    Round.round_id == Phraseset.prompt_round_id,
                    Round.round_id == Phraseset.copy_round_1_id,
                    Round.round_id == Phraseset.copy_round_2_id,
                )
            )
            .correlate(Phraseset)
            .exists()
        )

        already_voted_exists = (
            select(1)
            .select_from(Vote)
            .where(Vote.player_id == player_id)
            .where(Vote.phraseset_id == Phraseset.phraseset_id)
            .correlate(Phraseset)
            .exists()
        )

        result = await self.db.execute(
            select(Phraseset)
            .where(Phraseset.status.in_(["open", "closing"]))
            .where(~missing_relationships_clause)
            .where(~contributor_exists)
            .where(~already_voted_exists)
            .options(
                selectinload(Phraseset.prompt_round),
                selectinload(Phraseset.copy_round_1),
                selectinload(Phraseset.copy_round_2),
            )
        )
        return list(result.scalars().all())

    async def _ensure_recent_finalization(self) -> None:
        """Throttle expensive finalization checks to run at most once per interval."""

        interval = settings.vote_finalization_refresh_interval_seconds
        if interval <= 0:
            await self._check_and_finalize_active_phrasesets()
            return

        lock = self._get_finalization_lock()
        async with lock:
            now = time.monotonic()
            if now - self._last_finalization_check < interval:
                return
            self._last_finalization_check = now

        await self._check_and_finalize_active_phrasesets()

    async def _get_contributor_ids(self, phraseset: Phraseset) -> set[UUID]:
        """Load all contributor player IDs for a phraseset with a single query."""
        round_ids = [
            phraseset.prompt_round_id,
            phraseset.copy_round_1_id,
            phraseset.copy_round_2_id,
        ]
        round_ids = [round_id for round_id in round_ids if round_id is not None]
        if not round_ids:
            return set()

        result = await self.db.execute(
            select(Round.player_id).where(Round.round_id.in_(round_ids))
        )
        return {row[0] for row in result.all()}

    async def _create_result_view_for_player(
        self,
        _phraseset: Phraseset,
        phraseset_id: UUID,
        player_id: UUID,
        player_payout: int,
    ) -> tuple[ResultView, bool]:
        """Create a result view for the contributor, handling duplicates gracefully."""

        values = {
            "view_id": uuid.uuid4(),
            "phraseset_id": phraseset_id,
            "player_id": player_id,
            "payout_amount": player_payout,
            "result_viewed": False,
        }

        result_view, inserted = await upsert_result_view(
            self.db,
            phraseset_id=phraseset_id,
            player_id=player_id,
            values=values,
        )

        if inserted:
            logger.info(
                f"Player {player_id} viewed results for phraseset {phraseset_id} "
                f"(payout ${player_payout} was auto-distributed at finalization)"
            )

        return result_view, inserted

    async def get_available_phrasesets_for_player(self, player_id: UUID) -> Phraseset | None:
        """
        Get available phraseset for voting with priority:
        1. Phrasesets with >=5 votes (FIFO by fifth_vote_at)
        2. Phrasesets with 3-4 votes (FIFO by third_vote_at)
        3. Phrasesets with <3 votes (random)
        """
        available = await self._load_available_phrasesets_for_player(player_id)

        if not available:
            return None

        # Priority 1: >=5 votes (FIFO by fifth_vote_at)
        priority1 = [ws for ws in available if ws.vote_count >= 5 and ws.fifth_vote_at]
        if priority1:
            priority1.sort(key=lambda x: x.fifth_vote_at)
            return priority1[0]

        # Priority 2: 3-4 votes (FIFO by third_vote_at)
        priority2 = [ws for ws in available if 3 <= ws.vote_count < 5 and ws.third_vote_at]
        if priority2:
            priority2.sort(key=lambda x: x.third_vote_at)
            return priority2[0]

        # Priority 3: <3 votes (random)
        priority3 = [ws for ws in available if ws.vote_count < 3]
        if priority3:
            return random.choice(priority3)

        # Fallback: random from any available
        return random.choice(available)

    async def count_available_phrasesets_for_player(self, player_id: UUID) -> int:
        """Count how many phrasesets the player can vote on.

        First checks and finalizes any phrasesets that meet finalization criteria
        to ensure accurate availability counts.
        """
        await self._ensure_recent_finalization()

        # Then count available phrasesets for this player
        available = await self._load_available_phrasesets_for_player(player_id)
        return len(available)

    async def _check_and_finalize_active_phrasesets(self) -> None:
        """
        Check and finalize all active phrasesets that meet finalization criteria.

        This runs before counting available phrasesets to ensure accurate counts.
        """
        try:
            now = datetime.now(UTC)
            closing_cutoff = now - timedelta(minutes=settings.vote_closing_window_minutes)
            minimum_cutoff = now - timedelta(minutes=settings.vote_minimum_window_minutes)

            # Only load phrasesets that have met finalization prerequisites
            result = await self.db.execute(
                select(Phraseset)
                .where(Phraseset.status.in_(["open", "closing"]))
                .where(
                    or_(
                        Phraseset.vote_count >= settings.vote_max_votes,
                        and_(
                            Phraseset.vote_count >= settings.vote_closing_threshold,
                            or_(
                                Phraseset.fifth_vote_at.is_(None),
                                Phraseset.fifth_vote_at <= closing_cutoff,
                            ),
                        ),
                        and_(
                            Phraseset.vote_count >= settings.vote_minimum_threshold,
                            Phraseset.vote_count < settings.vote_closing_threshold,
                            or_(
                                Phraseset.third_vote_at.is_(None),
                                Phraseset.third_vote_at <= minimum_cutoff,
                            ),
                        ),
                    )
                )
                .order_by(Phraseset.created_at.asc())
            )
            active_phrasesets = list(result.scalars().all())

            if not active_phrasesets:
                return
                
            logger.info(f"Checking {len(active_phrasesets)} active phrasesets for finalization")
            
            # Import here to avoid circular imports
            from backend.services.transaction_service import TransactionService
            transaction_service = TransactionService(self.db)
            
            finalized_count = 0
            orphaned_count = 0
            for phraseset in active_phrasesets:
                await self._ensure_vote_threshold_timestamps(phraseset)
                try:
                    # Check if this phraseset should be finalized
                    # This will automatically finalize if conditions are met
                    await self.check_and_finalize(
                        phraseset,
                        transaction_service, 
                        auto_commit=True
                    )
                    
                    # Refresh to check if it was finalized
                    await self.db.refresh(phraseset)
                    if phraseset.status == "finalized":
                        finalized_count += 1
                        
                except ValueError as e:
                    # Handle orphaned phrasesets (missing round references)
                    if "Cannot calculate payouts: missing" in str(e):
                        orphaned_count += 1
                        logger.warning(
                            f"Marking orphaned phraseset {phraseset.phraseset_id} as closed due to missing relationships: {e}"
                        )
                        await self._handle_orphaned_phraseset(phraseset)
                        continue
                    else:
                        # Re-raise other ValueErrors
                        raise
                        
                except Exception as e:
                    logger.error(f"Error checking phraseset {phraseset.phraseset_id} for finalization: {e}",
                                 exc_info=True)
                    # Continue processing other phrasesets even if one fails
                    
            if finalized_count > 0:
                logger.info(f"Finalized {finalized_count} phrasesets during availability check")
            if orphaned_count > 0:
                logger.warning(f"Skipped {orphaned_count} orphaned phrasesets during availability check")
                
        except Exception as e:
            logger.error(f"Error during phraseset finalization check: {e}", exc_info=True)
            # Don't let finalization errors break the availability counting

    async def _handle_orphaned_phraseset(self, phraseset: Phraseset) -> None:
        """Mark a phraseset with missing round data as closed to avoid repeated processing."""
        phraseset.status = "closed"
        phraseset.closes_at = datetime.now(UTC)

        prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
        if prompt_round:
            prompt_round.phraseset_status = "closed"

        await self.activity_service.record_activity(
            activity_type="finalization_error",
            phraseset_id=phraseset.phraseset_id,
            metadata={
                "reason": "missing_round_reference",
            },
        )

        await self.db.commit()

    async def _ensure_vote_threshold_timestamps(self, phraseset: Phraseset) -> None:
        """Backfill missing vote threshold timestamps for legacy phrasesets."""

        updated = False

        if (
            phraseset.vote_count >= settings.vote_minimum_threshold
            and not phraseset.third_vote_at
        ):
            third_vote_at = await self._get_vote_timestamp(
                phraseset.phraseset_id, settings.vote_minimum_threshold
            )
            if third_vote_at:
                phraseset.third_vote_at = ensure_utc(third_vote_at)
                updated = True

        if (
            phraseset.vote_count >= settings.vote_closing_threshold
            and not phraseset.fifth_vote_at
        ):
            fifth_vote_at = await self._get_vote_timestamp(
                phraseset.phraseset_id, settings.vote_closing_threshold
            )
            if fifth_vote_at:
                phraseset.fifth_vote_at = ensure_utc(fifth_vote_at)
                # Ensure the phraseset is marked as closing when the 5th vote is reached
                if phraseset.status == "open":
                    phraseset.status = "closing"
                if not phraseset.closes_at:
                    phraseset.closes_at = ensure_utc(fifth_vote_at) + timedelta(
                        minutes=settings.vote_closing_window_minutes
                    )
                updated = True

        if updated:
            await self.db.flush()

    async def _get_vote_timestamp(self, phraseset_id: UUID, vote_rank: int) -> datetime | None:
        """Return the created_at timestamp for the nth vote on a phraseset."""

        result = await self.db.execute(
            select(Vote.created_at)
            .where(Vote.phraseset_id == phraseset_id)
            .order_by(Vote.created_at.asc())
            .offset(vote_rank - 1)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def start_vote_round(
        self,
        player: Player,
        transaction_service: TransactionService,
    ) -> tuple[Round, Phraseset]:
        """
        Start a vote round.

        - Get available phraseset (with priority)
        - Deduct $1 immediately
        - Create round with 60s timer
        - Return round and phraseset with randomized word order

        All operations are performed in a single atomic transaction.
        """
        # Get available phraseset (outside lock - read-only)
        phraseset = await self.get_available_phrasesets_for_player(player.player_id)
        if not phraseset:
            raise NoPhrasesetsAvailableError("No quips available for voting")

        # Acquire lock for the entire transaction
        from backend.utils import lock_client
        lock_name = f"start_vote_round:{player.player_id}"
        with lock_client.lock(lock_name, timeout=10):
            # Create transaction
            # Use skip_lock=True since we already have the lock
            # Use auto_commit=False to defer commit until all operations complete
            await transaction_service.create_transaction(
                player.player_id,
                -settings.vote_cost,
                "vote_entry",
                auto_commit=False,
                skip_lock=True,
            )

            # Create round
            round = Round(
                round_id=uuid.uuid4(),
                player_id=player.player_id,
                round_type="vote",
                status="active",
                cost=settings.vote_cost,
                expires_at=datetime.now(UTC) + timedelta(seconds=settings.vote_round_seconds),
                # Vote-specific fields
                phraseset_id=phraseset.phraseset_id,
            )

            # Add round to session BEFORE setting foreign key reference
            self.db.add(round)
            await self.db.flush()

            # Set player's active round (after adding round to session)
            player.active_round_id = round.round_id

            # Commit all changes atomically INSIDE the lock
            await self.db.commit()
            await self.db.refresh(round)

        # Invalidate dashboard cache to ensure fresh data
        from backend.utils.cache import dashboard_cache
        dashboard_cache.invalidate_player_data(player.player_id)

        logger.info(f"Started vote round {round.round_id} for phraseset {phraseset.phraseset_id}")
        return round, phraseset

    async def submit_system_vote(
        self,
        phraseset: Phraseset,
        player: Player,
        chosen_phrase: str,
        transaction_service: TransactionService,
    ) -> Vote:
        """
        Submit a vote from a system/AI player (no active round required).

        This method is used for AI backup votes and other programmatic voting.
        Unlike submit_vote(), this doesn't require an active round and skips
        the grace period check.

        All operations are performed in a single atomic transaction to ensure consistency.

        Args:
            phraseset: The phraseset being voted on
            player: The voting player (typically AI)
            chosen_phrase: The selected phrase
            transaction_service: Transaction service for payouts

        Returns:
            Created vote with immediate feedback

        Raises:
            ValueError: If phrase is not valid
            AlreadyVotedError: If player already voted on this phraseset
        """
        contributor_ids = await self._get_contributor_ids(phraseset)

        if player.player_id in contributor_ids:
            logger.error(
                f"Player {player.player_id} attempted system vote on their own phraseset {phraseset.phraseset_id}"
            )
            raise SelfVotingError("Cannot vote on phraseset you contributed to")

        # Normalize phrase
        phrase = chosen_phrase.strip().upper()

        # Check if phrase is one of the three
        valid_phrases = {
            phraseset.original_phrase,
            phraseset.copy_phrase_1,
            phraseset.copy_phrase_2,
        }
        if phrase not in valid_phrases:
            raise InvalidPhraseError(f"Phrase must be one of: {', '.join(sorted(valid_phrases))}")

        # Check if already voted
        existing = await self.db.execute(
            select(Vote)
            .where(Vote.phraseset_id == phraseset.phraseset_id)
            .where(Vote.player_id == player.player_id)
        )
        if existing.scalar_one_or_none():
            raise AlreadyVotedError("Already voted on this phraseset")

        # Determine if correct
        correct = phrase == phraseset.original_phrase
        payout = settings.vote_payout_correct if correct else 0

        # Charge vote cost up-front
        await transaction_service.create_transaction(
            player.player_id,
            -settings.vote_cost,
            "vote_entry",
            auto_commit=False,
        )

        # Create vote
        vote = Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=player.player_id,
            voted_phrase=phrase,
            correct=correct,
            payout=payout,
        )

        self.db.add(vote)
        await self.db.flush()

        # Give payout if correct (deferred commit)
        # Split payout: 70% of net to wallet, 30% to vault
        # Note: skip_lock=False (default) to acquire player lock for balance safety
        if correct:
            await transaction_service.create_split_payout(
                player_id=player.player_id,
                gross_amount=payout,
                cost=settings.vote_cost,
                trans_type="vote_payout",
                reference_id=vote.vote_id,
                auto_commit=False,  # Defer commit to end of this method
                skip_lock=False,  # Acquire lock for thread-safe balance updates
            )

        # Update phraseset vote count and prize pool
        phraseset.vote_count += 1
        # Add vote cost to prize pool
        phraseset.vote_contributions += settings.vote_cost
        phraseset.total_pool += settings.vote_cost
        # Deduct payout from prize pool if correct
        if correct:
            phraseset.vote_payouts_paid += payout
            phraseset.total_pool -= payout

        await self.activity_service.record_activity(
            activity_type="vote_submitted",
            phraseset_id=phraseset.phraseset_id,
            player_id=player.player_id,
            metadata={
                "voted_phrase": phrase,
                "correct": correct,
                "vote_count": phraseset.vote_count,
                "system_vote": True,
            },
        )

        # Update vote timeline (deferred commit)
        await self._update_vote_timeline(phraseset, auto_commit=False)

        # Check if should finalize (deferred commit)
        # Note: This may trigger _finalize_phraseset which also defers commits
        await self.check_and_finalize(phraseset, transaction_service, auto_commit=False)

        # Single atomic commit for all operations
        await self.db.commit()
        await self.db.refresh(vote)

        logger.info(
            f"System vote submitted: phraseset={phraseset.phraseset_id}, player={player.player_id}, "
            f"phrase={phrase}, correct={correct}, payout=${payout}"
        )
        return vote

    async def submit_vote(
        self,
        round: Round,
        phraseset: Phraseset,
        phrase: str,
        player: Player,
        transaction_service: TransactionService,
    ) -> Vote:
        """
        Submit vote.

        - Check grace period
        - Validate word is one of the three
        - Create vote with immediate feedback
        - Give $5 if correct
        - Update vote timeline
        - Check for finalization

        All operations are performed in a single atomic transaction to ensure consistency.
        """
        # Check grace period
        current_time = datetime.now(UTC)
        grace_cutoff = ensure_utc(round.expires_at) + timedelta(seconds=settings.grace_period_seconds)

        if current_time > grace_cutoff:
            raise RoundExpiredError("Round expired past grace period")

        # Safety check: Ensure player is not a contributor to this phraseset
        contributor_ids = await self._get_contributor_ids(phraseset)

        if player.player_id in contributor_ids:
            logger.error(
                f"Player {player.player_id} attempted to vote on their own phraseset {phraseset.phraseset_id}!"
            )
            raise ValueError("You cannot vote on a phraseset you contributed to")

        # Normalize phrase
        phrase = phrase.strip().upper()

        # Check if phrase is one of the three
        valid_phrases = {
            phraseset.original_phrase,
            phraseset.copy_phrase_1,
            phraseset.copy_phrase_2,
        }
        if phrase not in valid_phrases:
            raise ValueError(f"Phrase must be one of: {', '.join(valid_phrases)}")

        # Check if already voted (shouldn't happen with round, but double-check)
        existing = await self.db.execute(
            select(Vote)
            .where(Vote.phraseset_id == phraseset.phraseset_id)
            .where(Vote.player_id == player.player_id)
        )
        if existing.scalar_one_or_none():
            raise AlreadyVotedError("Already voted on this phraseset")

        # Determine if correct
        correct = phrase == phraseset.original_phrase
        payout = settings.vote_payout_correct if correct else 0

        # Create vote
        vote = Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=player.player_id,
            voted_phrase=phrase,
            correct=correct,
            payout=payout,
        )

        self.db.add(vote)
        await self.db.flush()

        # Give payout if correct (deferred commit)
        # Split payout: 70% of net to wallet, 30% to vault
        # Note: skip_lock=False (default) to acquire player lock for balance safety
        if correct:
            await transaction_service.create_split_payout(
                player_id=player.player_id,
                gross_amount=payout,
                cost=settings.vote_cost,
                trans_type="vote_payout",
                reference_id=vote.vote_id,
                auto_commit=False,  # Defer commit to end of this method
                skip_lock=False,  # Acquire lock for thread-safe balance updates
            )

        # Track consecutive incorrect votes for guests
        if player.is_guest:
            if correct:
                # Reset consecutive incorrect votes on correct vote
                player.consecutive_incorrect_votes = 0
            else:
                # Increment consecutive incorrect votes
                player.consecutive_incorrect_votes += 1

                # Lock out guest after configurable number of incorrect votes
                if player.consecutive_incorrect_votes >= settings.guest_vote_lockout_threshold:
                    lockout_duration = timedelta(hours=settings.guest_vote_lockout_hours)
                    player.vote_lockout_until = datetime.now(UTC) + lockout_duration
                    logger.warning(
                        "Guest player "
                        f"{player.player_id} locked out from voting for {settings.guest_vote_lockout_hours} hour(s) "
                        f"due to {player.consecutive_incorrect_votes} consecutive incorrect votes"
                    )

        # Update round
        round.status = "submitted"
        round.vote_submitted_at = datetime.now(UTC)

        # Clear player's active round
        player.active_round_id = None

        # Update phraseset vote count and prize pool
        phraseset.vote_count += 1
        # Add vote cost to prize pool
        phraseset.vote_contributions += settings.vote_cost
        phraseset.total_pool += settings.vote_cost
        # Deduct payout from prize pool if correct
        if correct:
            phraseset.vote_payouts_paid += payout
            phraseset.total_pool -= payout

        await self.activity_service.record_activity(
            activity_type="vote_submitted",
            phraseset_id=phraseset.phraseset_id,
            player_id=player.player_id,
            metadata={
                "voted_phrase": phrase,
                "correct": correct,
                "vote_count": phraseset.vote_count,
            },
        )

        # Update vote timeline (deferred commit)
        await self._update_vote_timeline(phraseset, auto_commit=False)

        # Check if should finalize (deferred commit)
        # Note: This may trigger _finalize_phraseset which also defers commits
        await self.check_and_finalize(phraseset, transaction_service, auto_commit=False)

        # Single atomic commit for all operations
        await self.db.commit()
        await self.db.refresh(vote)

        # Track quest progress for votes (runs after commit)
        from backend.services.quest_service import QuestService
        quest_service = QuestService(self.db)
        try:
            # Update vote streak quest
            await quest_service.check_and_update_vote_streak(player.player_id, correct)
            # Check milestone vote quest
            await quest_service.check_milestone_votes(player.player_id)
            # Check balanced player quest
            await quest_service.check_balanced_player(player.player_id)
        except Exception as e:
            logger.error(f"Failed to update quest progress for vote: {e}", exc_info=True)

        # Invalidate dashboard cache to ensure fresh data
        from backend.utils.cache import dashboard_cache
        dashboard_cache.invalidate_player_data(player.player_id)

        logger.info(
            f"Vote submitted: phraseset={phraseset.phraseset_id}, player={player.player_id}, "
            f"phrase={phrase}, correct={correct}, payout=${payout}"
        )
        return vote

    async def _update_vote_timeline(self, phraseset: Phraseset, auto_commit: bool = True) -> None:
        """Update vote timeline markers based on configured thresholds.

        Args:
            phraseset: The phraseset to update
            auto_commit: If True, commits the changes. If False, caller is responsible for commit.
        """
        prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
        if prompt_round and phraseset.vote_count >= 1 and prompt_round.phraseset_status not in {"closing", "finalized"}:
            prompt_round.phraseset_status = "voting"

        # Mark minimum vote threshold timestamp
        if phraseset.vote_count == settings.vote_minimum_threshold and not phraseset.third_vote_at:
            phraseset.third_vote_at = datetime.now(UTC)
            await self.activity_service.record_activity(
                activity_type="third_vote_reached",
                phraseset_id=phraseset.phraseset_id,
                metadata={"vote_count": phraseset.vote_count},
            )
            logger.info(
                f"Phraseset {phraseset.phraseset_id} reached {settings.vote_minimum_threshold} votes, "
                f"{settings.vote_minimum_window_minutes}min window starts"
            )

        # Mark closing threshold timestamp and change status to closing
        if phraseset.vote_count == settings.vote_closing_threshold and not phraseset.fifth_vote_at:
            phraseset.fifth_vote_at = datetime.now(UTC)
            phraseset.status = "closing"
            phraseset.closes_at = datetime.now(UTC) + timedelta(minutes=settings.vote_closing_window_minutes)
            if prompt_round:
                prompt_round.phraseset_status = "closing"
            await self.activity_service.record_activity(
                activity_type="fifth_vote_reached",
                phraseset_id=phraseset.phraseset_id,
                metadata={
                    "vote_count": phraseset.vote_count,
                    "closes_at": phraseset.closes_at.isoformat() if phraseset.closes_at else None,
                },
            )
            logger.info(
                f"Phraseset {phraseset.phraseset_id} reached {settings.vote_closing_threshold} votes, "
                f"{settings.vote_closing_window_minutes}min closing window"
            )

        if auto_commit:
            await self.db.commit()

    async def check_and_finalize(
        self,
        phraseset: Phraseset,
        transaction_service: TransactionService,
        auto_commit: bool = True,
    ) -> None:
        """
        Check if phraseset should be finalized based on configured thresholds.

        Conditions (configurable in settings):
        - vote_max_votes reached (default: 20)
        - OR vote_closing_threshold+ votes AND closing window elapsed
        - OR vote_minimum_threshold votes AND minimum window elapsed

        Args:
            phraseset: The phraseset to check
            transaction_service: Service for creating payout transactions
            auto_commit: If True, commits the changes. If False, caller is responsible for commit.
        """
        should_finalize = False
        current_time = datetime.now(UTC)

        # Max votes reached
        if phraseset.vote_count >= settings.vote_max_votes:
            should_finalize = True
            logger.info(f"Phraseset {phraseset.phraseset_id} reached max votes ({settings.vote_max_votes})")

        # Closing threshold+ votes and closing window elapsed
        elif phraseset.vote_count >= settings.vote_closing_threshold and phraseset.fifth_vote_at:
            elapsed = (current_time - ensure_utc(phraseset.fifth_vote_at)).total_seconds()
            if elapsed >= settings.vote_closing_window_minutes * 60:
                should_finalize = True
                logger.info(
                    f"{phraseset.phraseset_id=} 5th vote closing window expired "
                    f"({elapsed=} >= {settings.vote_closing_window_minutes * 60}s)"
                )

        # Minimum threshold votes and minimum window elapsed (no closing vote yet)
        elif phraseset.vote_count >= settings.vote_minimum_threshold and phraseset.third_vote_at:
            elapsed = (current_time - ensure_utc(phraseset.third_vote_at)).total_seconds()
            if elapsed >= settings.vote_minimum_window_minutes * 60:
                should_finalize = True
                logger.info(
                    f"{phraseset.phraseset_id=} 3rd vote minimum window expired "
                    f"({elapsed=} >= {settings.vote_minimum_window_minutes * 60}s)"
                )

        if should_finalize:
            await self._finalize_phraseset(phraseset, transaction_service, auto_commit=auto_commit)

    async def _finalize_phraseset(
        self,
        phraseset: Phraseset,
        transaction_service: TransactionService,
        auto_commit: bool = True,
    ) -> None:
        """
        Finalize phraseset.

        - Calculate payouts
        - Create prize transactions
        - Update status to finalized

        Args:
            phraseset: The phraseset to finalize
            transaction_service: Service for creating payout transactions
            auto_commit: If True, commits the changes. If False, caller is responsible for commit.
        """
        # Calculate payouts
        scoring_service = ScoringService(self.db)
        payouts = await scoring_service.calculate_payouts(phraseset)

        # Get round costs for split payout calculation - fetch all in one query
        round_ids = [
            phraseset.prompt_round_id,
            phraseset.copy_round_1_id,
            phraseset.copy_round_2_id,
        ]
        # Filter out None values
        valid_round_ids = [rid for rid in round_ids if rid is not None]

        # Fetch all rounds in a single query
        round_cost_map = {}
        if valid_round_ids:
            result = await self.db.execute(
                select(Round.round_id, Round.cost).where(Round.round_id.in_(valid_round_ids))
            )
            round_cost_map = {round_id: cost for round_id, cost in result.all()}

        # Map costs to roles
        round_costs = {
            "original": round_cost_map.get(phraseset.prompt_round_id, 0),
            "copy1": round_cost_map.get(phraseset.copy_round_1_id, 0),
            "copy2": round_cost_map.get(phraseset.copy_round_2_id, 0),
        }

        # Create prize transactions for each contributor
        # Split payout: 70% of net to wallet, 30% to vault
        for role in ["original", "copy1", "copy2"]:
            payout_info = payouts[role]
            if payout_info["player_id"] is not None and payout_info["payout"] > 0:
                # Verify player exists before creating transaction
                player_exists = await self.db.get(Player, payout_info["player_id"])
                if not player_exists:
                    logger.warning(
                        f"Skipping prize payout for {role}: player {payout_info['player_id']} not found. "
                        f"This suggests orphaned data in rounds table."
                    )
                    continue

                # Use split payout to handle wallet/vault distribution
                # Note: skip_lock=False (default) to acquire player lock for balance safety
                await transaction_service.create_split_payout(
                    player_id=payout_info["player_id"],
                    gross_amount=payout_info["payout"],
                    cost=round_costs.get(role, 0),
                    trans_type="prize_payout",
                    reference_id=phraseset.phraseset_id,
                    auto_commit=False,  # Defer commit to caller
                    skip_lock=False,  # Acquire lock for thread-safe balance updates
                )

        # Update phraseset status
        phraseset.status = "finalized"
        phraseset.finalized_at = datetime.now(UTC)

        prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
        if prompt_round:
            prompt_round.phraseset_status = "finalized"

        await self.activity_service.record_activity(
            activity_type="finalized",
            phraseset_id=phraseset.phraseset_id,
            metadata={
                "total_votes": phraseset.vote_count,
                "total_pool": phraseset.total_pool,
            },
        )

        if auto_commit:
            await self.db.commit()

        # Check quest progress for finalized phraseset
        # Note: Quest checks run after commit to avoid blocking the transaction
        from backend.services.quest_service import QuestService
        quest_service = QuestService(self.db)
        try:
            # Check deceptive copy and obvious original quests
            await quest_service.check_deceptive_copy(phraseset.phraseset_id)
            await quest_service.check_obvious_original(phraseset.phraseset_id)

            # Check if any player's phraseset reached 20 votes milestone
            if phraseset.vote_count >= 20:
                # Check for all contributors
                for player_id in [phraseset.original_player_id, phraseset.copy1_player_id, phraseset.copy2_player_id]:
                    if player_id:
                        await quest_service.check_milestone_phraseset_20votes(
                            player_id, phraseset.phraseset_id, phraseset.vote_count
                        )
        except Exception as e:
            logger.error(f"Failed to update quest progress for finalized phraseset: {e}", exc_info=True)

        try:
            await scoring_service.refresh_weekly_leaderboard()
        except Exception:  # pragma: no cover - defensive logging only
            logger.error("Failed to refresh weekly leaderboard after finalization", exc_info=True)

        logger.info(
            f"Finalized phraseset {phraseset.phraseset_id}: "
            f"original=${payouts['original']['payout']}, "
            f"copy1=${payouts['copy1']['payout']}, "
            f"copy2=${payouts['copy2']['payout']}"
        )

    async def get_phraseset_results(
        self,
        phraseset_id: UUID,
        player_id: UUID,
        transaction_service: TransactionService,
    ) -> dict:
        """
        Get phraseset results for a contributor.

        First view collects payout (idempotent).
        """
        phraseset = await self.db.get(Phraseset, phraseset_id)
        if not phraseset:
            raise ValueError("Phraseset not found")

        if phraseset.status != "finalized":
            raise ValueError("Phraseset not yet finalized")

        # Validate all contributor round IDs are present
        from backend.utils.phraseset_utils import validate_phraseset_contributor_rounds
        validate_phraseset_contributor_rounds(phraseset)

        # Load all contributor rounds in a single query
        round_ids = [
            phraseset.prompt_round_id,
            phraseset.copy_round_1_id,
            phraseset.copy_round_2_id,
        ]
        result = await self.db.execute(
            select(Round).where(Round.round_id.in_(round_ids))
        )
        rounds = {round_.round_id: round_ for round_ in result.scalars().all()}

        prompt_round = rounds.get(phraseset.prompt_round_id)
        copy1_round = rounds.get(phraseset.copy_round_1_id)
        copy2_round = rounds.get(phraseset.copy_round_2_id)

        # Validate that all required rounds exist
        if not prompt_round or not copy1_round or not copy2_round:
            missing = []
            if not prompt_round:
                missing.append(f"prompt({phraseset.prompt_round_id})")
            if not copy1_round:
                missing.append(f"copy1({phraseset.copy_round_1_id})")
            if not copy2_round:
                missing.append(f"copy2({phraseset.copy_round_2_id})")
            logger.error(
                f"Phraseset {phraseset.phraseset_id} has missing contributor rounds: {', '.join(missing)}. "
                f"Found {len(rounds)} of 3 expected rounds. This is a data integrity issue."
            )
            raise ValueError(f"Phraseset has missing contributor rounds: {', '.join(missing)}")

        contributor_map = {
            prompt_round.player_id: ("prompt", phraseset.original_phrase),
            copy1_round.player_id: ("copy", phraseset.copy_phrase_1),
            copy2_round.player_id: ("copy", phraseset.copy_phrase_2),
        }

        # Check if player is a contributor
        if player_id in contributor_map:
            role, phrase = contributor_map[player_id]
        else:
            # Check if player is a voter
            vote_result = await self.db.execute(
                select(Vote)
                .where(Vote.phraseset_id == phraseset_id)
                .where(Vote.player_id == player_id)
            )
            vote = vote_result.scalar_one_or_none()
            if not vote:
                raise ValueError("Not a contributor or voter for this phraseset")
            role = "vote"
            phrase = vote.voted_phrase

        scoring_service = ScoringService(self.db)
        payouts = await scoring_service.calculate_payouts(phraseset)

        # Get player payout
        if role == "vote":
            # For voters, payout is already stored in the vote record and has been paid
            player_payout = vote.payout
        else:
            # For contributors, calculate from payouts
            player_payout = 0
            for payout_info in payouts.values():
                if payout_info["player_id"] == player_id:
                    player_payout = payout_info["payout"]
                    break

        # Get or create result view
        result = await self.db.execute(
            select(ResultView)
            .where(ResultView.phraseset_id == phraseset_id)
            .where(ResultView.player_id == player_id)
        )
        result_view = result.scalar_one_or_none()
        already_viewed = bool(result_view and result_view.result_viewed)

        if not result_view:
            result_view, _ = await self._create_result_view_for_player(
                phraseset,
                phraseset_id,
                player_id,
                player_payout,
            )

        commit_needed = False
        now = datetime.now(UTC)

        if result_view.payout_amount != player_payout:
            result_view.payout_amount = player_payout
            commit_needed = True

        if not result_view.first_viewed_at:
            result_view.first_viewed_at = now
            commit_needed = True

        if not result_view.result_viewed:
            result_view.result_viewed = True
            commit_needed = True

        if not result_view.result_viewed_at:
            result_view.result_viewed_at = now
            commit_needed = True

        if commit_needed:
            await self.db.commit()

        # Get all votes for display
        votes_result = await self.db.execute(
            select(Vote)
            .where(Vote.phraseset_id == phraseset_id)
            .options(selectinload(Vote.player))
        )
        all_votes = list(votes_result.scalars().all())

        # Count votes per word
        vote_counts = {
            phraseset.original_phrase: 0,
            phraseset.copy_phrase_1: 0,
            phraseset.copy_phrase_2: 0,
        }
        voter_lists: dict[str, list[str]] = {
            phraseset.original_phrase: [],
            phraseset.copy_phrase_1: [],
            phraseset.copy_phrase_2: [],
        }
        for vote in all_votes:
            vote_counts[vote.voted_phrase] += 1
            username = vote.player.username if vote.player else "Unknown Player"
            voter_lists[vote.voted_phrase].append(username)

        # Calculate points based on configured multipliers
        correct_multiplier = settings.correct_vote_points
        incorrect_multiplier = settings.incorrect_vote_points

        # Calculate player points
        if role == "vote":
            # Voters don't earn points from the prize pool - they were paid when they voted
            points = 0
        else:
            # Contributors earn points based on correct/incorrect votes for their phrase
            if phrase == phraseset.original_phrase:
                points = vote_counts[phrase] * correct_multiplier
            else:
                points = vote_counts[phrase] * incorrect_multiplier

        # Build response
        votes_display = []
        total_points = 0
        total_votes = 0
        for w in [phraseset.original_phrase, phraseset.copy_phrase_1, phraseset.copy_phrase_2]:
            is_original = w == phraseset.original_phrase
            multiplier = correct_multiplier if is_original else incorrect_multiplier
            phrase_points = vote_counts[w] * multiplier
            total_votes += vote_counts[w]
            total_points += phrase_points
            votes_display.append({
                "phrase": w,
                "vote_count": vote_counts[w],
                "is_original": is_original,
                "voters": voter_lists[w],
            })

        correct_vote_count = vote_counts[phraseset.original_phrase]
        incorrect_vote_count = total_votes - correct_vote_count

        # Calculate vault skim amount (30% of net earnings if positive)
        if role == "prompt":
            round_cost = prompt_round.cost
        elif role == "copy":
            # Determine which copy round the player participated in
            round_cost = copy1_round.cost if copy1_round.player_id == player_id else copy2_round.cost
        else:  # role == "vote"
            round_cost = settings.vote_cost

        net_earnings = result_view.payout_amount - round_cost
        vault_skim_amount = int(net_earnings * 0.3) if net_earnings > 0 else 0

        results_payload = {
            "prompt_text": phraseset.prompt_text,
            "votes": votes_display,
            "your_phrase": phrase,
            "your_role": role,
            "your_points": points,
            "total_points": total_points,
            "your_payout": result_view.payout_amount,
            "vault_skim_amount": vault_skim_amount,
            "total_pool": phraseset.total_pool,
            "total_votes": total_votes,
            "already_collected": already_viewed,
            "finalized_at": phraseset.finalized_at,
            "correct_vote_count": correct_vote_count,
            "incorrect_vote_count": incorrect_vote_count,
            "correct_vote_points": correct_multiplier,
            "incorrect_vote_points": incorrect_multiplier,
            "prize_pool_base": settings.prize_pool_base,
            "vote_cost": settings.vote_cost,
            "vote_payout_correct": settings.vote_payout_correct,
            "system_contribution": phraseset.system_contribution,
            "second_copy_contribution": phraseset.second_copy_contribution,
        }

        if role == "copy":
            results_payload["original_phrase"] = phraseset.original_phrase

        return results_payload
