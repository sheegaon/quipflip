"""Vote service for managing voting rounds and finalization."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, UTC, timedelta
from backend.utils.exceptions import NoPhrasesetsAvailableError,  AlreadyVotedError, RoundExpiredError
from backend.utils.datetime_helpers import ensure_utc
from uuid import UUID
import uuid
import random
import logging

from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.vote import Vote
from backend.models.result_view import ResultView
from backend.services.transaction_service import TransactionService
from backend.services.scoring_service import ScoringService
from backend.services.activity_service import ActivityService
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VoteService:
    """Service for managing voting."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.activity_service = ActivityService(db)

    async def _load_available_phrasesets_for_player(self, player_id: UUID) -> list[Phraseset]:
        """Load phrasesets the player can vote on (excludes contributors and already-voted)."""
        result = await self.db.execute(
            select(Phraseset)
            .where(Phraseset.status.in_(["open", "closing"]))
            .options(
                selectinload(Phraseset.prompt_round),
                selectinload(Phraseset.copy_round_1),
                selectinload(Phraseset.copy_round_2),
            )
        )
        all_phrasesets = list(result.scalars().all())
        if not all_phrasesets:
            return []

        # Filter out phrasesets where player was a contributor
        candidate_phrasesets = []
        for ps in all_phrasesets:
            # Skip phrasesets with missing relationships (data integrity issue)
            if not ps.prompt_round or not ps.copy_round_1 or not ps.copy_round_2:
                logger.warning(
                    f"Skipping phraseset {ps.phraseset_id} with missing relationships: "
                    f"prompt_round={ps.prompt_round is not None}, "
                    f"copy_round_1={ps.copy_round_1 is not None}, "
                    f"copy_round_2={ps.copy_round_2 is not None}"
                )
                continue

            # Get contributor player IDs
            contributor_ids = {
                ps.prompt_round.player_id,
                ps.copy_round_1.player_id,
                ps.copy_round_2.player_id,
            }

            # Skip if player was a contributor
            if player_id in contributor_ids:
                logger.debug(f"Filtering out phraseset {ps.phraseset_id} - player {player_id} was a contributor")
                continue

            candidate_phrasesets.append(ps)
        candidate_ids = [ws.phraseset_id for ws in candidate_phrasesets]

        if not candidate_phrasesets:
            return []

        # Filter out phrasesets where player already voted
        voted_ids: set[UUID] = set()
        if candidate_ids:
            vote_result = await self.db.execute(
                select(Vote.phraseset_id)
                .where(Vote.player_id == player_id)
                .where(Vote.phraseset_id.in_(candidate_ids))
            )
            voted_ids = {row[0] for row in vote_result.all()}

        available = [ws for ws in candidate_phrasesets if ws.phraseset_id not in voted_ids]
        return available

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
        # First, check and finalize any active phrasesets that meet finalization criteria
        # This ensures we get accurate counts after any eligible phrasesets are finalized
        await self._check_and_finalize_active_phrasesets()
        
        # Then count available phrasesets for this player
        available = await self._load_available_phrasesets_for_player(player_id)
        return len(available)

    async def _check_and_finalize_active_phrasesets(self) -> None:
        """
        Check and finalize all active phrasesets that meet finalization criteria.
        
        This runs before counting available phrasesets to ensure accurate counts.
        """
        try:
            # Get all active phrasesets that could potentially be finalized
            result = await self.db.execute(
                select(Phraseset)
                .where(Phraseset.status.in_(["open", "closing"]))
                .order_by(Phraseset.created_at.asc())  # Process oldest first
            )
            active_phrasesets = list(result.scalars().all())
            
            if not active_phrasesets:
                return
                
            logger.debug(f"Checking {len(active_phrasesets)} active phrasesets for finalization")
            
            # Import here to avoid circular imports
            from backend.services.transaction_service import TransactionService
            transaction_service = TransactionService(self.db)
            
            finalized_count = 0
            orphaned_count = 0
            for phraseset in active_phrasesets:
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
                        logger.warning(f"Skipping orphaned phraseset {phraseset.phraseset_id}: {e}")
                        # Optionally mark phraseset as finalized with zero payouts to prevent future processing
                        # For now, just skip and let manual cleanup handle it
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
        # Normalize phrase
        phrase = chosen_phrase.strip().upper()

        # Check if phrase is one of the three
        valid_phrases = {
            phraseset.original_phrase,
            phraseset.copy_phrase_1,
            phraseset.copy_phrase_2,
        }
        if phrase not in valid_phrases:
            raise ValueError(f"Phrase must be one of: {', '.join(valid_phrases)}")

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
        if correct:
            await transaction_service.create_transaction(
                player.player_id,
                payout,
                "vote_payout",
                vote.vote_id,
                auto_commit=False,  # Defer commit to end of this method
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
        # Load the relationships to check contributor IDs
        from sqlalchemy import select as sql_select
        from sqlalchemy.orm import selectinload

        # Refresh phraseset with relationships
        result = await self.db.execute(
            sql_select(Phraseset)
            .where(Phraseset.phraseset_id == phraseset.phraseset_id)
            .options(
                selectinload(Phraseset.prompt_round),
                selectinload(Phraseset.copy_round_1),
                selectinload(Phraseset.copy_round_2),
            )
        )
        phraseset_with_relations = result.scalar_one()

        contributor_ids = {
            phraseset_with_relations.prompt_round.player_id if phraseset_with_relations.prompt_round else None,
            phraseset_with_relations.copy_round_1.player_id if phraseset_with_relations.copy_round_1 else None,
            phraseset_with_relations.copy_round_2.player_id if phraseset_with_relations.copy_round_2 else None,
        } - {None}  # Remove None values

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
        if correct:
            await transaction_service.create_transaction(
                player.player_id,
                payout,
                "vote_payout",
                vote.vote_id,
                auto_commit=False,  # Defer commit to end of this method
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
                f"{settings.vote_minimum_window_seconds}s window starts"
            )

        # Mark closing threshold timestamp and change status to closing
        if phraseset.vote_count == settings.vote_closing_threshold and not phraseset.fifth_vote_at:
            phraseset.fifth_vote_at = datetime.now(UTC)
            phraseset.status = "closing"
            phraseset.closes_at = datetime.now(UTC) + timedelta(seconds=settings.vote_closing_window_seconds)
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
                f"{settings.vote_closing_window_seconds}sec closing window"
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
            if elapsed >= settings.vote_closing_window_seconds:
                should_finalize = True
                logger.info(
                    f"{phraseset.phraseset_id=} 5th vote closing window expired "
                    f"({elapsed=} >= {settings.vote_closing_window_seconds}s)"
                )

        # Minimum threshold votes and minimum window elapsed (no closing vote yet)
        elif phraseset.vote_count >= settings.vote_minimum_threshold and phraseset.third_vote_at:
            elapsed = (current_time - ensure_utc(phraseset.third_vote_at)).total_seconds()
            if elapsed >= settings.vote_minimum_window_seconds:
                should_finalize = True
                logger.info(
                    f"{phraseset.phraseset_id=} 3rd vote minimum window expired "
                    f"({elapsed=} >= {settings.vote_minimum_window_seconds}s)"
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

        # Create prize transactions for each contributor
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

                await transaction_service.create_transaction(
                    payout_info["player_id"],
                    payout_info["payout"],
                    "prize_payout",
                    phraseset.phraseset_id,
                    auto_commit=False,  # Defer commit to caller
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

        # Check if player was a contributor
        prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
        copy1_round = await self.db.get(Round, phraseset.copy_round_1_id)
        copy2_round = await self.db.get(Round, phraseset.copy_round_2_id)

        # Validate that all required rounds exist
        if not prompt_round:
            raise ValueError("Prompt round not found for this phraseset")
        if not copy1_round:
            raise ValueError("Copy round 1 not found for this phraseset")
        if not copy2_round:
            raise ValueError("Copy round 2 not found for this phraseset")

        contributor_map = {
            prompt_round.player_id: ("prompt", phraseset.original_phrase),
            copy1_round.player_id: ("copy", phraseset.copy_phrase_1),
            copy2_round.player_id: ("copy", phraseset.copy_phrase_2),
        }

        if player_id not in contributor_map:
            raise ValueError("Not a contributor to this phraseset")

        role, phrase = contributor_map[player_id]

        # Get or create result view
        result = await self.db.execute(
            select(ResultView)
            .where(ResultView.phraseset_id == phraseset_id)
            .where(ResultView.player_id == player_id)
        )
        result_view = result.scalar_one_or_none()

        # Calculate payouts if not yet done
        if not result_view:
            scoring_service = ScoringService(self.db)
            payouts = await scoring_service.calculate_payouts(phraseset)

            # Find player's payout
            player_payout = 0
            for payout_info in payouts.values():
                if payout_info["player_id"] == player_id:
                    player_payout = payout_info["payout"]
                    break

            # Create result view and mark as viewed since player is viewing results now
            result_view = ResultView(
                view_id=uuid.uuid4(),
                phraseset_id=phraseset_id,
                player_id=player_id,
                payout_amount=player_payout,
                result_viewed=True,  # Mark as viewed since player is viewing results now
                first_viewed_at=datetime.now(UTC),
                result_viewed_at=datetime.now(UTC),  # Set viewed timestamp
            )
            self.db.add(result_view)
            await self.db.commit()

            logger.info(f"Player {player_id} viewed results for phraseset {phraseset_id} (payout ${player_payout} was auto-distributed at finalization)")
        else:
            updated = False
            # Mark as viewed if not already viewed
            if not result_view.result_viewed:
                result_view.result_viewed = True
                result_view.result_viewed_at = datetime.now(UTC)
                updated = True
            if not result_view.first_viewed_at:
                result_view.first_viewed_at = datetime.now(UTC)
                updated = True
            if updated:
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

        # Calculate points
        points = 0
        if phrase == phraseset.original_phrase:
            points = vote_counts[phrase] * 1
        else:
            points = vote_counts[phrase] * 2

        # Build response
        votes_display = []
        total_points = 0
        for w in [phraseset.original_phrase, phraseset.copy_phrase_1, phraseset.copy_phrase_2]:
            is_original = w == phraseset.original_phrase
            phrase_points = vote_counts[w] * (1 if is_original else 2)
            total_points += phrase_points
            votes_display.append({
                "phrase": w,
                "vote_count": vote_counts[w],
                "is_original": is_original,
                "voters": voter_lists[w],
            })

        return {
            "prompt_text": phraseset.prompt_text,
            "votes": votes_display,
            "your_phrase": phrase,
            "your_role": role,
            "original_phrase": phraseset.original_phrase,
            "your_points": points,
            "total_points": total_points,
            "your_payout": result_view.payout_amount,
            "total_pool": phraseset.total_pool,
            "total_votes": phraseset.vote_count,
            "already_collected": result_view.result_viewed,  # Add the missing field
            "finalized_at": phraseset.finalized_at,
        }
