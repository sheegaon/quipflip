"""Tests for daily bonus functionality.

This test suite ensures that:
1. Daily bonus appears in the UI when eligible
2. Login does not prevent bonus from being available
3. Bonus is tracked via DailyBonus table, not last_login_date
4. Bonus can only be claimed once per day
"""
import pytest
from datetime import timedelta, datetime, UTC
from uuid import uuid4

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, update

from backend.models.qf.player import QFPlayer
from backend.models.qf.daily_bonus import QFDailyBonus
from backend.services import GameType, QFPlayerService
from backend.services import TransactionService
from backend.config import get_settings


settings = get_settings()


@pytest.mark.asyncio
async def test_new_player_no_bonus_on_creation_day(test_app):
    """New players should NOT get daily bonus on the day they sign up."""
    payload = {
        "email": f"newuser_{uuid4().hex[:6]}@example.com",
        "password": "TestPass123!",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
        response = await client.post("/player", json=payload)
        assert response.status_code == 201
        data = response.json()
        token = data["access_token"]

        # Check balance endpoint
        balance_response = await client.get(
            "/player/balance",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert balance_response.status_code == 200
        balance_data = balance_response.json()

        # Daily bonus should NOT be available on creation day
        assert balance_data["daily_bonus_available"] is False
        assert balance_data["daily_bonus_amount"] == settings.daily_bonus_amount


@pytest.mark.asyncio
async def test_guest_players_cannot_claim_daily_bonus(test_app, db_session):
    """Guest accounts should not have access to the daily bonus."""

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
        response = await client.post("/player/guest")
        assert response.status_code == 201
        data = response.json()
        token = data["access_token"]
        player_id = data["player_id"]
        headers = {"Authorization": f"Bearer {token}"}

        # Initial balance check - bonus should not be available
        balance_response = await client.get("/player/balance", headers=headers)
        assert balance_response.status_code == 200
        balance_data = balance_response.json()
        assert balance_data["daily_bonus_available"] is False
        assert balance_data.get("is_guest") is True

        # Move the creation date back so first-day logic isn't the only blocker
        two_days_ago = datetime.now(UTC) - timedelta(days=2)
        await db_session.execute(
            update(QFPlayer)
            .where(QFPlayer.player_id == player_id)
            .values(created_at=two_days_ago)
        )
        await db_session.commit()

        # Attempting to claim should fail for guests
        claim_response = await client.post("/player/claim-daily-bonus", headers=headers)
        assert claim_response.status_code == 400
        assert "not available" in claim_response.json()["detail"].lower()

        # Bonus should remain unavailable afterwards
        balance_response = await client.get("/player/balance", headers=headers)
        assert balance_response.status_code == 200
        assert balance_response.json()["daily_bonus_available"] is False


@pytest.mark.asyncio
async def test_daily_bonus_available_after_login(test_app, db_session):
    """Daily bonus should remain available after logging in.

    This is the main regression test for the bug where logging in
    would update last_login_date and make the bonus unavailable.
    """
    # Create player
    payload = {
        "email": f"logintest_{uuid4().hex[:6]}@example.com",
        "password": "TestPass123!",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
        create_response = await client.post("/player", json=payload)
        assert create_response.status_code == 201
        player_id = create_response.json()["player_id"]

        # Simulate player created yesterday by updating database
        result = await db_session.execute(
            select(QFPlayer).where(QFPlayer.player_id == player_id)
        )
        player = result.scalar_one()

        yesterday = datetime.now(UTC) - timedelta(days=1)
        await db_session.execute(
            update(QFPlayer)
            .where(QFPlayer.player_id == player_id)
            .values(
                created_at=yesterday,
                last_login_date=yesterday
            )
        )
        await db_session.commit()

        # Login
        login_response = await client.post("/auth/login", json=payload)
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Check that daily bonus is STILL available after login
        balance_response = await client.get(
            "/player/balance",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert balance_response.status_code == 200
        balance_data = balance_response.json()

        # This is the key assertion - bonus should be available after login
        assert balance_data["daily_bonus_available"] is True
        assert balance_data["daily_bonus_amount"] == settings.daily_bonus_amount

        # Verify last_login_date was updated (for tracking)
        last_login_iso = balance_data["last_login_date"]
        assert last_login_iso is not None
        last_login_dt = datetime.fromisoformat(last_login_iso)
        assert last_login_dt.date() == datetime.now(UTC).date()
        assert last_login_dt.tzinfo is not None


@pytest.mark.asyncio
async def test_daily_bonus_uses_dailybonus_table_not_last_login(db_session):
    """Test that is_daily_bonus_available checks DailyBonus table, not last_login_date.

    This ensures the fix is working at the service layer.
    """
    # Create a player with last_login_date = today (which would fail the old logic)
    from backend.services import AuthService
    from backend.utils.model_registry import GameType

    auth_service = AuthService(db_session, game_type=GameType.QF)
    email = f"tabletest_{uuid4().hex[:6]}@example.com"
    player = await auth_service.register_player(email, "TestPass123!")

    # Set created_at to yesterday so bonus would be eligible
    yesterday = datetime.now(UTC) - timedelta(days=1)
    await db_session.execute(
        update(QFPlayer)
        .where(QFPlayer.player_id == player.player_id)
        .values(created_at=yesterday)
    )
    await db_session.commit()
    await db_session.refresh(player)

    # Set last_login_date to now (simulating a login)
    player.last_login_date = datetime.now(UTC)
    await db_session.commit()
    await db_session.refresh(player)

    # Check bonus availability using PlayerService
    player_service = QFPlayerService(db_session)
    is_available = await player_service.is_daily_bonus_available(player)

    # Should be available because DailyBonus table has no entry for today
    assert is_available is True

    # Verify no DailyBonus record exists
    result = await db_session.execute(
        select(QFDailyBonus)
        .where(QFDailyBonus.player_id == player.player_id)
        .where(QFDailyBonus.date == datetime.now(UTC).date())
    )
    bonus_record = result.scalar_one_or_none()
    assert bonus_record is None


@pytest.mark.asyncio
async def test_claim_daily_bonus_makes_it_unavailable(test_app, db_session):
    """After claiming bonus, it should be unavailable for the rest of the day."""
    payload = {
        "email": f"claimtest_{uuid4().hex[:6]}@example.com",
        "password": "TestPass123!",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
        create_response = await client.post("/player", json=payload)
        player_id = create_response.json()["player_id"]

        # Make player eligible by setting created_at to yesterday
        yesterday = datetime.now(UTC) - timedelta(days=1)
        await db_session.execute(
            update(QFPlayer)
            .where(QFPlayer.player_id == player_id)
            .values(created_at=yesterday)
        )
        await db_session.commit()

        # Get token and verify bonus is available
        login_response = await client.post("/auth/login", json=payload)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        balance_response = await client.get("/player/balance", headers=headers)
        assert balance_response.json()["daily_bonus_available"] is True

        # Claim bonus
        claim_response = await client.post("/player/claim-daily-bonus", headers=headers)
        assert claim_response.status_code == 200
        claim_data = claim_response.json()
        assert claim_data["success"] is True
        assert claim_data["amount"] == settings.daily_bonus_amount
        assert claim_data["new_wallet"] == settings.qf_starting_wallet + settings.daily_bonus_amount
        assert claim_data["new_vault"] == 0

        # Verify bonus is now unavailable
        balance_response = await client.get("/player/balance", headers=headers)
        assert balance_response.json()["daily_bonus_available"] is False

        # Verify DailyBonus record was created
        result = await db_session.execute(
            select(QFDailyBonus)
            .where(QFDailyBonus.player_id == player_id)
            .where(QFDailyBonus.date == datetime.now(UTC).date())
        )
        bonus_record = result.scalar_one_or_none()
        assert bonus_record is not None
        assert bonus_record.amount == settings.daily_bonus_amount


@pytest.mark.asyncio
async def test_cannot_claim_daily_bonus_twice(test_app, db_session):
    """Players should not be able to claim daily bonus twice in one day."""
    payload = {
        "email": f"doubletest_{uuid4().hex[:6]}@example.com",
        "password": "TestPass123!",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
        create_response = await client.post("/player", json=payload)
        player_id = create_response.json()["player_id"]

        # Make eligible
        yesterday = datetime.now(UTC) - timedelta(days=1)
        await db_session.execute(
            update(QFPlayer)
            .where(QFPlayer.player_id == player_id)
            .values(created_at=yesterday)
        )
        await db_session.commit()

        login_response = await client.post("/auth/login", json=payload)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # First claim should succeed
        claim_response = await client.post("/player/claim-daily-bonus", headers=headers)
        assert claim_response.status_code == 200

        # Second claim should fail
        claim_response = await client.post("/player/claim-daily-bonus", headers=headers)
        assert claim_response.status_code == 400
        assert "not available" in claim_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_multiple_logins_preserve_bonus_availability(test_app, db_session):
    """Multiple logins in the same day should not affect bonus availability.

    This is a critical regression test - ensures that repeated logins
    don't prevent the bonus from being claimable.
    """
    payload = {
        "email": f"multilogin_{uuid4().hex[:6]}@example.com",
        "password": "TestPass123!",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
        create_response = await client.post("/player", json=payload)
        player_id = create_response.json()["player_id"]

        # Make eligible
        yesterday = datetime.now(UTC) - timedelta(days=1)
        await db_session.execute(
            update(QFPlayer)
            .where(QFPlayer.player_id == player_id)
            .values(created_at=yesterday)
        )
        await db_session.commit()

        # Login multiple times
        for i in range(5):
            login_response = await client.post("/auth/login", json=payload)
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Check bonus is still available after each login
            balance_response = await client.get("/player/balance", headers=headers)
            balance_data = balance_response.json()
            assert balance_data["daily_bonus_available"] is True, f"Bonus unavailable after login #{i+1}"

        # Final claim should still work
        claim_response = await client.post("/player/claim-daily-bonus", headers=headers)
        assert claim_response.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_endpoint_includes_bonus_status(test_app, db_session):
    """The /player/dashboard endpoint should include daily_bonus_available.

    This ensures the frontend gets the data it needs to show the treasure chest.
    """
    payload = {
        "email": f"dashboard_{uuid4().hex[:6]}@example.com",
        "password": "TestPass123!",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
        create_response = await client.post("/player", json=payload)
        player_id = create_response.json()["player_id"]

        # Make eligible
        yesterday = datetime.now(UTC) - timedelta(days=1)
        await db_session.execute(
            update(QFPlayer)
            .where(QFPlayer.player_id == player_id)
            .values(created_at=yesterday)
        )
        await db_session.commit()

        login_response = await client.post("/auth/login", json=payload)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check dashboard endpoint
        dashboard_response = await client.get("/player/dashboard", headers=headers)
        assert dashboard_response.status_code == 200
        dashboard_data = dashboard_response.json()

        # Verify player data includes bonus information
        assert "player" in dashboard_data
        player_data = dashboard_data["player"]
        assert "daily_bonus_available" in player_data
        assert "daily_bonus_amount" in player_data
        assert player_data["daily_bonus_available"] is True
        assert player_data["daily_bonus_amount"] == settings.daily_bonus_amount


@pytest.mark.asyncio
async def test_bonus_available_next_day_after_claiming(test_app, db_session):
    """After claiming bonus, it should be available again the next day."""
    from backend.services import AuthService
    from backend.utils.model_registry import GameType

    # Create player
    auth_service = AuthService(db_session, game_type=GameType.QF)
    email = f"nextday_{uuid4().hex[:6]}@example.com"
    player = await auth_service.register_player(email, "TestPass123!")

    # Set created_at to 2 days ago
    two_days_ago = datetime.now(UTC) - timedelta(days=2)
    await db_session.execute(
        update(QFPlayer)
        .where(QFPlayer.player_id == player.player_id)
        .values(created_at=two_days_ago)
    )
    await db_session.commit()
    await db_session.refresh(player)

    # Claim bonus for yesterday
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    bonus_yesterday = QFDailyBonus(
        player_id=player.player_id,
        amount=100,
        date=yesterday,
    )
    db_session.add(bonus_yesterday)
    await db_session.commit()

    # Check that bonus is available today
    player_service = QFPlayerService(db_session)
    is_available = await player_service.is_daily_bonus_available(player)
    assert is_available is True

    # Claim today's bonus
    transaction_service = TransactionService(db_session, GameType.QF)
    amount = await player_service.claim_daily_bonus(player, transaction_service)
    assert amount == 100

    # Should not be available anymore today
    is_available = await player_service.is_daily_bonus_available(player)
    assert is_available is False

    # Verify two separate DailyBonus records exist
    result = await db_session.execute(
        select(QFDailyBonus).where(QFDailyBonus.player_id == player.player_id)
    )
    all_bonuses = result.scalars().all()
    assert len(all_bonuses) == 2
    bonus_dates = {b.date for b in all_bonuses}
    assert yesterday in bonus_dates
    assert datetime.now(UTC).date() in bonus_dates
