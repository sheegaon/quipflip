"""IR Player Service - Manages Initial Reaction player accounts and wallets."""

import logging
import uuid
import random
from datetime import datetime, UTC
from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from backend.config import get_settings
from backend.models.player import Player
from backend.models.ir.player_data import PlayerData
from backend.utils.passwords import hash_password
from backend.services.player_service_base import PlayerServiceBase, PlayerServiceError
from backend.services.username_service import UsernameService, canonicalize_username

logger = logging.getLogger(__name__)


class PlayerError(PlayerServiceError):
    """Raised when IR player service fails."""


class PlayerService(PlayerServiceBase):
    """Service for managing IR player accounts and wallets."""

    @property
    def player_model(self):
        """Return the unified player model class."""
        return Player

    @property
    def player_data_model(self):
        """Return the IR player data model class."""
        return PlayerData

    @property
    def error_class(self):
        """Return the IR player error class."""
        return PlayerError

    @property
    def game_type(self):
        """Return the game type for this service."""
        from backend.utils.model_registry import GameType
        return GameType.IR

    def get_guest_domain(self) -> str:
        """Get the domain for IR guest email addresses."""
        return "initialreaction.xyz"

    def _get_initial_balance(self) -> int:
        """Get the initial balance for new IR players."""
        return self.settings.ir_initial_balance

    async def get_player_by_id(self, player_id: Union[str, UUID]) -> Player | None:
        """Get IR player by ID with UUID/string compatibility.

        Args:
            player_id: Player UUID

        Returns:
            Player or None if not found
        """
        # Convert to UUID if needed for QF compatibility
        if isinstance(player_id, str):
            try:
                search_id = UUID(player_id) if len(player_id) > 32 else player_id
            except ValueError:
                search_id = player_id
        else:
            search_id = player_id

        stmt = select(Player).where(Player.player_id == search_id)
        result = await self.db.execute(stmt)
        player = result.scalars().first()
        return self.apply_admin_status(player)

    async def create_player(
        self,
        username: str,
        email: str,
        password_hash: str,
    ) -> Player:
        """Create a new IR player account.

        Args:
            username: Display username
            email: Email address
            password_hash: Hashed password

        Returns:
            Player: Created player

        Raises:
            PlayerError: If player creation fails
        """
        return await super().create_player(
            username=username,
            email=email,
            password_hash=password_hash,
        )

    async def set_vote_lockout(self, player_id: str, until: datetime) -> Player:
        """Set vote lockout for guest player (vote spam prevention).

        Args:
            player_id: Player UUID
            until: Lockout expiration time

        Returns:
            Player: Updated player

        Raises:
            PlayerError: If player not found
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise PlayerError("player_not_found")

        player.vote_lockout_until = until
        player.consecutive_incorrect_votes = 0
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def increment_incorrect_votes(self, player_id: str) -> Player:
        """Increment incorrect vote count for guest player.

        Args:
            player_id: Player UUID

        Returns:
            Player: Updated player

        Raises:
            PlayerError: If player not found
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise PlayerError("player_not_found")

        player.consecutive_incorrect_votes += 1
        await self.db.commit()
        await self.db.refresh(player)
        return player

    async def clear_incorrect_votes(self, player_id: str) -> Player:
        """Clear incorrect vote count for guest player.

        Args:
            player_id: Player UUID

        Returns:
            Player: Updated player

        Raises:
            PlayerError: If player not found
        """
        player = await self.get_player_by_id(player_id)
        if not player:
            raise PlayerError("player_not_found")

        player.consecutive_incorrect_votes = 0
        await self.db.commit()
        await self.db.refresh(player)
        return player
