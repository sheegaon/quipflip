"""Cleanup utilities for Meme Mint accounts."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mm.player import MMPlayer

logger = logging.getLogger(__name__)


class MMCleanupService:
    """Minimal cleanup service to remove Meme Mint players and related data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def delete_player(self, player_id: UUID) -> None:
        """Delete a Meme Mint player and cascade-owned rows.

        Meme Mint models are wired with ``delete-orphan`` cascades, so removing the
        player record will clean up dependent objects such as refresh tokens,
        transactions, daily state, and vote history.
        """

        result = await self.db.execute(
            select(MMPlayer).where(MMPlayer.player_id == player_id).with_for_update()
        )
        player = result.scalar_one_or_none()
        if not player:
            logger.info("MM player %s not found during cleanup", player_id)
            return

        await self.db.delete(player)
        await self.db.commit()
        logger.info("Deleted MM player %s and related data", player_id)
