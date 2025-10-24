"""Cleanup service for database maintenance tasks."""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text
from datetime import datetime, UTC, timedelta
from typing import Optional

from backend.models import (
    Player,
    Round,
    Vote,
    Transaction,
    DailyBonus,
    ResultView,
    PlayerAbandonedPrompt,
    PromptFeedback,
    PhrasesetActivity,
    RefreshToken,
    Quest,
)

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for periodic database cleanup tasks."""

    # Test player identification patterns
    TEST_PATTERNS = [
        "testplayer",
        "stresstest",
        "@example.com",
        "test_",
        "_test",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    # ===== Refresh Token Cleanup =====

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

    # ===== Orphaned Rounds Cleanup =====

    async def count_orphaned_rounds(self) -> tuple[int, dict[str, int]]:
        """Count orphaned rounds in the database."""
        # Count rounds with player_id not in players table
        result = await self.db.execute(text("""
            SELECT COUNT(*)
            FROM rounds
            WHERE player_id NOT IN (SELECT player_id FROM players)
        """))
        orphaned_count = result.scalar() or 0

        # Count by type
        result = await self.db.execute(text("""
            SELECT round_type, COUNT(*) as count
            FROM rounds
            WHERE player_id NOT IN (SELECT player_id FROM players)
            GROUP BY round_type
        """))
        by_type = {row.round_type: row.count for row in result}

        return orphaned_count, by_type

    async def cleanup_orphaned_rounds(self) -> int:
        """
        Remove orphaned rounds from the database.

        Orphaned rounds are rounds that reference player_ids that no longer exist.

        Returns:
            Number of orphaned rounds deleted
        """
        orphaned_count, by_type = await self.count_orphaned_rounds()

        if orphaned_count == 0:
            logger.debug("No orphaned rounds found")
            return 0

        logger.info(f"Found {orphaned_count} orphaned round(s): {by_type}")

        # Delete orphaned rounds
        result = await self.db.execute(text("""
            DELETE FROM rounds
            WHERE player_id NOT IN (SELECT player_id FROM players)
        """))
        await self.db.commit()

        deleted_count = result.rowcount or 0
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} orphaned round(s)")

        return deleted_count

    # ===== Test Player Cleanup =====

    async def get_test_players(self) -> list[Player]:
        """
        Find all players matching test patterns.

        Returns:
            List of Player objects
        """
        # Build query to find test players
        stmt = select(Player)
        result = await self.db.execute(stmt)
        all_players = result.scalars().all()

        # Filter players matching test patterns
        test_players = []
        for player in all_players:
            is_test = False
            for pattern in self.TEST_PATTERNS:
                if (pattern.lower() in player.username.lower() or
                    pattern.lower() in player.email.lower()):
                    is_test = True
                    break

            if is_test:
                test_players.append(player)

        return test_players

    async def cleanup_test_players(self, dry_run: bool = False) -> dict[str, int]:
        """
        Remove all test player data from the database.

        Args:
            dry_run: If True, return counts without deleting

        Returns:
            Dictionary with counts of deleted entities
        """
        # Find test players
        test_players = await self.get_test_players()

        if not test_players:
            logger.debug("No test players found")
            return {}

        logger.info(f"Found {len(test_players)} test player(s)")

        if dry_run:
            return {"would_delete_players": len(test_players)}

        # Extract player IDs for cascade deletion
        player_ids = [player.player_id for player in test_players]

        # Delete related data first (in order to respect foreign keys)
        deletion_counts = {}

        # 1. Votes (references player_id)
        result = await self.db.execute(
            delete(Vote).where(Vote.player_id.in_(player_ids))
        )
        deletion_counts['votes'] = result.rowcount or 0

        # 2. Transactions (references player_id)
        result = await self.db.execute(
            delete(Transaction).where(Transaction.player_id.in_(player_ids))
        )
        deletion_counts['transactions'] = result.rowcount or 0

        # 3. Daily bonuses (references player_id)
        result = await self.db.execute(
            delete(DailyBonus).where(DailyBonus.player_id.in_(player_ids))
        )
        deletion_counts['daily_bonuses'] = result.rowcount or 0

        # 4. Result views (references player_id)
        result = await self.db.execute(
            delete(ResultView).where(ResultView.player_id.in_(player_ids))
        )
        deletion_counts['result_views'] = result.rowcount or 0

        # 5. Abandoned prompts (references player_id)
        result = await self.db.execute(
            delete(PlayerAbandonedPrompt).where(PlayerAbandonedPrompt.player_id.in_(player_ids))
        )
        deletion_counts['abandoned_prompts'] = result.rowcount or 0

        # 6. Prompt feedback (references player_id)
        result = await self.db.execute(
            delete(PromptFeedback).where(PromptFeedback.player_id.in_(player_ids))
        )
        deletion_counts['prompt_feedback'] = result.rowcount or 0

        # 7. Phraseset activities (references player_id)
        result = await self.db.execute(
            delete(PhrasesetActivity).where(PhrasesetActivity.player_id.in_(player_ids))
        )
        deletion_counts['phraseset_activities'] = result.rowcount or 0

        # 8. Refresh tokens (references player_id)
        result = await self.db.execute(
            delete(RefreshToken).where(RefreshToken.player_id.in_(player_ids))
        )
        deletion_counts['refresh_tokens'] = result.rowcount or 0

        # 9. Quests (references player_id)
        result = await self.db.execute(
            delete(Quest).where(Quest.player_id.in_(player_ids))
        )
        deletion_counts['quests'] = result.rowcount or 0

        # 10. Delete rounds (references player_id)
        # Note: Prompts are shared across players and should not be deleted
        result = await self.db.execute(
            delete(Round).where(Round.player_id.in_(player_ids))
        )
        deletion_counts['rounds'] = result.rowcount or 0

        # 11. Finally, delete players
        result = await self.db.execute(
            delete(Player).where(Player.player_id.in_(player_ids))
        )
        deletion_counts['players'] = result.rowcount or 0

        # Commit the transaction
        await self.db.commit()

        total_deleted = sum(deletion_counts.values())
        logger.info(f"Deleted test players and {total_deleted} associated records")

        return deletion_counts

    # ===== Run All Cleanup Tasks =====

    async def run_all_cleanup_tasks(
        self,
        include_test_players: bool = False,
        test_players_dry_run: bool = True
    ) -> dict[str, int]:
        """
        Run all cleanup tasks.

        Args:
            include_test_players: Whether to include test player cleanup
            test_players_dry_run: If True, only count test players without deleting

        Returns:
            Dictionary with counts of items cleaned up per task
        """
        logger.info("Starting scheduled cleanup tasks")

        results = {
            "orphaned_tokens": await self.cleanup_orphaned_refresh_tokens(),
            "expired_tokens": await self.cleanup_expired_refresh_tokens(),
            "old_revoked_tokens": await self.cleanup_old_revoked_tokens(),
            "orphaned_rounds": await self.cleanup_orphaned_rounds(),
        }

        if include_test_players:
            test_player_results = await self.cleanup_test_players(dry_run=test_players_dry_run)
            results.update(test_player_results)

        total_cleaned = sum(results.values())
        logger.info(f"Cleanup tasks completed. Total items cleaned: {total_cleaned}")

        return results
