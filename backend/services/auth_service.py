"""Authentication and authorization helpers."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.player import Player
from backend.models.refresh_token import RefreshToken
from backend.services.player_service import PlayerService
from backend.services.username_service import canonicalize_username, normalize_username
from backend.utils.simple_jwt import (
    encode_jwt,
    decode_jwt,
    ExpiredSignatureError,
    InvalidTokenError,
)
from backend.utils.passwords import hash_password, verify_password

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    """Raised when authentication fails."""


class AuthService:
    """Service responsible for credential management and JWT issuance."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.player_service = PlayerService(db)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register_player(self, email: str, password: str) -> Player:
        """Create a new player with provided credentials."""
        from backend.services.username_service import UsernameService

        email_normalized = email.strip().lower()
        password_hash = hash_password(password)

        # Generate unique username and pseudonym for this player
        username_service = UsernameService(self.db)
        username_display, username_canonical = await username_service.generate_unique_username()
        pseudonym_display, pseudonym_canonical = await username_service.generate_unique_username()

        try:
            player = await self.player_service.create_player(
                username=username_display,
                email=email_normalized,
                password_hash=password_hash,
                pseudonym=pseudonym_display,
                pseudonym_canonical=pseudonym_canonical,
            )
            logger.info("Created player %s via credential signup with username %s and pseudonym %s", player.player_id, username_display, pseudonym_display)
            return player
        except ValueError as exc:
            message = str(exc)
            if message == "username_taken":
                # This should be extremely rare since we generate unique usernames
                raise AuthError("The system could not generate a unique username, please try again") from exc
            if message == "email_taken":
                raise AuthError("An account with this email already exists") from exc
            if message == "invalid_username":
                raise AuthError("The chosen username is invalid") from exc
            raise

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    async def authenticate_player(self, email: str, password: str) -> Player:
        """Authenticate a player using email and password."""
        email_normalized = email.strip().lower()
        if not email_normalized:
            raise AuthError("Email/password combination is invalid")

        result = await self.db.execute(
            select(Player).where(Player.email == email_normalized)
        )
        player = result.scalar_one_or_none()
        if not player or not verify_password(password, player.password_hash):
            raise AuthError("Email/password combination is invalid")

        return player

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------
    def _access_token_payload(self, player: Player) -> dict[str, str]:
        expire = datetime.now(UTC) + timedelta(minutes=self.settings.access_token_exp_minutes)
        return {
            "sub": str(player.player_id),
            "username": player.username,
            "exp": int(expire.timestamp()),
        }

    def create_access_token(self, player: Player) -> tuple[str, int]:
        payload = self._access_token_payload(player)
        token = encode_jwt(payload, self.settings.secret_key, algorithm=self.settings.jwt_algorithm)
        expires_in = self.settings.access_token_exp_minutes * 60
        return token, expires_in

    async def _store_refresh_token(self, player: Player, raw_token: str, expires_at: datetime) -> RefreshToken:
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        refresh_token = RefreshToken(
            token_id=uuid.uuid4(),
            player_id=player.player_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(refresh_token)
        return refresh_token

    async def revoke_refresh_token(self, raw_token: str) -> None:
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        refresh_token = result.scalar_one_or_none()
        if refresh_token:
            refresh_token.revoked_at = datetime.now(UTC)
            await self.db.commit()

    async def revoke_all_refresh_tokens(self, player_id: uuid.UUID) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.player_id == player_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.db.commit()

    async def issue_tokens(self, player: Player, *, rotate_existing: bool = True) -> tuple[str, str, int]:
        if rotate_existing:
            await self.revoke_all_refresh_tokens(player.player_id)

        access_token, expires_in = self.create_access_token(player)
        refresh_expires_at = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_exp_days)
        raw_refresh_token = secrets.token_urlsafe(48)
        await self._store_refresh_token(player, raw_refresh_token, refresh_expires_at)
        await self.db.commit()
        return access_token, raw_refresh_token, expires_in

    def decode_access_token(self, token: str) -> dict[str, str]:
        try:
            payload = decode_jwt(
                token,
                self.settings.secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            return payload
        except ExpiredSignatureError as exc:
            raise AuthError("Token expired error, please try again") from exc
        except InvalidTokenError as exc:
            raise AuthError("Invalid token error, please try again") from exc

    async def exchange_refresh_token(self, raw_token: str) -> tuple[Player, str, str, int]:
        try:
            token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
            result = await self.db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
            refresh_token = result.scalar_one_or_none()
            if not refresh_token or not refresh_token.is_active():
                raise AuthError("Token could not be refreshed, please log in again")

            player = await self.player_service.get_player_by_id(refresh_token.player_id)
            if not player:
                raise AuthError("Token could not be refreshed, please log in again")

            refresh_token.revoked_at = datetime.now(UTC)

            access_token, expires_in = self.create_access_token(player)
            new_refresh_token_value = secrets.token_urlsafe(48)
            new_refresh_expires = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_exp_days)
            await self._store_refresh_token(player, new_refresh_token_value, new_refresh_expires)
            await self.db.commit()
            return player, access_token, new_refresh_token_value, expires_in
        except AuthError:
            await self.db.rollback()
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            await self.db.rollback()
            logger.error("Unexpected error exchanging refresh token", exc_info=True)
            raise
