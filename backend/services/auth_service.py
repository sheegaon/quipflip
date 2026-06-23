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
from backend.models.player_base import PlayerBase
from backend.models.refresh_token import RefreshToken
from backend.services.player_service import PlayerService, PlayerServiceError
from backend.utils.passwords import PasswordValidationError, hash_password, validate_password_strength
from backend.services.username_service import UsernameService
from backend.utils.simple_jwt import (
    encode_jwt,
    decode_jwt,
    ExpiredSignatureError,
    InvalidTokenError,
)

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    """Raised when authentication fails."""


class AuthService:
    """Service responsible for credential management and JWT issuance.

    Now unified across all games - uses shared Player and RefreshToken models.
    Game-specific logic is handled through player_service parameter.
    """

    def __init__(self, db: AsyncSession, game_type: GameType | None = None, *, player_service: PlayerService | None = None):
        self.db = db
        self.game_type = game_type
        self.settings = get_settings()

        # Unified models for all games
        self.player_model = Player
        self.refresh_token_model = RefreshToken
        self.player_service = player_service or PlayerService(db)

    def _require_game_type(self) -> GameType:
        if self.game_type is None:
            raise AuthError("game_type_required")
        return self.game_type

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register_guest(self) -> tuple[PlayerBase, str]:
        """Create a guest account with auto-generated credentials.

        Returns:
            tuple[PlayerBase, str]: The created player and the auto-generated password
        """
        game_type = self.game_type or GameType.IR
        try:
            player, guest_password = await self.player_service.register_guest(game_type)
        except PlayerServiceError as exc:
            message = str(exc)
            if message == "username_generation_failed":
                raise AuthError("username_generation_failed") from exc
            if message == "guest_email_generation_failed":
                raise AuthError("guest_email_generation_failed") from exc
            if message == "invalid_username":
                raise AuthError("invalid_username") from exc
            if message == "game_type_required":
                raise AuthError("game_type_required") from exc
            raise

        logger.info(
            f"Created {game_type.value} guest player {player.player_id}"
        )
        return player, guest_password

    async def register_player(
        self,
        email: str,
        password: str,
        username: str | None = None,
    ) -> PlayerBase:
        """Create a new player with provided credentials."""
        game_type = self._require_game_type()

        try:
            validate_password_strength(password)

            if username is None:
                username_service = UsernameService(self.db, game_type=game_type)
                username, _ = await username_service.generate_unique_username()

            service = self.player_service._get_player_service(game_type)
            if service is None:
                raise PlayerServiceError("game_type_required")

            player = await service.create_player(
                username=username,
                email=email,
                password_hash=hash_password(password),
            )
            logger.info(
                f"Created {game_type.value} player {player.player_id} via credential signup"
            )

            if game_type == GameType.QF:
                from backend.services.qf.quest_service import QuestService

                quest_service = QuestService(self.db)
                try:
                    await quest_service.initialize_quests_for_player(player.player_id)
                    logger.info(f"Initialized starter quests for player {player.player_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to initialize quests for player {player.player_id}: {e}",
                        exc_info=True,
                    )

            return player
        except PlayerServiceError as exc:
            message = str(exc)
            if message == "username_taken":
                raise AuthError("username_generation_failed" if username is None else "username_taken") from exc
            if message == "email_taken":
                raise AuthError("email_taken") from exc
            if message == "invalid_username":
                raise AuthError("invalid_username") from exc
            raise AuthError(message) from exc
        except PasswordValidationError as exc:
            raise AuthError(str(exc)) from exc

    async def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        game_type: GameType | None = None,
    ) -> tuple[PlayerBase, str]:
        """Compatibility registration helper used by older IR tests."""

        effective_game_type = game_type or self.game_type or GameType.IR
        compat_service = AuthService(
            self.db,
            game_type=effective_game_type,
            player_service=self.player_service,
        )
        player = await compat_service.register_player(email=email, password=password, username=username)
        access_token, _, _ = await compat_service.issue_tokens(player)
        return player, access_token

    async def login(
        self,
        *,
        username: str | None = None,
        email: str | None = None,
        password: str,
        game_type: GameType | None = None,
    ) -> tuple[Player, str]:
        """Compatibility login helper used by older IR tests."""

        effective_game_type = game_type or self.game_type or GameType.IR
        compat_service = AuthService(
            self.db,
            game_type=effective_game_type,
            player_service=self.player_service,
        )

        if username:
            player = await compat_service.authenticate_player_by_username(username, password)
        elif email:
            player = await compat_service.authenticate_player(email, password)
        else:
            raise AuthError("missing_credentials")

        player.last_login_date = datetime.now(UTC)
        await self.db.commit()

        access_token, _, _ = await compat_service.issue_tokens(player)
        return player, access_token

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
        try:
            upgraded = await self.player_service.upgrade_guest(player, email, password)
            logger.info(
                f"Upgraded guest {player.player_id} to full account with email {upgraded.email}"
            )
            return upgraded
        except PlayerServiceError as exc:
            message = str(exc)
            if message in {"not_a_guest", "email_taken"}:
                raise AuthError(message) from exc
            raise AuthError("upgrade_failed") from exc

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    async def authenticate_player(self, email: str, password: str) -> Player:
        """Authenticate a player using email and password.

        Now uses unified Player model instead of game-specific models.
        """
        try:
            return await self.player_service.login_player(
                email=email, password=password, game_type=self.game_type
            )
        except PlayerServiceError as exc:
            raise AuthError("Email/password combination is invalid") from exc

    async def authenticate_player_by_username(self, username: str, password: str) -> Player:
        """Authenticate a player using username and password.

        Now uses unified Player model instead of game-specific models.
        """
        try:
            return await self.player_service.login_player(
                username=username, password=password, game_type=self.game_type
            )
        except PlayerServiceError as exc:
            raise AuthError("Username/password combination is invalid") from exc

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
        player = result.scalar_one_or_none()
        return self.player_service.apply_admin_status(player)

    async def refresh_tokens(self, raw_token: str) -> Player:
        """Compatibility helper that returns the player linked to a refresh token."""

        player = await self.get_player_from_refresh_token(raw_token)
        if not player:
            raise AuthError("Token could not be refreshed, please log in again")
        return player

    async def create_refresh_token(self, player_id: uuid.UUID | str) -> str:
        """Compatibility helper that persists a standalone refresh token."""

        normalized_player_id: uuid.UUID | str = player_id
        if isinstance(player_id, str):
            try:
                normalized_player_id = uuid.UUID(player_id)
            except ValueError as exc:
                raise AuthError("player_not_found") from exc

        result = await self.db.execute(select(Player).where(Player.player_id == normalized_player_id))
        player = self.player_service.apply_admin_status(result.scalar_one_or_none())
        if not player:
            raise AuthError("player_not_found")

        raw_refresh_token = secrets.token_urlsafe(48)
        refresh_expires_at = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_exp_days)
        await self._store_refresh_token(player, raw_refresh_token, refresh_expires_at)
        await self.db.commit()
        return raw_refresh_token

    async def refresh_access_token(self, raw_token: str) -> str:
        """Compatibility helper that returns a new access token for a refresh token."""

        _, access_token, _, _ = await self.exchange_refresh_token(raw_token)
        return access_token

    async def verify_access_token(self, token: str) -> str:
        """Compatibility helper that returns the subject claim from an access token."""

        payload = self.decode_access_token(token)
        subject = payload.get("sub")
        if not subject:
            raise AuthError("Invalid token error, please try again")
        return subject

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
            player = self.player_service.apply_admin_status(result.scalar_one_or_none())
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
