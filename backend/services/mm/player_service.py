"""Player service for Meme Mint leveraging shared player base logic."""

import logging
from datetime import UTC, datetime
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.player import Player
from backend.models.mm.player_data import MMPlayerData
from backend.services.mm.system_config_service import MMSystemConfigService
from backend.services.player_service_base import PlayerServiceBase, PlayerError
from backend.services.username_service import (
    UsernameService,
    canonicalize_username,
    normalize_username,
)
from backend.utils.model_registry import GameType

logger = logging.getLogger(__name__)
settings = get_settings()


class MMPlayerService(PlayerServiceBase):
    """Service for managing Meme Mint players."""

    def __init__(self, db: AsyncSession, config_service: MMSystemConfigService | None = None):
        super().__init__(db)
        self.config_service = config_service or MMSystemConfigService(db)

    @property
    def player_model(self):
        return Player

    @property
    def player_data_model(self):
        return MMPlayerData

    @property
    def error_class(self):
        return PlayerError

    @property
    def game_type(self) -> GameType:
        return GameType.MM

    def _get_initial_balance(self) -> int:
        """Get the initial balance for new QF players."""
        return settings.mm_starting_wallet

    async def create_player(self, *, username: str, email: str, password_hash: str) -> Player:
        """Create new Meme Mint player with configured starting balance."""
        return await super().create_player(
            username=username,
            email=email,
            password_hash=password_hash,
        )

    async def get_player_by_username(self, username: str) -> Player | None:
        username_service = UsernameService(self.db, game_type=GameType.MM)
        player = await username_service.find_player_by_username(username)
        return self.apply_admin_status(player)

    async def get_player_by_id(self, player_id: uuid.UUID) -> Player | None:
        result = await self.db.execute(select(Player).where(Player.player_id == player_id))
        player = result.scalar_one_or_none()
        return self.apply_admin_status(player)
