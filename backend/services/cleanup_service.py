"""Cleanup service for database maintenance tasks."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, UTC, timedelta

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for periodic database cleanup tasks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def cleanup_orphaned_refresh_tokens(self) -> int:
        """
        Remove refresh tokens that reference non-existent players.

        This handles cases where:
        - Tokens were created with inconsistent UUID formats
        - Players were deleted outside the CASCADE constraint
        - Data integrity issues occurred

        Returns:
            Number of orphaned tokens deleted
        """
        # Find and delete orphaned refresh tokens
        # The query normalizes both sides to handle UUID format mismatches (with/without hyphens)
        result = await self.db.execute(
            text("""
                DELETE FROM refresh_tokens
                WHERE rowid IN (
                    SELECT rt.rowid FROM refresh_tokens rt
                    WHERE NOT EXISTS (
                        SELECT 1 FROM players p
                        WHERE LOWER(REPLACE(p.player_id, '-', '')) = LOWER(REPLACE(rt.player_id, '-', ''))
                    )
                )
            """)
        )
        await self.db.commit()

        deleted_count = result.rowcount or 0
        if deleted_count > 0:
            logger.warning(f"Cleaned up {deleted_count} orphaned refresh tokens")
        else:
            logger.debug("No orphaned refresh tokens found")

        return deleted_count

    async def cleanup_expired_refresh_tokens(self) -> int:
        """
        Remove expired refresh tokens.

        Returns:
            Number of expired tokens deleted
        """
        now = datetime.now(UTC)

        result = await self.db.execute(
            text("""
                DELETE FROM refresh_tokens
                WHERE expires_at < :now OR revoked_at IS NOT NULL
            """),
            {"now": now}
        )
        await self.db.commit()

        deleted_count = result.rowcount or 0
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired/revoked refresh tokens")
        else:
            logger.debug("No expired refresh tokens found")

        return deleted_count

    async def cleanup_old_revoked_tokens(self, days_old: int = 30) -> int:
        """
        Remove revoked tokens older than specified days.

        Args:
            days_old: Remove revoked tokens older than this many days

        Returns:
            Number of old revoked tokens deleted
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days_old)

        result = await self.db.execute(
            text("""
                DELETE FROM refresh_tokens
                WHERE revoked_at IS NOT NULL AND revoked_at < :cutoff_date
            """),
            {"cutoff_date": cutoff_date}
        )
        await self.db.commit()

        deleted_count = result.rowcount or 0
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old revoked tokens (>{days_old} days)")

        return deleted_count

    async def run_all_cleanup_tasks(self) -> dict[str, int]:
        """
        Run all cleanup tasks.

        Returns:
            Dictionary with counts of items cleaned up per task
        """
        logger.info("Starting scheduled cleanup tasks")

        results = {
            "orphaned_tokens": await self.cleanup_orphaned_refresh_tokens(),
            "expired_tokens": await self.cleanup_expired_refresh_tokens(),
            "old_revoked_tokens": await self.cleanup_old_revoked_tokens(),
        }

        total_cleaned = sum(results.values())
        logger.info(f"Cleanup tasks completed. Total items cleaned: {total_cleaned}")

        return results
