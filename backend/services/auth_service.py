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
from backend.utils.model_registry import GameType
from backend.models.player import Player
from backend.models.refresh_token import RefreshToken
from backend.services.username_service import canonicalize_username
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
    """Service responsible for credential management and JWT issuance.

    Now unified across all games - uses shared Player and RefreshToken models.
    Game-specific logic is handled through player_service parameter.
    """

    def __init__(self, db: AsyncSession, game_type: GameType = GameType.QF):
        self.db = db
        self.game_type = game_type
        self.settings = get_settings()

        # Instantiate the correct player service based on game type
        # Player service is still game-specific for creating game-specific player_data
        if game_type == GameType.QF:
            from backend.services.qf.player_service import QFPlayerService as PlayerService
        elif game_type == GameType.IR:
            from backend.services.ir.player_service import IRPlayerService as PlayerService
        elif game_type == GameType.MM:
            from backend.services.mm.player_service import MMPlayerService as PlayerService
        else:
            raise ValueError(f"Unsupported game type: {game_type}")

        # Unified models for all games
        self.player_model = Player
        self.refresh_token_model = RefreshToken
        self.player_service = PlayerService(db)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register_guest(self) -> tuple[PlayerBase, str]:
        """Create a guest account with auto-generated credentials.

        Returns:
            tuple[PlayerBase, str]: The created player and the auto-generated password
        """
        from backend.services.username_service import UsernameService
        import random

        # Generate random 4-digit number for email
        random_digits = str(random.randint(1000, 9999))
        guest_domain = self.player_service.get_guest_domain()
        guest_email = f"guest{random_digits}@{guest_domain}"
        guest_password = self.player_service.get_guest_password()

        password_hash = hash_password(guest_password)

        # Generate unique username for this player
        username_service = UsernameService(self.db, game_type=self.game_type)
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

                logger.info(f"Created {self.game_type.value} guest player {player.player_id} with email {guest_email}")

                return player, guest_password
            except ValueError as exc:
                message = str(exc)
                if message == "email_taken" and attempt < max_retries - 1:
                    # Generate new random number and retry
                    random_digits = str(random.randint(1000, 9999))
                    guest_email = f"guest{random_digits}@{guest_domain}"
                    continue
                elif message == "username_taken":
                    raise AuthError("username_generation_failed") from exc
                elif message == "email_taken":
                    raise AuthError("guest_email_generation_failed") from exc
                elif message == "invalid_username":
                    raise AuthError("invalid_username") from exc
                raise

        raise AuthError("guest_email_generation_failed")

    async def register_player(self, email: str, password: str) -> PlayerBase:
        """Create a new player with provided credentials."""
        from backend.services.username_service import UsernameService

        email_normalized = email.strip().lower()
        try:
            validate_password_strength(password)
        except PasswordValidationError as exc:
            raise AuthError(str(exc)) from exc

        password_hash = hash_password(password)

        # Generate unique username for this player
        username_service = UsernameService(self.db, game_type=self.game_type)
        username_display, username_canonical = await username_service.generate_unique_username()

        try:
            player = await self.player_service.create_player(
                username=username_display,
                email=email_normalized,
                password_hash=password_hash,
            )
            logger.info(
                f"Created {self.game_type.value} player {player.player_id} via credential signup with username "
                f"{username_display}"
            )

            # Initialize game-specific content for new player
            if self.game_type == GameType.QF:
                from backend.services.qf.quest_service import QuestService
                quest_service = QuestService(self.db)
                try:
                    await quest_service.initialize_quests_for_player(player.player_id)
                    logger.info(f"Initialized starter quests for player {player.player_id}")
                except Exception as e:
                    logger.error(f"Failed to initialize quests for player {player.player_id}: {e}", exc_info=True)
                    # Don't fail account creation if quest initialization fails
                    # The backup script will create missing quests later if needed

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

        # Check if email is already taken in unified players table
        existing = await self.db.execute(
            select(Player).where(Player.email == email_normalized)
        )
        existing_player = existing.scalar_one_or_none()
        if existing_player and existing_player.player_id != player.player_id:
            raise AuthError("email_taken")

        # Update player credentials
        player.email = email_normalized
        player.password_hash = hash_password(password)
        player.is_guest = False

        try:
            await self.db.commit()
            await self.db.refresh(player)
            logger.info(f"Upgraded {self.game_type.value} guest {player.player_id} to full account with email "
                        f"{email_normalized}")
            return player
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Failed to upgrade {self.game_type.value} guest {player.player_id}: {exc}")
            raise AuthError("upgrade_failed") from exc

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    async def authenticate_player(self, email: str, password: str) -> Player:
        """Authenticate a player using email and password.

        Now uses unified Player model instead of game-specific models.
        """
        email_normalized = email.strip().lower()
        if not email_normalized:
            raise AuthError("Email/password combination is invalid")

        # Use unified Player model for authentication
        result = await self.db.execute(
            select(Player).where(Player.email == email_normalized)
        )
        player = result.scalar_one_or_none()
        if not player or not verify_password(password, player.password_hash):
            raise AuthError("Email/password combination is invalid")

        self.player_service.apply_admin_status(player)

        return player

    async def authenticate_player_by_username(self, username: str, password: str) -> Player:
        """Authenticate a player using username and password.

        Now uses unified Player model instead of game-specific models.
        """
        username_stripped = username.strip()
        if not username_stripped:
            raise AuthError("Username/password combination is invalid")

        # Convert to canonical form for lookup
        username_canonical = canonicalize_username(username_stripped)
        if not username_canonical:
            raise AuthError("Username/password combination is invalid")

        # Use unified Player model for authentication
        result = await self.db.execute(
            select(Player).where(Player.username_canonical == username_canonical)
        )
        player = result.scalar_one_or_none()
        if not player or not verify_password(password, player.password_hash):
            raise AuthError("Username/password combination is invalid")

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

    def create_short_lived_token(self, player: Player, expires_seconds: int) -> tuple[str, int]:
        """Create a short-lived access token with custom expiration (for WebSocket auth).

        Args:
            player: The player to create the token for
            expires_seconds: Token lifetime in seconds

        Returns:
            Tuple of (token, expires_in_seconds)
        """
        expire = datetime.now(UTC) + timedelta(seconds=expires_seconds)
        payload = {
            "sub": str(player.player_id),
            "username": player.username,
            "exp": int(expire.timestamp()),
        }
        token = encode_jwt(payload, self.settings.secret_key, algorithm=self.settings.jwt_algorithm)
        return token, expires_seconds

    async def _store_refresh_token(self, player: Player, raw_token: str, expires_at: datetime) -> RefreshToken:
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        refresh_token = self.refresh_token_model(
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
            select(self.refresh_token_model).where(self.refresh_token_model.token_hash == token_hash)
        )
        refresh_token = result.scalar_one_or_none()
        if refresh_token:
            refresh_token.revoked_at = datetime.now(UTC)
            await self.db.commit()

    async def revoke_all_refresh_tokens(self, player_id: uuid.UUID) -> None:
        await self.db.execute(
            update(self.refresh_token_model)
            .where(self.refresh_token_model.player_id == player_id)
            .where(self.refresh_token_model.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self.db.commit()

    async def get_player_from_refresh_token(self, raw_token: str) -> Player | None:
        """Return the unified player linked to the given refresh token without rotating it."""
        if not raw_token:
            return None

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        result = await self.db.execute(
            select(self.refresh_token_model).where(self.refresh_token_model.token_hash == token_hash)
        )
        refresh_token = result.scalar_one_or_none()
        if not refresh_token or not refresh_token.is_active():
            return None

        # Query unified Player model
        result = await self.db.execute(
            select(Player).where(Player.player_id == refresh_token.player_id)
        )
        return result.scalar_one_or_none()

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
                select(self.refresh_token_model).where(self.refresh_token_model.token_hash == token_hash)
            )
            refresh_token = result.scalar_one_or_none()
            if not refresh_token or not refresh_token.is_active():
                raise AuthError("Token could not be refreshed, please log in again")

            # Query unified Player model
            result = await self.db.execute(
                select(Player).where(Player.player_id == refresh_token.player_id)
            )
            player = result.scalar_one_or_none()
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
        except Exception:  # pragma: no cover - defensive logging
            await self.db.rollback()
            logger.error("Unexpected error exchanging refresh token", exc_info=True)
            raise
