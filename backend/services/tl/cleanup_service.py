"""ThinkLink player data cleanup service."""
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from backend.models.tl.player_data import TLPlayerData


class TLCleanupService:
    """Service for cleaning up ThinkLink player data (e.g., during account deletion)."""

    def __init__(self, db: AsyncSession):
        """Initialize the cleanup service.

        Args:
            db: Database session
        """
        self.db = db

    async def cleanup_player_game_data(self, player_id: UUID) -> None:
        """Clean up all ThinkLink-specific data for a deleted player.

        Args:
            player_id: ID of the player being deleted

        Notes:
            - Cascading deletes are handled by database FK constraints
            - This method is a hook for additional cleanup logic
        """
        # Cascading deletes handle most cleanup via ForeignKey constraints
        # Future: Add custom cleanup logic if needed (e.g., embeddings cleanup)
        pass
