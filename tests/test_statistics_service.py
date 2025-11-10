"""Tests for statistics service functionality."""
import pytest
from datetime import datetime, UTC, timedelta
from uuid import uuid4

from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.vote import Vote
from backend.models.transaction import Transaction
from backend.services.statistics_service import StatisticsService


def _base_player(username: str) -> Player:
    from backend.utils.passwords import hash_password

    now = datetime.now(UTC)
    return Player(
        player_id=uuid4(),
        username=username,
        username_canonical=username.lower(),
        email=f"{username}@example.com",
        password_hash=hash_password("TestPassword123!"),
        balance=1000,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_get_player_statistics_new_player(db_session):
    """Test statistics for a new player with no activity."""
    # Create a new player
    player = _base_player("newbie")
    db_session.add(player)
    await db_session.commit()

    # Get statistics
    stats_service = StatisticsService(db_session)
    stats = await stats_service.get_player_statistics(player.player_id)

    # Verify basic info
    assert stats.player_id == player.player_id
    assert stats.username == player.username
    assert stats.overall_balance == 1000

    # Verify all roles have zero stats
    assert stats.prompt_stats.total_rounds == 0
    assert stats.prompt_stats.total_earnings == 0
    assert stats.prompt_stats.win_rate == 0.0

    assert stats.copy_stats.total_rounds == 0
    assert stats.copy_stats.total_earnings == 0
    assert stats.copy_stats.win_rate == 0.0

    assert stats.voter_stats.total_rounds == 0
    assert stats.voter_stats.total_earnings == 0
    assert stats.voter_stats.win_rate == 0.0

    # Verify earnings breakdown
    assert stats.earnings.prompt_earnings == 0
    assert stats.earnings.copy_earnings == 0
    assert stats.earnings.vote_earnings == 0
    assert stats.earnings.daily_bonuses == 0
    assert stats.earnings.total_earnings == 0

    # Verify frequency metrics
    assert stats.frequency.total_rounds_played == 0
    assert stats.frequency.days_active == 0
    assert stats.frequency.rounds_per_day == 0.0

    # Verify empty lists
    assert stats.favorite_prompts == []
    assert stats.best_performing_phrases == []


@pytest.mark.asyncio
async def test_get_player_statistics_with_rounds(db_session):
    """Test statistics for a player with completed rounds."""
    # Create player
    player = _base_player("active_player")
    db_session.add(player)
    await db_session.commit()

    # Create some submitted rounds
    now = datetime.now(UTC)

    # Prompt rounds
    for i in range(3):
        prompt_round = Round(
            round_id=uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=now - timedelta(days=i),
            expires_at=now - timedelta(days=i) + timedelta(minutes=5),
            cost=100,
            prompt_text=f"Test prompt {i}",
            submitted_phrase=f"Test phrase {i}",
        )
        db_session.add(prompt_round)

    # Copy rounds
    for i in range(2):
        copy_round = Round(
            round_id=uuid4(),
            player_id=player.player_id,
            round_type="copy",
            status="submitted",
            created_at=now - timedelta(days=i),
            expires_at=now - timedelta(days=i) + timedelta(minutes=5),
            cost=90,
            copy_phrase=f"Copy phrase {i}",
            original_phrase="Original phrase",
        )
        db_session.add(copy_round)

    # Vote rounds
    for i in range(5):
        vote_round = Round(
            round_id=uuid4(),
            player_id=player.player_id,
            round_type="vote",
            status="submitted",
            created_at=now - timedelta(days=i),
            expires_at=now - timedelta(days=i) + timedelta(minutes=5),
            cost=1,
        )
        db_session.add(vote_round)

    # Add some transactions (earnings)
    # Daily bonus
    daily_bonus = Transaction(
        transaction_id=uuid4(),
        player_id=player.player_id,
        amount=50,
        type="daily_bonus",
        balance_after=1050,
        created_at=now,
    )
    db_session.add(daily_bonus)

    # Vote payout
    vote_payout = Transaction(
        transaction_id=uuid4(),
        player_id=player.player_id,
        amount=25,
        type="vote_payout",
        balance_after=1075,
        created_at=now,
    )
    db_session.add(vote_payout)

    await db_session.commit()

    # Get statistics
    stats_service = StatisticsService(db_session)
    stats = await stats_service.get_player_statistics(player.player_id)

    # Verify round counts
    assert stats.prompt_stats.total_rounds == 3
    assert stats.copy_stats.total_rounds == 2
    assert stats.voter_stats.total_rounds == 5

    # Verify earnings
    assert stats.earnings.daily_bonuses == 50
    assert stats.earnings.vote_earnings == 25
    assert stats.earnings.total_earnings == 75

    # Verify frequency
    assert stats.frequency.total_rounds_played == 10
    assert stats.frequency.days_active > 0


@pytest.mark.asyncio
async def test_get_player_statistics_win_rate(db_session):
    """Test win rate calculation."""
    # Create player
    player = _base_player("winner")
    db_session.add(player)
    await db_session.commit()

    now = datetime.now(UTC)

    # Create prompt rounds first - we'll link 2 to phrasesets for wins
    prompt_rounds = []
    for i in range(3):
        prompt_round = Round(
            round_id=uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=now - timedelta(days=i),
            expires_at=now - timedelta(days=i) + timedelta(minutes=5),
            cost=100,
            prompt_text=f"Test prompt {i}",
            submitted_phrase=f"Test phrase {i}",
        )
        db_session.add(prompt_round)
        prompt_rounds.append(prompt_round)

    await db_session.commit()

    # Create 2 phrasesets linked to the first 2 prompt rounds (these will be "wins")
    phrasesets = []
    for i in range(2):
        phraseset = Phraseset(
            phraseset_id=uuid4(),
            prompt_round_id=prompt_rounds[i].round_id,  # Link to actual prompt round
            copy_round_1_id=uuid4(),
            copy_round_2_id=uuid4(),
            prompt_text=f"Test prompt {i}",
            original_phrase=f"Original {i}",
            copy_phrase_1=f"Copy 1 {i}",
            copy_phrase_2=f"Copy 2 {i}",
            status="finalized",
            vote_count=5,
            total_pool=300,
            created_at=now - timedelta(days=i),
            finalized_at=now - timedelta(days=i),
        )
        db_session.add(phraseset)
        phrasesets.append(phraseset)

    await db_session.commit()

    # Add winning transactions for each phraseset (2 wins total)
    for i, phraseset in enumerate(phrasesets):
        payout = Transaction(
            transaction_id=uuid4(),
            player_id=player.player_id,
            amount=100,
            type="prize_payout",
            reference_id=phraseset.phraseset_id,
            balance_after=1100 + (i * 100),
            created_at=now - timedelta(days=i),
        )
        db_session.add(payout)

    await db_session.commit()

    # Get statistics
    stats_service = StatisticsService(db_session)
    stats = await stats_service.get_player_statistics(player.player_id)

    # Win rate should be 2/3 = 66.67%
    assert stats.prompt_stats.total_rounds == 3
    assert stats.prompt_stats.win_rate == pytest.approx(66.67, rel=0.1)
    assert stats.prompt_stats.total_earnings == 200
    assert stats.prompt_stats.average_earnings == pytest.approx(66.67, rel=0.1)


@pytest.mark.asyncio
async def test_get_player_statistics_nonexistent_player(db_session):
    """Test statistics for a nonexistent player."""
    stats_service = StatisticsService(db_session)

    with pytest.raises(ValueError, match="Player not found"):
        await stats_service.get_player_statistics(uuid4())
