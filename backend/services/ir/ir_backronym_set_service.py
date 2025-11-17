"""IR Backronym Set Service - Set lifecycle management for Initial Reaction."""

import logging
from datetime import datetime, UTC, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from backend.config import get_settings
from backend.models.ir.ir_backronym_set import IRBackronymSet
from backend.models.ir.ir_backronym_entry import IRBackronymEntry
from backend.models.ir.ir_backronym_vote import IRBackronymVote
from backend.models.ir.ir_backronym_observer_guard import IRBackronymObserverGuard
from backend.models.ir.ir_player import IRPlayer
from backend.models.ir.enums import IRSetStatus, IRMode
from backend.services.ir.ir_word_service import IRWordService, IRWordError
from backend.services.ir.ir_queue_service import IRQueueService

logger = logging.getLogger(__name__)


class IRBackronymSetError(RuntimeError):
    """Raised when backronym set service fails."""


class IRBackronymSetService:
    """Service for managing backronym sets and their lifecycle."""

    def __init__(self, db: AsyncSession):
        """Initialize IR backronym set service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
        self.word_service = IRWordService(db)
        self.queue_service = IRQueueService(db)

    async def create_set(self, mode: str = IRMode.RAPID) -> IRBackronymSet:
        """Create a new backronym set with random word.

        Args:
            mode: Game mode ('standard' or 'rapid'). Defaults to 'rapid'.

        Returns:
            IRBackronymSet: Created set

        Raises:
            IRBackronymSetError: If set creation fails
        """
        try:
            # Generate random word
            word = await self.word_service.get_random_word()

            # Create set
            set_obj = IRBackronymSet(
                word=word,
                mode=mode,
                status=IRSetStatus.OPEN,
                created_at=datetime.now(UTC),
            )
            self.db.add(set_obj)
            await self.db.flush()  # Flush to get the set_id without committing
            # Store set_id locally to avoid lazy load issues
            set_id_str = str(set_obj.set_id)
            # Cache word usage (doesn't commit)
            await self.word_service.cache_word_usage(set_id_str, word)
            # Now commit everything together
            await self.db.commit()
            await self.db.refresh(set_obj)
            await self.queue_service.enqueue_entry_set(set_id_str)

            logger.info(f"Created IR backronym set {set_obj.set_id} with word {word}")
            return set_obj

        except IRWordError as e:
            raise IRBackronymSetError(f"Failed to generate word: {str(e)}") from e
        except Exception as e:
            await self.db.rollback()
            raise IRBackronymSetError(f"Failed to create set: {str(e)}") from e

    async def get_set_by_id(self, set_id: str) -> IRBackronymSet | None:
        """Get backronym set by ID.

        Args:
            set_id: Set UUID

        Returns:
            IRBackronymSet or None if not found
        """
        stmt = select(IRBackronymSet).where(IRBackronymSet.set_id == set_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_available_set_for_entry(
        self, exclude_player_id: str | None = None
    ) -> IRBackronymSet | None:
        """Get an open set for a player to join.

        Prioritizes recently created open sets to avoid spreading players across
        multiple sets.

        Args:
            exclude_player_id: Optional player ID to exclude (if player already
                              has entry in a set)

        Returns:
            IRBackronymSet or None if no available sets
        """
        try:
            # Find open sets that are not too old
            age_limit = datetime.now(UTC) - timedelta(
                minutes=self.settings.ir_rapid_entry_timeout_minutes * 2
            )
            stmt = select(IRBackronymSet).where(
                and_(
                    IRBackronymSet.status == IRSetStatus.OPEN,
                    IRBackronymSet.created_at >= age_limit,
                    IRBackronymSet.entry_count < 5,  # Not full
                )
            )

            # If player specified, exclude sets where they already have entry
            if exclude_player_id:
                existing_entries = select(IRBackronymEntry.set_id).where(
                    IRBackronymEntry.player_id == exclude_player_id
                )
                stmt = stmt.where(
                    ~IRBackronymSet.set_id.in_(existing_entries)
                )

            # Order by created_at DESC (most recent first)
            stmt = stmt.order_by(IRBackronymSet.created_at.desc()).limit(1)

            result = await self.db.execute(stmt)
            return result.scalars().first()

        except Exception as e:
            logger.error(f"Error getting available set: {e}")
            return None

    async def add_entry(
        self,
        set_id: str,
        player_id: str,
        backronym_text: list[str],
        is_ai: bool = False,
    ) -> IRBackronymEntry:
        """Add a backronym entry to a set.

        Args:
            set_id: Set UUID
            player_id: Player UUID
            backronym_text: Array of words for backronym
            is_ai: Whether this is an AI-generated entry

        Returns:
            IRBackronymEntry: Created entry

        Raises:
            IRBackronymSetError: If entry creation fails
        """
        try:
            set_obj = await self.get_set_by_id(set_id)
            if not set_obj:
                raise IRBackronymSetError("set_not_found")

            if set_obj.status != IRSetStatus.OPEN:
                raise IRBackronymSetError("set_not_open")

            # Create entry
            entry = IRBackronymEntry(
                set_id=set_id,
                player_id=player_id,
                backronym_text=backronym_text,
                is_ai=is_ai,
                submitted_at=datetime.now(UTC),
            )
            self.db.add(entry)

            # Update set entry count
            set_obj.entry_count += 1
            if not is_ai:
                now = datetime.now(UTC)
                set_obj.last_human_entry_at = now
                if set_obj.first_participant_joined_at is None:
                    set_obj.first_participant_joined_at = now

                    # Create observer guard when first participant joins
                    # Use the timestamp when first participant joined the set,
                    # not their account creation time. This blocks accounts created
                    # after the set started, preventing gaming the system.
                    observer_guard = IRBackronymObserverGuard(
                        set_id=set_id,
                        first_participant_created_at=now,  # When they joined, not account age
                    )
                    self.db.add(observer_guard)
                    logger.info(
                        f"Created observer guard for set {set_id} with timestamp {now}"
                    )

                # Set timer for when AI will fill remaining slots (Rapid mode only)
                if set_obj.mode == IRMode.RAPID:
                    set_obj.transitions_to_voting_at = now + timedelta(
                        minutes=self.settings.ir_rapid_entry_timer_minutes
                    )

            await self.db.commit()
            await self.db.refresh(entry)

            logger.info(
                f"Added entry {entry.entry_id} to set {set_id} from player {player_id}"
            )

            # Check if we should transition to voting
            if set_obj.entry_count >= 5:
                await self.transition_to_voting(set_id)

            return entry

        except IRBackronymSetError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise IRBackronymSetError(f"Failed to add entry: {str(e)}") from e

    async def transition_to_voting(self, set_id: str) -> IRBackronymSet:
        """Transition set from open to voting phase.

        Args:
            set_id: Set UUID

        Returns:
            IRBackronymSet: Updated set

        Raises:
            IRBackronymSetError: If transition fails
        """
        try:
            set_obj = await self.get_set_by_id(set_id)
            if not set_obj:
                raise IRBackronymSetError("set_not_found")

            if set_obj.status != IRSetStatus.OPEN:
                raise IRBackronymSetError("set_not_in_open_status")

            set_obj.status = IRSetStatus.VOTING

            # Set timer for when AI will fill remaining votes
            now = datetime.now(UTC)
            if set_obj.mode == IRMode.RAPID:
                set_obj.voting_finalized_at = now + timedelta(
                    minutes=self.settings.ir_rapid_voting_timer_minutes
                )
            else:  # Standard mode
                set_obj.voting_finalized_at = now + timedelta(
                    minutes=self.settings.ir_standard_voting_timer_minutes
                )

            await self.db.commit()
            await self.db.refresh(set_obj)
            await self.queue_service.dequeue_entry_set(set_id)
            await self.queue_service.enqueue_voting_set(set_id)

            logger.info(f"Transitioned set {set_id} to VOTING phase")
            return set_obj

        except IRBackronymSetError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise IRBackronymSetError(f"Failed to transition to voting: {str(e)}") from e

    async def add_vote(
        self,
        set_id: str,
        player_id: str,
        chosen_entry_id: str,
        is_participant_voter: bool,
        is_ai: bool = False,
    ) -> IRBackronymVote:
        """Add a vote to a set.

        Args:
            set_id: Set UUID
            player_id: Player UUID
            chosen_entry_id: Entry ID being voted for
            is_participant_voter: Whether voter participated in entry creation
            is_ai: Whether this is an AI vote

        Returns:
            IRBackronymVote: Created vote

        Raises:
            IRBackronymSetError: If vote addition fails
        """
        try:
            set_obj = await self.get_set_by_id(set_id)
            if not set_obj:
                raise IRBackronymSetError("set_not_found")

            if set_obj.status != IRSetStatus.VOTING:
                raise IRBackronymSetError("set_not_in_voting_phase")

            # Create vote
            vote = IRBackronymVote(
                set_id=set_id,
                player_id=player_id,
                chosen_entry_id=chosen_entry_id,
                is_participant_voter=is_participant_voter,
                is_ai=is_ai,
                created_at=datetime.now(UTC),
            )
            self.db.add(vote)

            # Update set vote count
            set_obj.vote_count += 1
            if not is_ai:
                set_obj.last_human_vote_at = datetime.now(UTC)
            if not is_participant_voter:
                set_obj.non_participant_vote_count += 1

            # Update entry vote count
            entry = (
                await self.db.execute(
                    select(IRBackronymEntry).where(
                        IRBackronymEntry.entry_id == chosen_entry_id
                    )
                )
            ).scalars().first()
            if entry:
                entry.received_votes += 1

            await self.db.commit()
            await self.db.refresh(vote)

            logger.debug(
                f"Added vote {vote.vote_id} to set {set_id} from player {player_id}"
            )

            # Check if we should finalize:
            # Finalize when all 5 participant creators have voted
            # Non-participant votes are "up to 5" but not required for finalization
            participant_votes = (
                await self.db.execute(
                    select(IRBackronymVote).where(
                        and_(
                            IRBackronymVote.set_id == set_id,
                            IRBackronymVote.is_participant_voter == True,
                        )
                    )
                )
            ).scalars().all()

            participant_vote_count = len(participant_votes)

            # Finalize if all 5 participant creators have voted
            if participant_vote_count >= 5:
                await self.finalize_set(set_id)
                logger.info(
                    f"Set {set_id} finalized after {participant_vote_count} participant votes "
                    f"and {set_obj.non_participant_vote_count} non-participant votes"
                )

            return vote

        except IRBackronymSetError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise IRBackronymSetError(f"Failed to add vote: {str(e)}") from e

    async def finalize_set(self, set_id: str) -> IRBackronymSet:
        """Finalize a set after voting period ends.

        Marks set as finalized. Actual payout calculations are handled by
        ir_scoring_service.

        Args:
            set_id: Set UUID

        Returns:
            IRBackronymSet: Updated set

        Raises:
            IRBackronymSetError: If finalization fails
        """
        try:
            set_obj = await self.get_set_by_id(set_id)
            if not set_obj:
                raise IRBackronymSetError("set_not_found")

            set_obj.status = IRSetStatus.FINALIZED
            set_obj.finalized_at = datetime.now(UTC)
            await self.db.commit()
            await self.db.refresh(set_obj)
            await self.queue_service.dequeue_voting_set(set_id)

            logger.info(f"Finalized set {set_id}")
            return set_obj

        except IRBackronymSetError:
            raise
        except Exception as e:
            await self.db.rollback()
            raise IRBackronymSetError(f"Failed to finalize set: {str(e)}") from e

    async def get_set_details(self, set_id: str) -> dict:
        """Get full set details including entries and votes.

        Args:
            set_id: Set UUID

        Returns:
            dict: Set details with entries and votes

        Raises:
            IRBackronymSetError: If set not found
        """
        try:
            set_obj = await self.get_set_by_id(set_id)
            if not set_obj:
                raise IRBackronymSetError("set_not_found")

            # Get entries
            entries_stmt = select(IRBackronymEntry).where(
                IRBackronymEntry.set_id == set_id
            )
            entries_result = await self.db.execute(entries_stmt)
            entries = entries_result.scalars().all()

            # Get votes
            votes_stmt = select(IRBackronymVote).where(
                IRBackronymVote.set_id == set_id
            )
            votes_result = await self.db.execute(votes_stmt)
            votes = votes_result.scalars().all()

            return {
                "set_id": str(set_obj.set_id),
                "word": set_obj.word,
                "mode": set_obj.mode,
                "status": set_obj.status,
                "entry_count": set_obj.entry_count,
                "vote_count": set_obj.vote_count,
                "created_at": set_obj.created_at.isoformat(),
                "finalized_at": set_obj.finalized_at.isoformat()
                if set_obj.finalized_at
                else None,
                "entries": [
                    {
                        "entry_id": str(e.entry_id),
                        "player_id": str(e.player_id),
                        "backronym_text": e.backronym_text,
                        "is_ai": e.is_ai,
                        "received_votes": e.received_votes,
                        "vote_share_pct": e.vote_share_pct,
                    }
                    for e in entries
                ],
                "votes": [
                    {
                        "vote_id": str(v.vote_id),
                        "player_id": str(v.player_id),
                        "chosen_entry_id": str(v.chosen_entry_id),
                        "is_participant_voter": v.is_participant_voter,
                        "is_ai": v.is_ai,
                    }
                    for v in votes
                ],
            }

        except IRBackronymSetError:
            raise
        except Exception as e:
            raise IRBackronymSetError(f"Failed to get set details: {str(e)}") from e

    async def get_stalled_open_sets(self, minutes: int = 2) -> list[IRBackronymSet]:
        """Get sets that have been open for too long and need AI filling.

        Args:
            minutes: Age threshold in minutes

        Returns:
            list[IRBackronymSet]: Sets needing AI entries
        """
        try:
            cutoff_time = datetime.now(UTC) - timedelta(minutes=minutes)
            stmt = select(IRBackronymSet).where(
                and_(
                    IRBackronymSet.status == IRSetStatus.OPEN,
                    IRBackronymSet.entry_count < 5,
                    IRBackronymSet.created_at <= cutoff_time,
                )
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting stalled open sets: {e}")
            return []

    async def get_stalled_voting_sets(self, minutes: int = 2) -> list[IRBackronymSet]:
        """Get sets that have been voting for too long and need AI votes.

        Args:
            minutes: Age threshold in minutes

        Returns:
            list[IRBackronymSet]: Sets needing AI votes
        """
        try:
            cutoff_time = datetime.now(UTC) - timedelta(minutes=minutes)
            stmt = select(IRBackronymSet).where(
                and_(
                    IRBackronymSet.status == IRSetStatus.VOTING,
                    IRBackronymSet.vote_count < 5,
                    # Check when first participant joined or created
                    or_(
                        IRBackronymSet.first_participant_joined_at <= cutoff_time,
                        and_(
                            IRBackronymSet.first_participant_joined_at == None,
                            IRBackronymSet.created_at <= cutoff_time,
                        ),
                    ),
                )
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting stalled voting sets: {e}")
            return []
