"""IR Vote Service - Voting logic and eligibility checks."""

import logging
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.models.ir.ir_backronym_set import IRBackronymSet
from backend.models.ir.ir_backronym_entry import IRBackronymEntry
from backend.models.ir.ir_backronym_vote import IRBackronymVote
from backend.models.ir.ir_player import IRPlayer
from backend.models.ir.enums import IRSetStatus

logger = logging.getLogger(__name__)


class IRVoteError(RuntimeError):
    """Raised when vote service fails."""


class IRVoteService:
    """Service for voting logic and eligibility checking."""

    def __init__(self, db: AsyncSession):
        """Initialize IR vote service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()

    async def check_vote_eligibility(
        self, player_id: str, set_id: str
    ) -> tuple[bool, str, bool]:
        """Check if player can vote on a set.

        Args:
            player_id: Player UUID
            set_id: Set UUID

        Returns:
            tuple: (is_eligible, error_message, is_participant)
                - is_eligible: True if player can vote
                - error_message: Error message if not eligible
                - is_participant: True if player created entry in this set

        Raises:
            IRVoteError: If eligibility check fails
        """
        try:
            # Get set
            set_stmt = select(IRBackronymSet).where(IRBackronymSet.set_id == set_id)
            set_result = await self.db.execute(set_stmt)
            set_obj = set_result.scalars().first()

            if not set_obj:
                return False, "set_not_found", False

            if set_obj.status != IRSetStatus.VOTING:
                return False, "set_not_in_voting_phase", False

            # Check if player has wallet balance for vote
            player_stmt = select(IRPlayer).where(IRPlayer.player_id == player_id)
            player_result = await self.db.execute(player_stmt)
            player = player_result.scalars().first()

            if not player:
                return False, "player_not_found", False

            # Check if player is a participant (has entry in set)
            entry_stmt = select(IRBackronymEntry).where(
                (IRBackronymEntry.set_id == set_id)
                & (IRBackronymEntry.player_id == player_id)
            )
            entry_result = await self.db.execute(entry_stmt)
            player_entry = entry_result.scalars().first()

            is_participant = player_entry is not None

            # Check wallet balance only for non-participants
            # Participants already paid entry fee and don't pay to vote
            if not is_participant:
                if (
                    set_obj.non_participant_vote_count
                    >= self.settings.ir_non_participant_votes_per_set
                ):
                    return False, "non_participant_slots_filled", False
                vote_cost = self.settings.ir_vote_cost
                if player.wallet < vote_cost:
                    return False, "insufficient_balance", False

            # Check if player already voted
            vote_stmt = select(IRBackronymVote).where(
                (IRBackronymVote.set_id == set_id)
                & (IRBackronymVote.player_id == player_id)
            )
            vote_result = await self.db.execute(vote_stmt)
            existing_vote = vote_result.scalars().first()

            if existing_vote:
                return False, "already_voted", is_participant

            # Non-participant vote cap check (optional, can vote multiple times if want)
            # For MVP, we allow unlimited votes from non-participants
            if not is_participant:
                # Check if guest player exceeds non-participant vote cap
                if player.is_guest and not is_participant:
                    # Count non-participant votes by this guest
                    guest_votes_stmt = select(IRBackronymVote).where(
                        (IRBackronymVote.player_id == player_id)
                        & (IRBackronymVote.is_participant_voter == False)
                    )
                    guest_votes_result = await self.db.execute(guest_votes_stmt)
                    guest_votes = guest_votes_result.scalars().all()

                    if (
                        len(guest_votes)
                        >= self.settings.ir_non_participant_vote_cap
                    ):
                        return (
                            False,
                            "non_participant_vote_cap_exceeded",
                            is_participant,
                        )

            return True, "", is_participant

        except Exception as e:
            raise IRVoteError(f"Vote eligibility check failed: {str(e)}") from e

    async def get_available_sets_for_voting(self, player_id: str) -> list[dict]:
        """Get sets available for a player to vote on.

        Returns sets that are in voting phase and player hasn't voted on.

        Args:
            player_id: Player UUID

        Returns:
            list[dict]: Available sets with basic info
        """
        try:
            # Get all voting sets
            sets_stmt = select(IRBackronymSet).where(
                IRBackronymSet.status == IRSetStatus.VOTING
            )
            sets_result = await self.db.execute(sets_stmt)
            voting_sets = sets_result.scalars().all()

            available_sets = []

            for set_obj in voting_sets:
                # Check eligibility
                is_eligible, error, is_participant = await self.check_vote_eligibility(
                    player_id, str(set_obj.set_id)
                )

                if is_eligible:
                    available_sets.append(
                        {
                            "set_id": str(set_obj.set_id),
                            "word": set_obj.word,
                            "entry_count": set_obj.entry_count,
                            "vote_count": set_obj.vote_count,
                            "is_participant": is_participant,
                        }
                    )

            return available_sets

        except Exception as e:
            logger.error(f"Error getting available voting sets: {e}")
            return []

    async def get_entries_for_voting(self, set_id: str) -> list[dict]:
        """Get all entries in a set for voting display.

        Shuffles entries to avoid bias and marks player's own entry.

        Args:
            set_id: Set UUID

        Returns:
            list[dict]: Entries with basic info, shuffled

        Raises:
            IRVoteError: If retrieval fails
        """
        try:
            # Get all entries
            entries_stmt = select(IRBackronymEntry).where(
                IRBackronymEntry.set_id == set_id
            )
            entries_result = await self.db.execute(entries_stmt)
            entries = entries_result.scalars().all()

            # Convert to dict and shuffle
            entries_list = [
                {
                    "entry_id": str(e.entry_id),
                    "player_id": str(e.player_id),
                    "backronym_text": e.backronym_text,
                    "is_ai": e.is_ai,
                }
                for e in entries
            ]

            # Shuffle using deterministic shuffle based on set_id
            # This ensures same shuffle for all viewers
            import hashlib

            seed = int(
                hashlib.md5(str(set_id).encode()).hexdigest(), 16
            )
            import random

            rng = random.Random(seed)
            rng.shuffle(entries_list)

            return entries_list

        except Exception as e:
            raise IRVoteError(f"Failed to get entries for voting: {str(e)}") from e

    async def submit_vote(
        self,
        set_id: str,
        player_id: str,
        chosen_entry_id: str,
        is_participant: bool,
    ) -> dict:
        """Submit a vote for a backronym entry.

        Assumes eligibility has already been checked by the caller (router).
        For non-participants, assumes voting cost has already been deducted from wallet.

        Args:
            set_id: Set UUID
            player_id: Player UUID
            chosen_entry_id: Entry ID being voted for
            is_participant: Whether voter participated in entry creation

        Returns:
            dict: Vote submission result with vote info

        Raises:
            IRVoteError: If vote submission fails
        """
        try:
            # Verify chosen entry exists and belongs to set
            entry_stmt = select(IRBackronymEntry).where(
                (IRBackronymEntry.entry_id == chosen_entry_id)
                & (IRBackronymEntry.set_id == set_id)
            )
            entry_result = await self.db.execute(entry_stmt)
            entry = entry_result.scalars().first()

            if not entry:
                raise IRVoteError("entry_not_found")

            if str(entry.player_id) == str(player_id):
                raise IRVoteError("cannot_vote_own_entry")

            # Create vote
            vote = IRBackronymVote(
                set_id=set_id,
                player_id=player_id,
                chosen_entry_id=chosen_entry_id,
                is_participant_voter=is_participant,
                created_at=datetime.now(UTC),
            )
            self.db.add(vote)

            # Update set vote count
            set_stmt = select(IRBackronymSet).where(IRBackronymSet.set_id == set_id)
            set_result = await self.db.execute(set_stmt)
            set_obj = set_result.scalars().first()

            if set_obj:
                set_obj.vote_count += 1
                if not is_participant:
                    set_obj.non_participant_vote_count += 1

            # Update entry vote count
            entry.received_votes += 1

            await self.db.commit()
            await self.db.refresh(vote)

            logger.info(
                f"Vote submitted: player {player_id} voted on set {set_id} for entry {chosen_entry_id}"
            )

            return {
                "vote_id": str(vote.vote_id),
                "set_id": set_id,
                "chosen_entry_id": chosen_entry_id,
                "created_at": vote.created_at.isoformat(),
            }

        except IRVoteError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise IRVoteError(f"Failed to submit vote: {str(e)}") from e

    async def get_vote_stats_for_set(self, set_id: str) -> dict:
        """Get voting statistics for a set.

        Args:
            set_id: Set UUID

        Returns:
            dict: Vote statistics
        """
        try:
            # Get votes
            votes_stmt = select(IRBackronymVote).where(
                IRBackronymVote.set_id == set_id
            )
            votes_result = await self.db.execute(votes_stmt)
            votes = votes_result.scalars().all()

            # Get entries
            entries_stmt = select(IRBackronymEntry).where(
                IRBackronymEntry.set_id == set_id
            )
            entries_result = await self.db.execute(entries_stmt)
            entries = entries_result.scalars().all()

            # Count votes by entry
            votes_by_entry = {}
            for entry in entries:
                entry_votes = [v for v in votes if v.chosen_entry_id == entry.entry_id]
                votes_by_entry[str(entry.entry_id)] = {
                    "entry_id": str(entry.entry_id),
                    "vote_count": len(entry_votes),
                    "vote_percentage": (
                        (len(entry_votes) / len(votes) * 100) if votes else 0
                    ),
                }

            # Count by voter type
            participant_votes = [v for v in votes if v.is_participant_voter]
            non_participant_votes = [v for v in votes if not v.is_participant_voter]
            ai_votes = [v for v in votes if v.is_ai]
            human_votes = [v for v in votes if not v.is_ai]

            return {
                "set_id": set_id,
                "total_votes": len(votes),
                "participant_votes": len(participant_votes),
                "non_participant_votes": len(non_participant_votes),
                "ai_votes": len(ai_votes),
                "human_votes": len(human_votes),
                "votes_by_entry": list(votes_by_entry.values()),
            }

        except Exception as e:
            logger.error(f"Failed to get vote stats: {e}")
            return {}
