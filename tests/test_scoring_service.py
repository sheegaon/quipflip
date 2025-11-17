"""
Tests for ScoringService - payout calculation and distribution.
"""

import pytest
from datetime import datetime, timedelta, UTC
import uuid

from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.vote import Vote
from backend.services import ScoringService
from backend.config import get_settings

settings = get_settings()


@pytest.fixture
async def finalized_phraseset_with_votes(db_session):
    """Create a finalized phraseset with votes for scoring tests."""
    test_id = uuid.uuid4().hex[:8]

    # Create players
    prompter = QFPlayer(
        player_id=uuid.uuid4(),
        username=f"prompter_{test_id}",
        username_canonical=f"prompter_{test_id}",
        email=f"prompter_{test_id}@test.com",
        password_hash="hash",
        balance=5000,
    )
    copier1 = QFPlayer(
        player_id=uuid.uuid4(),
        username=f"copier1_{test_id}",
        username_canonical=f"copier1_{test_id}",
        email=f"copier1_{test_id}@test.com",
        password_hash="hash",
        balance=5000,
    )
    copier2 = QFPlayer(
        player_id=uuid.uuid4(),
        username=f"copier2_{test_id}",
        username_canonical=f"copier2_{test_id}",
        email=f"copier2_{test_id}@test.com",
        password_hash="hash",
        balance=5000,
    )
    db_session.add_all([prompter, copier1, copier2])
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

    # Create phraseset with votes
    # Voting pattern: 3 correct (ORIGINAL), 4 for COPY ONE, 2 for COPY TWO
    phraseset = Phraseset(
        phraseset_id=uuid.uuid4(),
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy1_round.round_id,
        copy_round_2_id=copy2_round.round_id,
        prompt_text="Test prompt",
        original_phrase="ORIGINAL",
        copy_phrase_1="COPY ONE",
        copy_phrase_2="COPY TWO",
        status="finalized",
        vote_count=9,
        total_pool=250,  # Base 200 + some votes
        vote_contributions=90,  # 9 votes * 10
        vote_payouts_paid=60,  # 3 correct * 20
        system_contribution=0,
    )
    db_session.add(phraseset)
    await db_session.flush()

    # Add votes
    votes = [
        # 3 correct votes for ORIGINAL
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="ORIGINAL", correct=True, payout=20),
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="ORIGINAL", correct=True, payout=20),
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="ORIGINAL", correct=True, payout=20),
        # 4 incorrect votes for COPY ONE
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="COPY ONE", correct=False, payout=0),
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="COPY ONE", correct=False, payout=0),
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="COPY ONE", correct=False, payout=0),
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="COPY ONE", correct=False, payout=0),
        # 2 incorrect votes for COPY TWO
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="COPY TWO", correct=False, payout=0),
        Vote(vote_id=uuid.uuid4(), phraseset_id=phraseset.phraseset_id,
             player_id=uuid.uuid4(), voted_phrase="COPY TWO", correct=False, payout=0),
    ]
    db_session.add_all(votes)
    await db_session.commit()

    return {
        "phraseset": phraseset,
        "prompter": prompter,
        "copier1": copier1,
        "copier2": copier2,
        "prompt_round": prompt_round,
        "copy1_round": copy1_round,
        "copy2_round": copy2_round,
    }


class TestPayoutCalculation:
    """Test payout calculation logic."""

    @pytest.mark.asyncio
    async def test_calculate_payouts_basic(self, db_session, finalized_phraseset_with_votes):
        """Should calculate payouts based on vote distribution."""
        phraseset = finalized_phraseset_with_votes["phraseset"]
        scoring_service = ScoringService(db_session)

        payouts = await scoring_service.calculate_payouts(phraseset)

        assert "original" in payouts
        assert "copy1" in payouts
        assert "copy2" in payouts

        # All payouts should be non-negative
        assert payouts["original"]["payout"] >= 0
        assert payouts["copy1"]["payout"] >= 0
        assert payouts["copy2"]["payout"] >= 0

        # Total payouts should approximately equal the prize pool
        total_payout = (
            payouts["original"]["payout"] +
            payouts["copy1"]["payout"] +
            payouts["copy2"]["payout"]
        )
        # Allow small rounding differences
        assert abs(total_payout - phraseset.total_pool) <= 5

    @pytest.mark.asyncio
    async def test_payouts_proportional_to_votes(self, db_session, finalized_phraseset_with_votes):
        """Should award more to phrases with more incorrect votes."""
        phraseset = finalized_phraseset_with_votes["phraseset"]
        scoring_service = ScoringService(db_session)

        payouts = await scoring_service.calculate_payouts(phraseset)

        # COPY ONE got 4 incorrect votes (worth 2 points each = 8 points)
        # ORIGINAL got 3 correct votes (worth 1 point each = 3 points)
        # COPY TWO got 2 incorrect votes (worth 2 points each = 4 points)
        # Total points: 15

        # COPY ONE should get the most (8/15 of pool)
        # COPY TWO should get middle (4/15 of pool)
        # ORIGINAL should get the least (3/15 of pool)
        assert payouts["copy1"]["payout"] > payouts["copy2"]["payout"]
        assert payouts["copy2"]["payout"] > payouts["original"]["payout"]

    @pytest.mark.asyncio
    async def test_payout_with_no_votes(self, db_session):
        """Should handle phraseset with no votes gracefully."""
        test_id = uuid.uuid4().hex[:8]

        prompter = QFPlayer(
            player_id=uuid.uuid4(),
            username=f"prompter_{test_id}",
            username_canonical=f"prompter_{test_id}",
            email=f"prompter_{test_id}@test.com",
            password_hash="hash",
            balance=5000,
        )
        db_session.add(prompter)
        await db_session.commit()

        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompter.player_id,
            round_type="prompt",
            status="submitted",
            prompt_text="Test",
            submitted_phrase="ORIGINAL",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        db_session.add(prompt_round)
        await db_session.flush()

        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=uuid.uuid4(),
            copy_round_2_id=uuid.uuid4(),
            prompt_text="Test",
            original_phrase="ORIGINAL",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="finalized",
            vote_count=0,  # No votes
            total_pool=200,
            vote_contributions=0,
            vote_payouts_paid=0,
            system_contribution=0,
        )
        db_session.add(phraseset)
        await db_session.commit()

        scoring_service = ScoringService(db_session)
        payouts = await scoring_service.calculate_payouts(phraseset)

        # With no votes, should split evenly or use default distribution
        # At minimum, should not crash and should return valid data
        assert "original" in payouts
        assert "copy1" in payouts
        assert "copy2" in payouts


# NOTE: TestPayoutDistribution class removed - payout distribution is now
# integrated into the finalization process in VoteService._finalize_phraseset()
# rather than being a separate ScoringService method. See vote_service.py for
# payout distribution logic.
