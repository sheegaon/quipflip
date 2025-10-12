"""Vote service for managing voting rounds and finalization."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, UTC, timedelta
from backend.utils.exceptions import NoWordsetsAvailableError,  AlreadyVotedError, RoundExpiredError
from uuid import UUID
import uuid
import random
import logging

from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import PhraseSet
from backend.models.vote import Vote
from backend.models.result_view import ResultView
from backend.services.transaction_service import TransactionService
from backend.services.scoring_service import ScoringService
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VoteService:
    """Service for managing voting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_available_wordsets_for_player(self, player_id: UUID) -> list[PhraseSet]:
        """Load phrasesets the player can vote on (excludes contributors and already-voted)."""
        result = await self.db.execute(
            select(PhraseSet)
            .where(PhraseSet.status.in_(["open", "closing"]))
            .options(
                selectinload(PhraseSet.prompt_round),
                selectinload(PhraseSet.copy_round_1),
                selectinload(PhraseSet.copy_round_2),
            )
        )
        all_wordsets = list(result.scalars().all())
        if not all_wordsets:
            return []

        # Filter out phrasesets where player was a contributor
        candidate_wordsets = [
            ws for ws in all_wordsets
            if player_id not in {
                ws.prompt_round.player_id,
                ws.copy_round_1.player_id,
                ws.copy_round_2.player_id,
            }
        ]
        candidate_ids = [ws.phraseset_id for ws in candidate_wordsets]

        if not candidate_wordsets:
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

        available = [ws for ws in candidate_wordsets if ws.phraseset_id not in voted_ids]
        return available

    async def get_available_wordset_for_player(self, player_id: UUID) -> PhraseSet | None:
        """
        Get available phraseset for voting with priority:
        1. Wordsets with >=5 votes (FIFO by fifth_vote_at)
        2. Wordsets with 3-4 votes (FIFO by third_vote_at)
        3. Wordsets with <3 votes (random)
        """
        available = await self._load_available_wordsets_for_player(player_id)

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

    async def count_available_wordsets_for_player(self, player_id: UUID) -> int:
        """Count how many phrasesets the player can vote on."""
        available = await self._load_available_wordsets_for_player(player_id)
        return len(available)

    async def start_vote_round(
        self,
        player: Player,
        transaction_service: TransactionService,
    ) -> tuple[Round, PhraseSet]:
        """
        Start a vote round.

        - Get available phraseset (with priority)
        - Deduct $1 immediately
        - Create round with 60s timer
        - Return round and phraseset with randomized word order

        All operations are performed in a single atomic transaction.
        """
        # Get available phraseset (outside lock - read-only)
        phraseset = await self.get_available_wordset_for_player(player.player_id)
        if not phraseset:
            raise NoWordsetsAvailableError("No phrasesets available for voting")

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

        logger.info(f"Started vote round {round.round_id} for phraseset {phraseset.phraseset_id}")
        return round, phraseset

    async def submit_vote(
        self,
        round: Round,
        phraseset: PhraseSet,
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
        """
        # Check grace period - ensure both datetimes have same timezone awareness
        current_time = datetime.now(UTC)
        expires_at = round.expires_at
        
        # Handle timezone-naive datetime from database
        if expires_at.tzinfo is None:
            # If expires_at is naive, treat it as UTC
            expires_at = expires_at.replace(tzinfo=UTC)
        
        grace_cutoff = expires_at + timedelta(seconds=settings.grace_period_seconds)
        
        if current_time > grace_cutoff:
            raise RoundExpiredError("Round expired past grace period")

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

        # Give payout if correct
        if correct:
            await transaction_service.create_transaction(
                player.player_id,
                payout,
                "vote_payout",
                vote.vote_id,
            )

        # Update round
        round.status = "submitted"
        round.vote_submitted_at = datetime.now(UTC)

        # Clear player's active round
        player.active_round_id = None

        # Update phraseset vote count
        phraseset.vote_count += 1

        await self.db.commit()

        # Update vote timeline
        await self._update_vote_timeline(phraseset)

        # Check if should finalize
        await self._check_and_finalize(phraseset, transaction_service)

        await self.db.refresh(vote)

        logger.info(
            f"Vote submitted: phraseset={phraseset.phraseset_id}, player={player.player_id}, "
            f"phrase={phrase}, correct={correct}, payout=${payout}"
        )
        return vote

    async def _update_vote_timeline(self, phraseset: PhraseSet):
        """Update vote timeline markers (3rd vote, 5th vote)."""
        # Mark 3rd vote timestamp
        if phraseset.vote_count == 3 and not phraseset.third_vote_at:
            phraseset.third_vote_at = datetime.now(UTC)
            logger.info(f"Phraseset {phraseset.phraseset_id} reached 3rd vote, 10min window starts")

        # Mark 5th vote timestamp and change status to closing
        if phraseset.vote_count == 5 and not phraseset.fifth_vote_at:
            phraseset.fifth_vote_at = datetime.now(UTC)
            phraseset.status = "closing"
            phraseset.closes_at = datetime.now(UTC) + timedelta(seconds=60)
            logger.info(f"Phraseset {phraseset.phraseset_id} reached 5th vote, 60sec closing window")

        await self.db.commit()

    async def _check_and_finalize(
        self,
        phraseset: PhraseSet,
        transaction_service: TransactionService,
    ):
        """
        Check if phraseset should be finalized.

        Conditions:
        - 20 votes (max)
        - OR 5+ votes AND 60 seconds elapsed since 5th vote
        - OR 3 votes AND 10 minutes elapsed since 3rd vote
        """
        should_finalize = False
        current_time = datetime.now(UTC)

        # Max votes reached
        if phraseset.vote_count >= 20:
            should_finalize = True
            logger.info(f"Phraseset {phraseset.phraseset_id} reached max votes (20)")

        # 5+ votes and 60 seconds elapsed
        elif phraseset.vote_count >= 5 and phraseset.fifth_vote_at:
            fifth_vote_at = phraseset.fifth_vote_at
            # Handle timezone-naive datetime from database
            if fifth_vote_at.tzinfo is None:
                fifth_vote_at = fifth_vote_at.replace(tzinfo=UTC)
            
            elapsed = (current_time - fifth_vote_at).total_seconds()
            if elapsed >= 60:
                should_finalize = True
                logger.info(f"Phraseset {phraseset.phraseset_id} closing window expired (60s)")

        # 3 votes and 10 minutes elapsed (no 5th vote)
        elif phraseset.vote_count >= 3 and phraseset.third_vote_at and not phraseset.fifth_vote_at:
            third_vote_at = phraseset.third_vote_at
            # Handle timezone-naive datetime from database
            if third_vote_at.tzinfo is None:
                third_vote_at = third_vote_at.replace(tzinfo=UTC)
                
            elapsed = (current_time - third_vote_at).total_seconds()
            if elapsed >= 600:  # 10 minutes
                should_finalize = True
                logger.info(f"Phraseset {phraseset.phraseset_id} 10min window expired")

        if should_finalize:
            await self._finalize_wordset(phraseset, transaction_service)

    async def _finalize_wordset(
        self,
        phraseset: PhraseSet,
        transaction_service: TransactionService,
    ):
        """
        Finalize phraseset.

        - Calculate payouts
        - Create prize transactions
        - Update status to finalized
        """
        # Calculate payouts
        scoring_service = ScoringService(self.db)
        payouts = await scoring_service.calculate_payouts(phraseset)

        # Create prize transactions for each contributor
        for role in ["original", "copy1", "copy2"]:
            payout_info = payouts[role]
            if payout_info["payout"] > 0:
                await transaction_service.create_transaction(
                    payout_info["player_id"],
                    payout_info["payout"],
                    "prize_payout",
                    phraseset.phraseset_id,
                )

        # Update phraseset status
        phraseset.status = "finalized"
        phraseset.finalized_at = datetime.now(UTC)

        await self.db.commit()

        logger.info(
            f"Finalized phraseset {phraseset.phraseset_id}: "
            f"original=${payouts['original']['payout']}, "
            f"copy1=${payouts['copy1']['payout']}, "
            f"copy2=${payouts['copy2']['payout']}"
        )

    async def get_phraseset_results(
        self,
        wordset_id: UUID,
        player_id: UUID,
        transaction_service: TransactionService,
    ) -> dict:
        """
        Get phraseset results for a contributor.

        First view collects payout (idempotent).
        """
        phraseset = await self.db.get(PhraseSet, wordset_id)
        if not phraseset:
            raise ValueError("Phraseset not found")

        if phraseset.status != "finalized":
            raise ValueError("Phraseset not yet finalized")

        # Check if player was a contributor
        prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
        copy1_round = await self.db.get(Round, phraseset.copy_round_1_id)
        copy2_round = await self.db.get(Round, phraseset.copy_round_2_id)

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
            .where(ResultView.phraseset_id == wordset_id)
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

            # Create result view
            result_view = ResultView(
                view_id=uuid.uuid4(),
                phraseset_id=wordset_id,
                player_id=player_id,
                payout_collected=True,  # Mark as collected on first view
                payout_amount=player_payout,
            )
            self.db.add(result_view)
            await self.db.commit()

            logger.info(f"Player {player_id} collected payout ${player_payout} from phraseset {wordset_id}")

        # Get all votes for display
        votes_result = await self.db.execute(
            select(Vote).where(Vote.phraseset_id == wordset_id)
        )
        all_votes = list(votes_result.scalars().all())

        # Count votes per word
        vote_counts = {
            phraseset.original_phrase: 0,
            phraseset.copy_phrase_1: 0,
            phraseset.copy_phrase_2: 0,
        }
        for vote in all_votes:
            vote_counts[vote.voted_phrase] += 1

        # Calculate points
        points = 0
        if phrase == phraseset.original_phrase:
            points = vote_counts[phrase] * 1
        else:
            points = vote_counts[phrase] * 2

        # Build response
        votes_display = []
        for w in [phraseset.original_phrase, phraseset.copy_phrase_1, phraseset.copy_phrase_2]:
            votes_display.append({
                "phrase": w,
                "vote_count": vote_counts[w],
                "is_original": (w == phraseset.original_phrase),
            })

        return {
            "prompt_text": phraseset.prompt_text,
            "votes": votes_display,
            "your_phrase": phrase,
            "your_role": role,
            "your_points": points,
            "your_payout": result_view.payout_amount,
            "total_pool": phraseset.total_pool,
            "total_votes": phraseset.vote_count,
            "already_collected": result_view.payout_collected,
            "finalized_at": phraseset.finalized_at,
        }

    async def get_wordset_results(
        self,
        wordset_id: UUID,
        player_id: UUID,
        transaction_service: TransactionService,
    ) -> dict:
        """Backward-compatible alias for phrase-based results."""
        return await self.get_phraseset_results(wordset_id, player_id, transaction_service)
