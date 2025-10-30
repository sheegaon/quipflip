"""
Comprehensive tests for VoteService.

Tests vote submission, validation, payout calculation, and phraseset state management.
"""

import pytest
from datetime import datetime, timedelta, UTC
import uuid

from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.vote import Vote
from backend.services.vote_service import VoteService
from backend.services.transaction_service import TransactionService
from backend.config import get_settings
from backend.utils.exceptions import InvalidPhraseError

settings = get_settings()


@pytest.fixture
async def test_phraseset_with_players(db_session):
    """Create a complete phraseset with players for voting tests."""
    test_id = uuid.uuid4().hex[:8]

    # Create players
    prompter = Player(
        player_id=uuid.uuid4(),
        username=f"prompter_{test_id}",
        username_canonical=f"prompter_{test_id}",
        pseudonym=f"Prompter_{test_id}",
        pseudonym_canonical=f"prompter_{test_id}",
        email=f"prompter_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    copier1 = Player(
        player_id=uuid.uuid4(),
        username=f"copier1_{test_id}",
        username_canonical=f"copier1_{test_id}",
        pseudonym=f"Copier1_{test_id}",
        pseudonym_canonical=f"copier1_{test_id}",
        email=f"copier1_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    copier2 = Player(
        player_id=uuid.uuid4(),
        username=f"copier2_{test_id}",
        username_canonical=f"copier2_{test_id}",
        pseudonym=f"Copier2_{test_id}",
        pseudonym_canonical=f"copier2_{test_id}",
        email=f"copier2_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    voter = Player(
        player_id=uuid.uuid4(),
        username=f"voter_{test_id}",
        username_canonical=f"voter_{test_id}",
        pseudonym=f"Voter_{test_id}",
        pseudonym_canonical=f"voter_{test_id}",
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
            voter = Player(
                player_id=uuid.uuid4(),
                username=f"voter{i}_{test_id}",
                username_canonical=f"voter{i}_{test_id}",
                pseudonym=f"Voter{i}_{test_id}",
                pseudonym_canonical=f"voter{i}_{test_id}",
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
            voter = Player(
                player_id=uuid.uuid4(),
                username=f"wrong_voter{i}_{test_id}",
                username_canonical=f"wrong_voter{i}_{test_id}",
                pseudonym=f"WrongVoter{i}_{test_id}",
                pseudonym_canonical=f"wrongvoter{i}_{test_id}",
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
