"""Tests for IR authentication and player services."""
import pytest
import uuid
from backend.services.ir.auth_service import IRAuthService
from backend.services.ir.player_service import IRPlayerService
from backend.utils.passwords import hash_password, verify_password
from backend.services.username_service import UsernameService


@pytest.mark.asyncio
async def test_ir_player_creation(db_session):
    """Test creating a new IR player."""
    player_service = IRPlayerService(db_session)
    username_service = UsernameService(db_session)

    email = f"test{uuid.uuid4().hex[:8]}@example.com"
    username, _ = await username_service.generate_unique_username()
    password_hash = hash_password("TestPassword123!")

    player = await player_service.create_player(
        username=username,
        email=email,
        password_hash=password_hash
    )

    assert player is not None
    assert player.email == email
    assert player.username == username
    assert player.is_guest is False
    assert player.wallet == 1000  # Default initial balance
    assert player.vault == 0


@pytest.mark.asyncio
async def test_ir_guest_player_creation(db_session):
    """Test creating a guest IR player."""
    player_service = IRPlayerService(db_session)

    player, _ = await player_service.register_guest()

    assert player is not None
    assert player.is_guest is True
    assert player.wallet == 1000
    assert player.vault == 0
    assert player.username is not None


@pytest.mark.asyncio
async def test_ir_guest_upgrade_to_full(db_session):
    """Test upgrading guest account to full account."""
    player_service = IRPlayerService(db_session)

    # Create guest
    guest, _ = await player_service.register_guest()
    assert guest.is_guest is True

    # Upgrade to full
    email = f"upgraded{uuid.uuid4().hex[:8]}@example.com"

    upgraded = await player_service.upgrade_guest_to_full(
        guest, email, hash_password("NewPassword123!")
    )

    assert upgraded.is_guest is False
    assert upgraded.email == email
    assert verify_password("NewPassword123!", upgraded.password_hash)


@pytest.mark.asyncio
async def test_ir_get_player_by_email(db_session):
    """Test retrieving player by email."""
    player_service = IRPlayerService(db_session)
    username_service = UsernameService(db_session)

    email = f"lookup{uuid.uuid4().hex[:8]}@example.com"
    username, _ = await username_service.generate_unique_username()
    password_hash = hash_password("TestPassword123!")

    created_player = await player_service.create_player(
        username=username,
        email=email,
        password_hash=password_hash
    )

    # Lookup player
    found_player = await player_service.get_player_by_email(email)

    assert found_player is not None
    assert found_player.player_id == created_player.player_id
    assert found_player.email == email


@pytest.mark.asyncio
async def test_ir_get_player_by_id(db_session):
    """Test retrieving player by ID."""
    player_service = IRPlayerService(db_session)
    username_service = UsernameService(db_session)

    email = f"lookup{uuid.uuid4().hex[:8]}@example.com"
    username, _ = await username_service.generate_unique_username()
    password_hash = hash_password("TestPassword123!")

    created_player = await player_service.create_player(
        username=username,
        email=email,
        password_hash=password_hash
    )

    # Lookup player
    found_player = await player_service.get_player_by_id(created_player.player_id)

    assert found_player is not None
    assert found_player.player_id == created_player.player_id


@pytest.mark.asyncio
async def test_ir_duplicate_email_prevention(db_session):
    """Test that duplicate emails are not allowed."""
    player_service = IRPlayerService(db_session)
    username_service = UsernameService(db_session)

    email = f"unique{uuid.uuid4().hex[:8]}@example.com"
    username1, _ = await username_service.generate_unique_username()
    username2, _ = await username_service.generate_unique_username()
    password_hash = hash_password("TestPassword123!")

    # Create first player
    await player_service.create_player(
        username=username1,
        email=email,
        password_hash=password_hash
    )

    # Try to create second player with same email
    with pytest.raises(Exception):  # Should raise error
        await player_service.create_player(
            username=username2,
            email=email,
            password_hash=password_hash
        )


@pytest.mark.asyncio
async def test_ir_auth_registration(db_session):
    """Test registering through auth service."""
    auth_service = IRAuthService(db_session)

    username = f"player{uuid.uuid4().hex[:8]}"
    email = f"authtest{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"

    player, token = await auth_service.register(
        username=username,
        email=email,
        password=password
    )

    assert player is not None
    assert player.email == email
    assert token is not None
    assert len(token) > 0


@pytest.mark.asyncio
async def test_ir_auth_login(db_session):
    """Test login through auth service."""
    auth_service = IRAuthService(db_session)

    username = f"player{uuid.uuid4().hex[:8]}"
    email = f"login{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"

    # Register first
    player, _ = await auth_service.register(
        username=username,
        email=email,
        password=password
    )

    # Login
    logged_in_player, token = await auth_service.login(
        username=username,
        password=password
    )

    assert logged_in_player.player_id == player.player_id
    assert token is not None


@pytest.mark.asyncio
async def test_ir_auth_invalid_login(db_session):
    """Test that invalid login fails."""
    auth_service = IRAuthService(db_session)

    # Try to login with non-existent username
    with pytest.raises(Exception):  # Should raise IRAuthError
        await auth_service.login(
            username="nonexistent",
            password="password"
        )


@pytest.mark.asyncio
async def test_ir_auth_wrong_password(db_session):
    """Test that wrong password fails."""
    auth_service = IRAuthService(db_session)

    username = f"player{uuid.uuid4().hex[:8]}"
    email = f"wrongpwd{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"

    # Register
    await auth_service.register(
        username=username,
        email=email,
        password=password
    )

    # Try to login with wrong password
    with pytest.raises(Exception):  # Should raise IRAuthError
        await auth_service.login(
            username=username,
            password="WrongPassword123!"
        )


@pytest.mark.asyncio
async def test_ir_auth_refresh_token(db_session):
    """Test refresh token generation and verification."""
    auth_service = IRAuthService(db_session)

    username = f"player{uuid.uuid4().hex[:8]}"
    email = f"refresh{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"

    # Register
    player, _ = await auth_service.register(
        username=username,
        email=email,
        password=password
    )

    # Create refresh token
    refresh_token = await auth_service.create_refresh_token(player.player_id)
    assert refresh_token is not None
    assert len(refresh_token) > 0

    # Use refresh token to get new access token
    new_access_token = await auth_service.refresh_access_token(refresh_token)
    assert new_access_token is not None
    assert len(new_access_token) > 0


@pytest.mark.asyncio
async def test_ir_auth_verify_access_token(db_session):
    """Test verifying access tokens."""
    auth_service = IRAuthService(db_session)

    username = f"player{uuid.uuid4().hex[:8]}"
    email = f"verify{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"

    # Register
    player, token = await auth_service.register(
        username=username,
        email=email,
        password=password
    )

    # Verify token
    player_id = await auth_service.verify_access_token(token)

    assert player_id == str(player.player_id)


@pytest.mark.asyncio
async def test_ir_invalid_token_verification(db_session):
    """Test that invalid tokens are rejected."""
    auth_service = IRAuthService(db_session)

    invalid_token = "invalid.token.here"

    # Should raise error for invalid token
    with pytest.raises(Exception):  # Should raise IRAuthError
        await auth_service.verify_access_token(invalid_token)


@pytest.mark.asyncio
async def test_ir_password_verification(db_session):
    """Test password hashing and verification."""
    player_service = IRPlayerService(db_session)

    email = f"pwd{uuid.uuid4().hex[:8]}@example.com"
    username = f"pwduser{uuid.uuid4().hex[:8]}"
    raw_password = "TestPassword123!"
    password_hash = hash_password(raw_password)

    player = await player_service.create_player(
        username=username,
        email=email,
        password_hash=password_hash
    )

    # Verify password
    assert verify_password(raw_password, player.password_hash)
    assert not verify_password("WrongPassword123!", player.password_hash)
