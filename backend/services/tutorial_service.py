"""Tutorial service for managing player tutorial progress."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, UTC
from uuid import UUID
import logging

from backend.models.player import Player
from backend.schemas.player import TutorialStatus

logger = logging.getLogger(__name__)


class TutorialService:
    """Service for managing tutorial progress."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_player(self, player_id: UUID) -> Player:
        """Fetch a player by ID or raise ValueError if not found."""
        result = await self.db.execute(
            select(Player).where(Player.player_id == player_id)
        )
        player = result.scalar_one_or_none()

        if not player:
            raise ValueError("Player not found")

        return player

    def _create_tutorial_status(self, player: Player) -> TutorialStatus:
        """Create a TutorialStatus schema from a Player model."""
        return TutorialStatus(
            tutorial_completed=player.tutorial_completed,
            tutorial_progress=player.tutorial_progress,
            tutorial_started_at=player.tutorial_started_at,
            tutorial_completed_at=player.tutorial_completed_at,
        )

    async def get_tutorial_status(self, player_id: UUID) -> TutorialStatus:
        """Get the tutorial status for a player."""
        player = await self._get_player(player_id)
        return self._create_tutorial_status(player)

    async def update_tutorial_progress(
        self, player_id: UUID, progress: str
    ) -> TutorialStatus:
        """Update tutorial progress for a player."""
        player = await self._get_player(player_id)

        # Update progress
        player.tutorial_progress = progress

        # If starting tutorial from 'welcome', reset completion status
        # This allows players to restart the tutorial
        if progress == "welcome":
            player.tutorial_completed = False
            player.tutorial_completed_at = None

        # Set started_at if this is the first progress update
        if progress != "not_started" and not player.tutorial_started_at:
            player.tutorial_started_at = datetime.now(UTC)

        # Mark as completed if progress is "completed"
        if progress == "completed":
            player.tutorial_completed = True
            player.tutorial_completed_at = datetime.now(UTC)

        await self.db.commit()
        await self.db.refresh(player)

        logger.info(
            f"Updated tutorial progress for player {player_id} to {progress}"
        )

        return self._create_tutorial_status(player)

    async def reset_tutorial(self, player_id: UUID) -> TutorialStatus:
        """Reset tutorial progress for a player."""
        player = await self._get_player(player_id)

        # Reset all tutorial fields
        player.tutorial_completed = False
        player.tutorial_progress = "not_started"
        player.tutorial_started_at = None
        player.tutorial_completed_at = None

        await self.db.commit()
        await self.db.refresh(player)

        logger.info(f"Reset tutorial for player {player_id}")

        return self._create_tutorial_status(player)
