"""Test CASCADE delete behavior for Player foreign keys."""
import pytest
from datetime import datetime, UTC, timedelta
from sqlalchemy import select, delete
from backend.models import (
    Player,
    Transaction,
    DailyBonus,
    RefreshToken,
    Quest,
)


@pytest.mark.asyncio
async def test_cascade_delete_removes_all_player_data(db_session):
    """Test that deleting a player cascades to all related tables."""
    # Create a test player
    player = Player(
        username="cascadetest123",
        username_canonical="cascadetest123",
        pseudonym="Test CASCADE 123",
        pseudonym_canonical="test cascade 123",
        email="cascade123@example.com",
        password_hash="fake_hash"
    )
    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)
    player_id = player.player_id

    # Create related records in various tables
    # 1. Transaction
    transaction = Transaction(
        player_id=player_id,
        amount=100,
        type="test",
        balance_after=100
    )
    db_session.add(transaction)

    # 2. Daily Bonus
    daily_bonus = DailyBonus(
        player_id=player_id,
        amount=100,
        date=datetime.now(UTC).date()
    )
    db_session.add(daily_bonus)

    # 3. Refresh Token
    refresh_token = RefreshToken(
        player_id=player_id,
        token_hash="test_token_hash",
        expires_at=datetime.now(UTC) + timedelta(days=1)
    )
    db_session.add(refresh_token)

    # 4. Quest
    quest = Quest(
        player_id=player_id,
        quest_type="test_quest",
        reward_amount=50,
        progress={}
    )
    db_session.add(quest)

    await db_session.commit()

    # Verify all records exist
    result = await db_session.execute(
        select(Transaction).where(Transaction.player_id == player_id)
    )
    assert result.scalar_one_or_none() is not None

    result = await db_session.execute(
        select(DailyBonus).where(DailyBonus.player_id == player_id)
    )
    assert result.scalar_one_or_none() is not None

    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.player_id == player_id)
    )
    assert result.scalar_one_or_none() is not None

    result = await db_session.execute(
        select(Quest).where(Quest.player_id == player_id)
    )
    assert result.scalar_one_or_none() is not None

    # Delete the player using SQLAlchemy delete
    await db_session.execute(
        delete(Player).where(Player.player_id == player_id)
    )
    await db_session.commit()

    # Verify all related records were cascaded
    result = await db_session.execute(
        select(Transaction).where(Transaction.player_id == player_id)
    )
    assert result.scalar_one_or_none() is None

    result = await db_session.execute(
        select(DailyBonus).where(DailyBonus.player_id == player_id)
    )
    assert result.scalar_one_or_none() is None

    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.player_id == player_id)
    )
    assert result.scalar_one_or_none() is None

    result = await db_session.execute(
        select(Quest).where(Quest.player_id == player_id)
    )
    assert result.scalar_one_or_none() is None
