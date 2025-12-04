"""Global player service orchestrating cross-game auth and data provisioning."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.player import Player
from backend.models.qf.player_data import QFPlayerData
from backend.models.ir.player_data import IRPlayerData
from backend.models.mm.player_data import MMPlayerData
from backend.models.tl.player_data import TLPlayerData
from backend.services.player_service_base import PlayerServiceBase
from backend.services.username_service import UsernameService, canonicalize_username
from backend.utils.model_registry import GameType
from backend.utils.passwords import (
    PasswordValidationError,
    hash_password,
    validate_password_strength,
    verify_password,
)

logger = logging.getLogger(__name__)


class PlayerServiceError(RuntimeError):
    """Raised when player operations fail."""


class PlayerService:
    """Global player service coordinating authentication and per-game data creation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self._player_services: Dict[GameType, PlayerServiceBase] = {}

    def _get_player_service(self, game_type: GameType | None) -> PlayerServiceBase | None:
        """Return a cached per-game player service instance when a game is provided."""
        if game_type is None:
            return None

        if game_type not in self._player_services:
            if game_type == GameType.QF:
                from backend.services.qf.player_service import QFPlayerService

                self._player_services[game_type] = QFPlayerService(self.db)
            elif game_type == GameType.IR:
                from backend.services.ir.player_service import IRPlayerService

                self._player_services[game_type] = IRPlayerService(self.db)
            elif game_type == GameType.MM:
                from backend.services.mm.player_service import MMPlayerService

                self._player_services[game_type] = MMPlayerService(self.db)
            elif game_type == GameType.TL:
                from backend.services.tl.player_service import TLPlayerService

                self._player_services[game_type] = TLPlayerService(self.db)
            else:
                raise PlayerServiceError(f"Unsupported game type: {game_type}")

        return self._player_services[game_type]

    def _player_data_model(self, game_type: GameType) -> type[Any]:
        if game_type == GameType.QF:
            return QFPlayerData
        if game_type == GameType.IR:
            return IRPlayerData
        if game_type == GameType.MM:
            return MMPlayerData
        if game_type == GameType.TL:
            return TLPlayerData
        raise PlayerServiceError(f"Unsupported game type: {game_type}")

    def apply_admin_status(self, player: Player | None) -> Player | None:
        """Ensure the player's admin flag reflects configuration."""
        if not player:
            return None
        player.is_admin = self.settings.is_admin_email(player.email)
        return player

    async def _get_player_by_email(self, email: str) -> Player | None:
        normalized_email = email.strip().lower()
        result = await self.db.execute(select(Player).where(Player.email == normalized_email))
        return self.apply_admin_status(result.scalar_one_or_none())

    async def _get_player_by_username(self, username: str) -> Player | None:
        canonical = canonicalize_username(username)
        result = await self.db.execute(
            select(Player).where(Player.username_canonical == canonical)
        )
        return self.apply_admin_status(result.scalar_one_or_none())

    async def ensure_player_data(self, player: Player, game_type: GameType) -> Any:
        """Ensure the player has per-game data, creating it with defaults if missing."""
        try:
            existing = player.get_game_data(game_type)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise PlayerServiceError(str(exc)) from exc

        if existing:
            return existing

        service = self._get_player_service(game_type)
        starting_wallet = service._get_initial_balance() if service else 0  # type: ignore[attr-defined]
        player_data_cls = self._player_data_model(game_type)
        player_data = player_data_cls(player_id=player.player_id, wallet=starting_wallet, vault=0)
        self.db.add(player_data)
        await self.db.commit()
        await self.db.refresh(player_data)
        logger.info("Provisioned %s player data for %s", game_type.value, player.player_id)
        return player_data

    async def snapshot_player_data(self, player: Player, game_type: GameType | None) -> dict[str, Any] | None:
        """Return a lightweight snapshot of per-game data if requested."""
        if not game_type:
            return None
        player_data = await self.ensure_player_data(player, game_type)
        snapshot = {"game_type": game_type.value}
        for field in ("wallet", "vault", "tutorial_completed"):
            if hasattr(player_data, field):
                snapshot[field] = getattr(player_data, field)
        return snapshot

    async def login_player(
        self,
        *,
        password: str,
        email: str | None = None,
        username: str | None = None,
        game_type: GameType | None = None,
    ) -> Player:
        """Authenticate a player and optionally ensure per-game data exists."""
        identifier = email or username
        if not identifier:
            raise PlayerServiceError("missing_credentials")

        player: Optional[Player] = None
        if email:
            player = await self._get_player_by_email(email)
        elif username:
            player = await self._get_player_by_username(username)

        if not player:
            raise PlayerServiceError("invalid_credentials")

        if player.locked_until:
            locked_until = (
                player.locked_until.replace(tzinfo=UTC)
                if player.locked_until.tzinfo is None
                else player.locked_until
            )
            if locked_until > datetime.now(UTC):
                raise PlayerServiceError("account_locked")

        if not verify_password(password, player.password_hash):
            raise PlayerServiceError("invalid_credentials")

        player = self.apply_admin_status(player)

        if game_type:
            await self.ensure_player_data(player, game_type)

        return player

    async def register_guest(self, game_type: GameType) -> tuple[Player, str]:
        """Create a guest account for the provided game."""
        service = self._get_player_service(game_type)
        if not service:
            raise PlayerServiceError("game_type_required")

        return await service.register_guest()

    async def register_player(self, game_type: GameType, email: str, password: str) -> Player:
        """Create a new player with credentials for the given game."""
        service = self._get_player_service(game_type)
        if not service:
            raise PlayerServiceError("game_type_required")

        try:
            validate_password_strength(password)
        except PasswordValidationError as exc:
            raise PlayerServiceError(str(exc)) from exc

        username_service = UsernameService(self.db, game_type=game_type)
        username_display, _ = await username_service.generate_unique_username()
        password_hash = hash_password(password)
        player = await service.create_player(
            username=username_display,
            email=email.strip().lower(),
            password_hash=password_hash,
        )
        return self.apply_admin_status(player)

    async def upgrade_guest(self, player: Player, email: str, password: str) -> Player:
        """Upgrade a guest account to a full account with credentials."""
        if not player.is_guest:
            raise PlayerServiceError("not_a_guest")

        try:
            validate_password_strength(password)
        except PasswordValidationError as exc:
            raise PlayerServiceError(str(exc)) from exc

        email_normalized = email.strip().lower()
        existing = await self.db.execute(select(Player).where(Player.email == email_normalized))
        if existing.scalar_one_or_none() and email_normalized != player.email:
            raise PlayerServiceError("email_taken")

        player.email = email_normalized
        player.password_hash = hash_password(password)
        player.is_guest = False
        await self.db.commit()
        await self.db.refresh(player)
        return self.apply_admin_status(player)

    async def get_player_from_refresh_token(self, refresh_token: str) -> Player | None:
        """Return the player linked to the provided refresh token without rotation."""
        import hashlib
        from backend.models.refresh_token import RefreshToken

        token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()
        if not token or not token.is_active():
            return None

        player_result = await self.db.execute(
            select(Player).where(Player.player_id == token.player_id)
        )
        return self.apply_admin_status(player_result.scalar_one_or_none())
