"""
Tests for AuthService - JWT authentication, token management, and security.
"""

import pytest
from datetime import datetime, timedelta, UTC
import uuid

from backend.models.player import Player
from backend.models.refresh_token import RefreshToken
from backend.services.auth_service import AuthService
from backend.utils.passwords import hash_password
from sqlalchemy import select


@pytest.fixture
async def test_player(db_session):
    """Create a test player with known credentials."""
    test_id = uuid.uuid4().hex[:8]
    player = Player(
        player_id=uuid.uuid4(),
        username=f"auth_test_{test_id}",
        username_canonical=f"auth_test_{test_id}",
        pseudonym=f"AuthTest{test_id}",
        pseudonym_canonical=f"authtest{test_id}",
        email=f"auth_test_{test_id}@test.com",
        password_hash=hash_password("test_password_123"),
        balance=1000,
    )
    db_session.add(player)
    await db_session.commit()
    return player


class TestAuthentication:
    """Test user authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_with_correct_password(self, db_session, test_player):
        """Should authenticate user with correct credentials."""
        auth_service = AuthService(db_session)

        player = await auth_service.authenticate(
            test_player.username,
            "test_password_123"
        )

        assert player is not None
        assert player.player_id == test_player.player_id
        assert player.username == test_player.username

    @pytest.mark.asyncio
    async def test_authenticate_with_wrong_password(self, db_session, test_player):
        """Should reject authentication with wrong password."""
        auth_service = AuthService(db_session)

        player = await auth_service.authenticate(
            test_player.username,
            "wrong_password"
        )

        assert player is None

    @pytest.mark.asyncio
    async def test_authenticate_with_nonexistent_user(self, db_session):
        """Should reject authentication for non-existent user."""
        auth_service = AuthService(db_session)

        player = await auth_service.authenticate(
            "nonexistent_user",
            "any_password"
        )

        assert player is None

    @pytest.mark.asyncio
    async def test_authenticate_case_insensitive_username(self, db_session, test_player):
        """Should authenticate with case-insensitive username."""
        auth_service = AuthService(db_session)

        # Try with different case
        player = await auth_service.authenticate(
            test_player.username.upper(),
            "test_password_123"
        )

        # Should still authenticate because usernames are case-insensitive
        assert player is not None
        assert player.player_id == test_player.player_id


class TestJWTTokenGeneration:
    """Test JWT access token generation."""

    @pytest.mark.asyncio
    async def test_create_access_token(self, db_session, test_player):
        """Should create valid JWT access token."""
        auth_service = AuthService(db_session)

        token = auth_service.create_access_token(test_player.player_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_verify_valid_token(self, db_session, test_player):
        """Should verify and decode valid token."""
        auth_service = AuthService(db_session)

        token = auth_service.create_access_token(test_player.player_id)
        payload = auth_service.verify_token(token)

        assert payload is not None
        assert "player_id" in payload
        assert payload["player_id"] == str(test_player.player_id)

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self, db_session):
        """Should reject invalid token."""
        auth_service = AuthService(db_session)

        payload = auth_service.verify_token("invalid.token.here")

        assert payload is None

    @pytest.mark.asyncio
    async def test_verify_expired_token(self, db_session, test_player):
        """Should reject expired token."""
        auth_service = AuthService(db_session)

        # Create token with very short expiration
        token = auth_service.create_access_token(
            test_player.player_id,
            expires_delta=timedelta(seconds=-1)  # Already expired
        )

        payload = auth_service.verify_token(token)

        assert payload is None


class TestRefreshTokens:
    """Test refresh token management."""

    @pytest.mark.asyncio
    async def test_create_refresh_token(self, db_session, test_player):
        """Should create and store refresh token."""
        auth_service = AuthService(db_session)

        refresh_token = await auth_service.create_refresh_token(test_player.player_id)

        assert refresh_token is not None
        assert isinstance(refresh_token, str)

        # Verify it's stored in database
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.player_id == test_player.player_id)
        )
        db_token = result.scalar_one_or_none()

        assert db_token is not None
        assert db_token.token == refresh_token
        assert db_token.revoked is False

    @pytest.mark.asyncio
    async def test_verify_valid_refresh_token(self, db_session, test_player):
        """Should verify valid refresh token."""
        auth_service = AuthService(db_session)

        refresh_token = await auth_service.create_refresh_token(test_player.player_id)
        is_valid = await auth_service.verify_refresh_token(refresh_token)

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_invalid_refresh_token(self, db_session):
        """Should reject invalid refresh token."""
        auth_service = AuthService(db_session)

        is_valid = await auth_service.verify_refresh_token("invalid_token")

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_revoke_refresh_token(self, db_session, test_player):
        """Should revoke refresh token."""
        auth_service = AuthService(db_session)

        refresh_token = await auth_service.create_refresh_token(test_player.player_id)
        await auth_service.revoke_refresh_token(refresh_token)

        # Should no longer be valid
        is_valid = await auth_service.verify_refresh_token(refresh_token)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_refresh_access_token(self, db_session, test_player):
        """Should create new access token from refresh token."""
        auth_service = AuthService(db_session)

        refresh_token = await auth_service.create_refresh_token(test_player.player_id)
        new_access_token = await auth_service.refresh_access_token(refresh_token)

        assert new_access_token is not None

        # Verify new token is valid
        payload = auth_service.verify_token(new_access_token)
        assert payload is not None
        assert payload["player_id"] == str(test_player.player_id)


class TestTokenExpiration:
    """Test token expiration handling."""

    @pytest.mark.asyncio
    async def test_refresh_token_has_expiration(self, db_session, test_player):
        """Should set expiration date on refresh tokens."""
        auth_service = AuthService(db_session)

        refresh_token = await auth_service.create_refresh_token(test_player.player_id)

        # Check expiration in database
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        db_token = result.scalar_one()

        assert db_token.expires_at is not None
        assert db_token.expires_at > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_expired_refresh_token_rejected(self, db_session, test_player):
        """Should reject expired refresh tokens."""
        auth_service = AuthService(db_session)

        # Create token and manually set it as expired
        refresh_token = await auth_service.create_refresh_token(test_player.player_id)

        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        db_token = result.scalar_one()

        # Set expiration to the past
        db_token.expires_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.commit()

        # Should be invalid now
        is_valid = await auth_service.verify_refresh_token(refresh_token)
        assert is_valid is False


class TestMultipleSessions:
    """Test handling multiple sessions and tokens."""

    @pytest.mark.asyncio
    async def test_multiple_refresh_tokens_per_user(self, db_session, test_player):
        """Should allow multiple active refresh tokens per user."""
        auth_service = AuthService(db_session)

        # Create multiple refresh tokens (different devices/sessions)
        token1 = await auth_service.create_refresh_token(test_player.player_id)
        token2 = await auth_service.create_refresh_token(test_player.player_id)
        token3 = await auth_service.create_refresh_token(test_player.player_id)

        # All should be valid
        assert await auth_service.verify_refresh_token(token1)
        assert await auth_service.verify_refresh_token(token2)
        assert await auth_service.verify_refresh_token(token3)

    @pytest.mark.asyncio
    async def test_revoke_one_token_leaves_others_active(self, db_session, test_player):
        """Should only revoke the specific token, not all user tokens."""
        auth_service = AuthService(db_session)

        token1 = await auth_service.create_refresh_token(test_player.player_id)
        token2 = await auth_service.create_refresh_token(test_player.player_id)

        # Revoke only token1
        await auth_service.revoke_refresh_token(token1)

        # token1 should be invalid, token2 should still be valid
        assert await auth_service.verify_refresh_token(token1) is False
        assert await auth_service.verify_refresh_token(token2) is True

    @pytest.mark.asyncio
    async def test_revoke_all_tokens_for_user(self, db_session, test_player):
        """Should revoke all refresh tokens for a user."""
        auth_service = AuthService(db_session)

        # Create multiple tokens
        token1 = await auth_service.create_refresh_token(test_player.player_id)
        token2 = await auth_service.create_refresh_token(test_player.player_id)
        token3 = await auth_service.create_refresh_token(test_player.player_id)

        # Revoke all tokens for user
        await auth_service.revoke_all_user_tokens(test_player.player_id)

        # All should now be invalid
        assert await auth_service.verify_refresh_token(token1) is False
        assert await auth_service.verify_refresh_token(token2) is False
        assert await auth_service.verify_refresh_token(token3) is False


class TestSecurity:
    """Test security features and edge cases."""

    @pytest.mark.asyncio
    async def test_token_contains_no_sensitive_data(self, db_session, test_player):
        """Should not include sensitive data in token payload."""
        auth_service = AuthService(db_session)

        token = auth_service.create_access_token(test_player.player_id)
        payload = auth_service.verify_token(token)

        # Should not contain password or other sensitive fields
        assert "password" not in payload
        assert "password_hash" not in payload
        assert "email" not in payload  # Unless intentionally included

    @pytest.mark.asyncio
    async def test_different_users_get_different_tokens(self, db_session):
        """Should generate different tokens for different users."""
        auth_service = AuthService(db_session)

        test_id = uuid.uuid4().hex[:8]
        player1 = Player(
            player_id=uuid.uuid4(),
            username=f"user1_{test_id}",
            username_canonical=f"user1_{test_id}",
            pseudonym=f"User1{test_id}",
            pseudonym_canonical=f"user1{test_id}",
            email=f"user1_{test_id}@test.com",
            password_hash=hash_password("password"),
            balance=1000,
        )
        player2 = Player(
            player_id=uuid.uuid4(),
            username=f"user2_{test_id}",
            username_canonical=f"user2_{test_id}",
            pseudonym=f"User2{test_id}",
            pseudonym_canonical=f"user2{test_id}",
            email=f"user2_{test_id}@test.com",
            password_hash=hash_password("password"),
            balance=1000,
        )
        db_session.add_all([player1, player2])
        await db_session.commit()

        token1 = auth_service.create_access_token(player1.player_id)
        token2 = auth_service.create_access_token(player2.player_id)

        assert token1 != token2

        # Verify each token belongs to correct user
        payload1 = auth_service.verify_token(token1)
        payload2 = auth_service.verify_token(token2)

        assert payload1["player_id"] == str(player1.player_id)
        assert payload2["player_id"] == str(player2.player_id)
