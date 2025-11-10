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
from backend.utils.passwords import (
    hash_password,
    verify_password,
    validate_password_strength,
    PasswordValidationError,
)

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
    async def register_guest(self) -> tuple[Player, str]:
        """Create a guest account with auto-generated credentials.

        Returns:
            tuple[Player, str]: The created player and the auto-generated password
        """
        from backend.services.username_service import UsernameService
        from backend.services.quest_service import QuestService
        import random

        # Generate random 4-digit number for email
        random_digits = str(random.randint(1000, 9999))
        guest_email = f"guest{random_digits}@quipflip.xyz"
        guest_password = "QuipGuest"

        password_hash = hash_password(guest_password)

        # Generate unique username for this player
        username_service = UsernameService(self.db)
        username_display, username_canonical = await username_service.generate_unique_username()

        # Try to create the guest account, retry with new email if collision
        max_retries = 10
        for attempt in range(max_retries):
            try:
                player = await self.player_service.create_player(
                    username=username_display,
                    email=guest_email,
                    password_hash=password_hash,
                )
                # Mark as guest after creation
                player.is_guest = True
                await self.db.commit()
                await self.db.refresh(player)

                logger.info(f"Created guest player {player.player_id} with email {guest_email}")

                # Initialize starter quests for new guest
                quest_service = QuestService(self.db)
                await quest_service.initialize_quests_for_player(player.player_id)
                logger.info(f"Initialized starter quests for guest {player.player_id}")

                return player, guest_password
            except ValueError as exc:
                message = str(exc)
                if message == "email_taken" and attempt < max_retries - 1:
                    # Generate new random number and retry
                    random_digits = str(random.randint(1000, 9999))
                    guest_email = f"guest{random_digits}@quipflip.xyz"
                    continue
                elif message == "username_taken":
                    raise AuthError("username_generation_failed") from exc
                elif message == "email_taken":
                    raise AuthError("guest_email_generation_failed") from exc
                elif message == "invalid_username":
                    raise AuthError("invalid_username") from exc
                raise

        raise AuthError("guest_email_generation_failed")

    async def register_player(self, email: str, password: str) -> Player:
        """Create a new player with provided credentials."""
        from backend.services.username_service import UsernameService
        from backend.services.quest_service import QuestService

        email_normalized = email.strip().lower()
        try:
            validate_password_strength(password)
        except PasswordValidationError as exc:
            raise AuthError(str(exc)) from exc

        password_hash = hash_password(password)

        # Generate unique username for this player
        username_service = UsernameService(self.db)
        username_display, username_canonical = await username_service.generate_unique_username()

        try:
            player = await self.player_service.create_player(
                username=username_display,
                email=email_normalized,
                password_hash=password_hash,
            )
            logger.info(
                f"Created player {player.player_id} via credential signup with username {username_display}"
            )

            # Initialize starter quests for new player
            quest_service = QuestService(self.db)
            await quest_service.initialize_quests_for_player(player.player_id)
            logger.info(f"Initialized starter quests for player {player.player_id}")

            return player
        except ValueError as exc:
            message = str(exc)
            if message == "username_taken":
                # This should be extremely rare since we generate unique usernames
                raise AuthError("username_generation_failed") from exc
            if message == "email_taken":
                raise AuthError("email_taken") from exc
            if message == "invalid_username":
                raise AuthError("invalid_username") from exc
            raise

    async def upgrade_guest(self, player: Player, email: str, password: str) -> Player:
        """Upgrade a guest account to a full account.

        Args:
            player: The guest player to upgrade
            email: New email for the account
            password: New password for the account

        Returns:
            Player: The upgraded player

        Raises:
            AuthError: If player is not a guest, email is taken, or password is invalid
        """
        if not player.is_guest:
            raise AuthError("not_a_guest")

        email_normalized = email.strip().lower()

        # Validate password strength
        try:
            validate_password_strength(password)
        except PasswordValidationError as exc:
            raise AuthError(str(exc)) from exc

        # Check if email is already taken
        existing = await self.player_service.get_player_by_email(email_normalized)
        if existing and existing.player_id != player.player_id:
            raise AuthError("email_taken")

        # Update player credentials
        player.email = email_normalized
        player.password_hash = hash_password(password)
        player.is_guest = False

        try:
            await self.db.commit()
            await self.db.refresh(player)
            logger.info(f"Upgraded guest {player.player_id} to full account with email {email_normalized}")
            return player
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to upgrade guest {player.player_id}: {exc}")
            raise AuthError("upgrade_failed") from exc

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

        self.player_service.apply_admin_status(player)

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
