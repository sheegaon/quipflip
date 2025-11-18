"""
Comprehensive tests for VoteService.

Tests vote submission, validation, payout calculation, and phraseset state management.
"""

import pytest
from datetime import datetime, timedelta, UTC
import uuid

from sqlalchemy import delete

from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.vote import Vote
from backend.models.qf.result_view import QFResultView
from backend.services import VoteService
from backend.services import TransactionService
from backend.services import ScoringService
from backend.config import get_settings
from backend.utils.exceptions import InvalidPhraseError

settings = get_settings()


@pytest.fixture
async def test_phraseset_with_players(db_session):
    """Create a complete phraseset with players for voting tests."""
    test_id = uuid.uuid4().hex[:8]

    # Create players
    prompter = QFPlayer(
        player_id=uuid.uuid4(),
        username=f"prompter_{test_id}",
        username_canonical=f"prompter_{test_id}",
        email=f"prompter_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    copier1 = QFPlayer(
        player_id=uuid.uuid4(),
        username=f"copier1_{test_id}",
        username_canonical=f"copier1_{test_id}",
        email=f"copier1_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    copier2 = QFPlayer(
        player_id=uuid.uuid4(),
        username=f"copier2_{test_id}",
        username_canonical=f"copier2_{test_id}",
        email=f"copier2_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    voter = QFPlayer(
        player_id=uuid.uuid4(),
        username=f"voter_{test_id}",
        username_canonical=f"voter_{test_id}",
        email=f"voter_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    db_session.add_all([prompter, copier1, copier2, voter])
    await db_session.commit()

    # Create rounds
    prompt_round = Round(
        round_id=uuid.uuid4(),
        player_id=prompter.player_id,
        round_type="prompt",
        status="submitted",
        prompt_text="Test prompt",
        submitted_phrase="ORIGINAL",
        cost=settings.prompt_cost,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    copy1_round = Round(
        round_id=uuid.uuid4(),
        player_id=copier1.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        original_phrase="ORIGINAL",
        copy_phrase="COPY ONE",
        cost=settings.copy_cost_normal,
        system_contribution=0,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    copy2_round = Round(
        round_id=uuid.uuid4(),
        player_id=copier2.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        original_phrase="ORIGINAL",
        copy_phrase="COPY TWO",
        cost=settings.copy_cost_normal,
        system_contribution=0,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add_all([prompt_round, copy1_round, copy2_round])
    await db_session.flush()

    # Create phraseset
    phraseset = Phraseset(
        phraseset_id=uuid.uuid4(),
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy1_round.round_id,
        copy_round_2_id=copy2_round.round_id,
        prompt_text="Test prompt",
        original_phrase="ORIGINAL",
        copy_phrase_1="COPY ONE",
        copy_phrase_2="COPY TWO",
        status="open",
        vote_count=0,
        total_pool=settings.prize_pool_base,
        vote_contributions=0,
        vote_payouts_paid=0,
        system_contribution=0,
    )
    db_session.add(phraseset)
    await db_session.commit()

    return {
        "phraseset": phraseset,
        "prompter": prompter,
        "copier1": copier1,
        "copier2": copier2,
        "voter": voter,
    }


class TestVoteSubmission:
    """Test basic vote submission functionality."""

    @pytest.mark.asyncio
    async def test_submit_correct_vote(self, db_session, test_phraseset_with_players):
        """Should successfully submit a correct vote and award payout."""
        phraseset = test_phraseset_with_players["phraseset"]
        voter = test_phraseset_with_players["voter"]

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        initial_balance = voter.balance
        initial_pool = phraseset.total_pool

        # Submit correct vote
        vote = await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=voter,
            chosen_phrase="ORIGINAL",
            transaction_service=transaction_service,
        )

        assert vote is not None
        assert vote.voted_phrase == "ORIGINAL"
        assert vote.correct is True
        assert vote.payout == settings.vote_payout_correct

        # Verify voter balance increased
        await db_session.refresh(voter)
        expected_balance = initial_balance - settings.vote_cost + settings.vote_payout_correct
        assert voter.balance == expected_balance

        # Verify phraseset was updated
        await db_session.refresh(phraseset)
        assert phraseset.vote_count == 1
        expected_pool = initial_pool + settings.vote_cost - settings.vote_payout_correct
        assert phraseset.total_pool == expected_pool
        assert phraseset.vote_contributions == settings.vote_cost
        assert phraseset.vote_payouts_paid == settings.vote_payout_correct

    @pytest.mark.asyncio
    async def test_submit_incorrect_vote(self, db_session, test_phraseset_with_players):
        """Should submit incorrect vote with no payout."""
        phraseset = test_phraseset_with_players["phraseset"]
        voter = test_phraseset_with_players["voter"]

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        initial_balance = voter.balance
        initial_pool = phraseset.total_pool

        # Submit incorrect vote
        vote = await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=voter,
            chosen_phrase="COPY ONE",
            transaction_service=transaction_service,
        )

        assert vote is not None
        assert vote.voted_phrase == "COPY ONE"
        assert vote.correct is False
        assert vote.payout == 0

        # Verify voter balance decreased by vote cost only
        await db_session.refresh(voter)
        expected_balance = initial_balance - settings.vote_cost
        assert voter.balance == expected_balance

        # Verify phraseset pool increased (no payout deducted)
        await db_session.refresh(phraseset)
        assert phraseset.vote_count == 1
        expected_pool = initial_pool + settings.vote_cost
        assert phraseset.total_pool == expected_pool
        assert phraseset.vote_contributions == settings.vote_cost
        assert phraseset.vote_payouts_paid == 0


class TestVoteValidation:
    """Test vote validation rules."""

    @pytest.mark.asyncio
    async def test_cannot_vote_on_own_phraseset(self, db_session, test_phraseset_with_players):
        """Should prevent players from voting on their own contributions."""
        phraseset = test_phraseset_with_players["phraseset"]
        prompter = test_phraseset_with_players["prompter"]

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        # Prompter tries to vote on their own phraseset
        with pytest.raises(Exception):  # Should raise appropriate error
            await vote_service.submit_system_vote(
                phraseset=phraseset,
                player=prompter,
                chosen_phrase="ORIGINAL",
                transaction_service=transaction_service,
            )

    @pytest.mark.asyncio
    async def test_cannot_vote_invalid_phrase(self, db_session, test_phraseset_with_players):
        """Should reject votes for phrases not in the phraseset."""
        phraseset = test_phraseset_with_players["phraseset"]
        voter = test_phraseset_with_players["voter"]

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        # Try to vote for invalid phrase
        with pytest.raises(InvalidPhraseError):
            await vote_service.submit_system_vote(
                phraseset=phraseset,
                player=voter,
                chosen_phrase="INVALID PHRASE",
                transaction_service=transaction_service,
            )

    @pytest.mark.asyncio
    async def test_cannot_vote_twice(self, db_session, test_phraseset_with_players):
        """Should prevent double voting on same phraseset."""
        phraseset = test_phraseset_with_players["phraseset"]
        voter = test_phraseset_with_players["voter"]

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        # Submit first vote
        await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=voter,
            chosen_phrase="ORIGINAL",
            transaction_service=transaction_service,
        )

        # Try to vote again
        with pytest.raises(Exception):  # Should raise appropriate error
            await vote_service.submit_system_vote(
                phraseset=phraseset,
                player=voter,
                chosen_phrase="COPY ONE",
                transaction_service=transaction_service,
            )


class TestPhrasesetStatusTransitions:
    """Test phraseset status changes based on vote count."""

    @pytest.mark.asyncio
    async def test_phraseset_opens_correctly(self, db_session, test_phraseset_with_players):
        """Should have phraseset in open status initially."""
        phraseset = test_phraseset_with_players["phraseset"]

        assert phraseset.status == "open"
        assert phraseset.vote_count == 0

    @pytest.mark.asyncio
    async def test_multiple_votes_tracked(self, db_session, test_phraseset_with_players):
        """Should correctly track multiple votes."""
        phraseset = test_phraseset_with_players["phraseset"]
        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        # Create additional voters
        test_id = uuid.uuid4().hex[:8]
        voters = []
        for i in range(3):
            voter = QFPlayer(
                player_id=uuid.uuid4(),
                username=f"voter{i}_{test_id}",
                username_canonical=f"voter{i}_{test_id}",
                email=f"voter{i}_{test_id}@test.com",
                password_hash="hash",
                balance=1000,
            )
            voters.append(voter)

        db_session.add_all(voters)
        await db_session.commit()

        # Submit votes
        for voter in voters:
            await vote_service.submit_system_vote(
                phraseset=phraseset,
                player=voter,
                chosen_phrase="ORIGINAL",
                transaction_service=transaction_service,
            )

        await db_session.refresh(phraseset)
        assert phraseset.vote_count == 3


class TestVoteBalanceAccounting:
    """Test that vote-related balance changes are accurate."""

    @pytest.mark.asyncio
    async def test_vote_cost_deducted(self, db_session, test_phraseset_with_players):
        """Should deduct vote cost from voter balance."""
        phraseset = test_phraseset_with_players["phraseset"]
        voter = test_phraseset_with_players["voter"]

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        initial_balance = voter.balance

        await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=voter,
            chosen_phrase="COPY TWO",  # Incorrect
            transaction_service=transaction_service,
        )

        await db_session.refresh(voter)
        assert voter.balance == initial_balance - settings.vote_cost

    @pytest.mark.asyncio
    async def test_vote_payout_awarded(self, db_session, test_phraseset_with_players):
        """Should award payout for correct vote."""
        phraseset = test_phraseset_with_players["phraseset"]
        voter = test_phraseset_with_players["voter"]

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        initial_balance = voter.balance

        await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=voter,
            chosen_phrase="ORIGINAL",  # Correct
            transaction_service=transaction_service,
        )

        await db_session.refresh(voter)
        net_change = settings.vote_payout_correct - settings.vote_cost
        assert voter.balance == initial_balance + net_change

    @pytest.mark.asyncio
    async def test_prize_pool_grows_with_incorrect_votes(self, db_session, test_phraseset_with_players):
        """Should grow prize pool when voters are wrong."""
        phraseset = test_phraseset_with_players["phraseset"]
        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        initial_pool = phraseset.total_pool

        # Create voters who all vote incorrectly
        test_id = uuid.uuid4().hex[:8]
        for i in range(5):
            voter = QFPlayer(
                player_id=uuid.uuid4(),
                username=f"wrong_voter{i}_{test_id}",
                username_canonical=f"wrong_voter{i}_{test_id}",
                email=f"wrong_voter{i}_{test_id}@test.com",
                password_hash="hash",
                balance=1000,
            )
            db_session.add(voter)
            await db_session.flush()

            await vote_service.submit_system_vote(
                phraseset=phraseset,
                player=voter,
                chosen_phrase="COPY ONE",  # Wrong
                transaction_service=transaction_service,
            )

        await db_session.refresh(phraseset)
        # Pool should grow by vote_cost * 5 (no payouts for wrong answers)
        expected_pool = initial_pool + (settings.vote_cost * 5)
        assert phraseset.total_pool == expected_pool


class TestPhrasesetResults:
    """Tests for contributor results payloads."""

    @pytest.mark.asyncio
    async def test_copy_role_includes_original_phrase(self, db_session, test_phraseset_with_players):
        """Copy contributors should receive the original phrase in results."""
        phraseset = test_phraseset_with_players["phraseset"]
        copier = test_phraseset_with_players["copier1"]
        voter = test_phraseset_with_players["voter"]

        phraseset.status = "finalized"
        phraseset.finalized_at = datetime.now(UTC)
        phraseset.vote_count = 1
        await db_session.flush()

        vote = Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=voter.player_id,
            voted_phrase=phraseset.copy_phrase_1,
            correct=False,
            payout=0,
        )
        db_session.add(vote)
        await db_session.commit()

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        results = await vote_service.get_phraseset_results(
            phraseset.phraseset_id,
            copier.player_id,
            transaction_service,
        )

        assert results["your_role"] == "copy"
        assert results["original_phrase"] == phraseset.original_phrase

    @pytest.mark.asyncio
    async def test_prompt_role_omits_original_phrase(self, db_session, test_phraseset_with_players):
        """Prompt contributors should not receive the redundant original phrase."""
        phraseset = test_phraseset_with_players["phraseset"]
        prompter = test_phraseset_with_players["prompter"]
        voter = test_phraseset_with_players["voter"]

        phraseset.status = "finalized"
        phraseset.finalized_at = datetime.now(UTC)
        phraseset.vote_count = 1
        await db_session.flush()

        vote = Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=voter.player_id,
            voted_phrase=phraseset.copy_phrase_1,
            correct=False,
            payout=0,
        )
        db_session.add(vote)
        await db_session.commit()

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        results = await vote_service.get_phraseset_results(
            phraseset.phraseset_id,
            prompter.player_id,
            transaction_service,
        )

        assert results["your_role"] == "prompt"
        assert "original_phrase" not in results

    @pytest.mark.asyncio
    async def test_existing_result_view_marks_as_viewed(
        self,
        db_session,
        test_phraseset_with_players,
    ):
        """Existing result views should be marked as viewed and committed."""

        phraseset = test_phraseset_with_players["phraseset"]
        prompter = test_phraseset_with_players["prompter"]

        phraseset.status = "finalized"
        phraseset.finalized_at = datetime.now(UTC)
        phraseset.vote_count = 0

        scoring_service = ScoringService(db_session)
        payouts = await scoring_service.calculate_payouts(phraseset)
        prompter_payout = payouts["original"]["payout"]

        preexisting_view = QFResultView(
            view_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=prompter.player_id,
            payout_amount=prompter_payout,
            result_viewed=False,
        )
        db_session.add(preexisting_view)
        await db_session.commit()

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        results = await vote_service.get_phraseset_results(
            phraseset.phraseset_id,
            prompter.player_id,
            transaction_service,
        )

        await db_session.refresh(preexisting_view)

        assert results["already_collected"] is False
        assert preexisting_view.result_viewed is True
        assert preexisting_view.result_viewed_at is not None
        assert preexisting_view.first_viewed_at is not None


class TestGuestVoteLockoutFlow:
    """Validate guest-specific vote tracking within VoteService.submit_vote."""

    @pytest.mark.asyncio
    async def test_guest_vote_lockout_progression(self, db_session, test_phraseset_with_players):
        """Guest votes should increment, reset, and lock out according to settings."""

        phraseset_id = test_phraseset_with_players["phraseset"].phraseset_id
        guest_id = test_phraseset_with_players["voter"].player_id

        # Mark voter as guest and ensure clean slate
        guest = await db_session.get(QFPlayer, guest_id)
        guest.is_guest = True
        guest.consecutive_incorrect_votes = 0
        guest.vote_lockout_until = None
        await db_session.commit()

        phraseset = await db_session.get(Phraseset, phraseset_id)
        incorrect_phrases = [phraseset.copy_phrase_1, phraseset.copy_phrase_2]
        original_phrase = phraseset.original_phrase

        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        async def submit_guest_vote(phrase: str) -> QFPlayer:
            current_player = await db_session.get(QFPlayer, guest_id)
            phraseset_obj = await db_session.get(Phraseset, phraseset_id)

            vote_round = Round(
                round_id=uuid.uuid4(),
                player_id=current_player.player_id,
                round_type="vote",
                status="active",
                phraseset_id=phraseset_obj.phraseset_id,
                prompt_round_id=phraseset_obj.prompt_round_id,
                cost=settings.vote_cost,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            current_player.active_round_id = vote_round.round_id
            db_session.add(vote_round)
            await db_session.flush()

            vote = await vote_service.submit_vote(
                vote_round,
                phraseset_obj,
                phrase,
                current_player,
                transaction_service,
            )

            await db_session.execute(delete(Vote).where(Vote.vote_id == vote.vote_id))
            await db_session.commit()

            return await db_session.get(QFPlayer, guest_id)

        # Incorrect votes should increment the counter
        guest = await submit_guest_vote(incorrect_phrases[0])
        assert guest.consecutive_incorrect_votes == 1
        assert guest.vote_lockout_until is None

        guest = await submit_guest_vote(incorrect_phrases[1])
        assert guest.consecutive_incorrect_votes == 2
        assert guest.vote_lockout_until is None

        # Correct vote resets the counter
        guest = await submit_guest_vote(original_phrase)
        assert guest.consecutive_incorrect_votes == 0
        assert guest.vote_lockout_until is None

        # Reach configured threshold again to trigger lockout
        for attempt in range(settings.guest_vote_lockout_threshold):
            phrase = incorrect_phrases[attempt % len(incorrect_phrases)]
            guest = await submit_guest_vote(phrase)

        assert guest.consecutive_incorrect_votes == settings.guest_vote_lockout_threshold
        assert guest.vote_lockout_until is not None

        expected_duration = timedelta(hours=settings.guest_vote_lockout_hours)
        tolerance = timedelta(seconds=5)
        remaining = guest.vote_lockout_until - datetime.now(UTC)
        assert remaining <= expected_duration
        assert remaining >= max(expected_duration - tolerance, timedelta(0))
