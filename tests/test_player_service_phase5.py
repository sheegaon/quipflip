import uuid
from datetime import UTC, datetime, timedelta

import pytest

from backend.config import get_settings
from backend.models.player import Player
from backend.services.player_service import PlayerService, PlayerServiceError
from backend.services.username_service import canonicalize_username
from backend.utils.model_registry import GameType
from backend.utils.passwords import hash_password


@pytest.mark.asyncio
async def test_login_provisions_game_data_with_initial_balance(db_session):
    service = PlayerService(db_session)
    password = "Phase5!Password"
    player = Player(
        player_id=str(uuid.uuid4()),
        username="phase5-user",
        username_canonical=canonicalize_username("phase5-user"),
        email="phase5-user@example.com",
        password_hash=hash_password(password),
        created_at=datetime.now(UTC),
        is_guest=False,
        is_admin=False,
    )
    db_session.add(player)
    await db_session.commit()

    logged_in = await service.login_player(
        password=password,
        email=player.email,
        game_type=GameType.QF,
    )

    await db_session.refresh(logged_in)
    assert logged_in.qf_player_data is not None
    assert logged_in.qf_player_data.wallet == get_settings().qf_starting_wallet
    assert logged_in.qf_player_data.vault == 0


@pytest.mark.asyncio
async def test_login_respects_lockout(db_session):
    service = PlayerService(db_session)
    password = "LockedOut!Password"
    player = Player(
        player_id=str(uuid.uuid4()),
        username="locked-player",
        username_canonical=canonicalize_username("locked-player"),
        email="locked@example.com",
        password_hash=hash_password(password),
        created_at=datetime.now(UTC),
        locked_until=datetime.now(UTC) + timedelta(hours=1),
        is_guest=False,
        is_admin=False,
    )
    db_session.add(player)
    await db_session.commit()

    with pytest.raises(PlayerServiceError) as exc_info:
        await service.login_player(password=password, email=player.email)

    assert str(exc_info.value) == "account_locked"


@pytest.mark.asyncio
async def test_login_by_username_applies_admin_flag(db_session):
    service = PlayerService(db_session)
    password = "Admin!Password"
    admin_email = "tfishman@gmail.com"
    player = Player(
        player_id=str(uuid.uuid4()),
        username="AdminUser",
        username_canonical=canonicalize_username("AdminUser"),
        email=admin_email,
        password_hash=hash_password(password),
        created_at=datetime.now(UTC),
        is_guest=False,
        is_admin=False,
    )
    db_session.add(player)
    await db_session.commit()

    logged_in = await service.login_player(password=password, username="AdminUser")

    assert logged_in.is_admin is True
    assert logged_in.email == admin_email
