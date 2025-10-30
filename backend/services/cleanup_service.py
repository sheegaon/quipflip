"""Cleanup service for database maintenance tasks."""
import logging
import re
from uuid import UUID
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

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
from backend.services.username_service import canonicalize_username

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for periodic database cleanup tasks."""

    # Test player identification patterns derived from test scripts
    _TEST_USERNAME_REGEXES = [
        re.compile(r"^testplayer\d+_\d+$", re.IGNORECASE),
        re.compile(r"^stresstest\d+_\d+$", re.IGNORECASE),
        re.compile(r"^test_user_[0-9a-f]{8}$", re.IGNORECASE),
    ]
    _TEST_EMAIL_REGEXES = [
        re.compile(r"^testplayer\d+_\d+@example\.com$", re.IGNORECASE),
        re.compile(r"^stresstest\d+_\d+@example\.com$", re.IGNORECASE),
        re.compile(r"^test_user_[0-9a-f]{8}@example\.com$", re.IGNORECASE),
    ]
    _TEST_LIKE_PATTERNS = [
        ("username", "testplayer%"),
        ("email", "testplayer%"),
        ("username", "stresstest%"),
        ("email", "stresstest%"),
        ("username", "test_user_%"),
        ("email", "test_user_%"),
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _has_recycled_suffix(username: str | None) -> bool:
        """Return True if the username already carries a recycled suffix."""
        if not username:
            return False
        return username.endswith(" X") or bool(re.search(r" X\d+$", username))

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
        from sqlalchemy import or_

        if not self._TEST_LIKE_PATTERNS:
            return []

        like_conditions = []
        for column_name, like_pattern in self._TEST_LIKE_PATTERNS:
            column = getattr(Player, column_name)
            like_conditions.append(column.ilike(like_pattern))

        stmt = select(Player).where(or_(*like_conditions))
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()

        def matches(player: Player) -> bool:
            username = player.username or ""
            email = player.email or ""
            return any(regex.match(username) for regex in self._TEST_USERNAME_REGEXES) or any(
                regex.match(email) for regex in self._TEST_EMAIL_REGEXES
            )

        unique_players: dict[str, Player] = {}
        for player in candidates:
            if matches(player):
                unique_players[player.player_id] = player

        return list(unique_players.values())

    async def _delete_players_by_ids(self, player_ids: list[UUID]) -> dict[str, int]:
        """Delete players and related data for the provided IDs."""

        if not player_ids:
            return {}

        deletion_counts: dict[str, int] = {}

        # Delete related data first (in order to respect foreign keys)

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

        return deletion_counts

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
        deletion_counts = await self._delete_players_by_ids(player_ids)

        total_deleted = sum(deletion_counts.values())
        logger.info(f"Deleted test players and {total_deleted} associated records")

        return deletion_counts

    async def delete_player(self, player_id: UUID) -> dict[str, int]:
        """Delete a single player and associated data."""

        deletion_counts = await self._delete_players_by_ids([player_id])
        if deletion_counts:
            logger.info("Deleted player %s and related data", player_id)
        else:
            logger.debug("No records deleted for player %s", player_id)
        return deletion_counts

    # ===== Inactive Guest Player Cleanup =====

    async def cleanup_inactive_guest_players(self, days_old: int = 7) -> int:
        """
        Remove guest accounts that:
        1. Have is_guest=True
        2. Were created more than days_old days ago
        3. Have not played any rounds (no rounds associated with their player_id)

        Args:
            days_old: Delete guests older than this many days (default: 7)

        Returns:
            Number of inactive guest players deleted
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days_old)

        # Find inactive guests
        stmt = select(Player).where(
            Player.is_guest == True,  # noqa: E712
            Player.created_at < cutoff_date
        )
        result = await self.db.execute(stmt)
        all_old_guests = result.scalars().all()

        if not all_old_guests:
            logger.debug("No old guest players found")
            return 0

        # Filter to those with no rounds
        inactive_guest_ids = []
        for guest in all_old_guests:
            # Check if player has any rounds
            rounds_stmt = select(Round).where(Round.player_id == guest.player_id).limit(1)
            rounds_result = await self.db.execute(rounds_stmt)
            has_rounds = rounds_result.scalar_one_or_none() is not None

            if not has_rounds:
                inactive_guest_ids.append(guest.player_id)

        if not inactive_guest_ids:
            logger.debug(f"Found {len(all_old_guests)} old guest(s), but all have played rounds")
            return 0

        logger.info(f"Found {len(inactive_guest_ids)} inactive guest player(s) to clean up (>{days_old} days old, no rounds)")

        # Delete inactive guests and their related data
        deletion_counts = await self._delete_players_by_ids(inactive_guest_ids)

        deleted_count = deletion_counts.get('players', 0)
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} inactive guest player(s)")

        return deleted_count

    async def recycle_inactive_guest_usernames(self, days_old: int = 30) -> int:
        """
        Recycle usernames from guest accounts that haven't logged in for 30+ days
        by appending " X" (and numeric suffixes if needed) while ensuring the
        canonical username remains unique.

        This allows those usernames to be reused by new players.

        Args:
            days_old: Recycle usernames for guests inactive for this many days (default: 30)

        Returns:
            Number of guest usernames recycled
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days_old)

        stmt = select(Player).where(
            Player.is_guest == True,  # noqa: E712
            Player.last_login_date < cutoff_date,
        )

        result = await self.db.execute(stmt)
        candidates = [player for player in result.scalars() if player and not self._has_recycled_suffix(player.username)]

        if not candidates:
            logger.debug("No guest usernames to recycle")
            return 0

        recycled_count = 0
        reserved_canonicals: set[str] = set()

        for guest in candidates:
            base_username = guest.username or ""

            if not base_username.strip():
                logger.debug("Skipping guest %s with empty username", guest.player_id)
                continue

            suffix_index = 1
            updated = False

            while suffix_index < 1000:  # reasonable guard to avoid infinite loops
                if suffix_index == 1:
                    new_username = f"{base_username} X"
                else:
                    new_username = f"{base_username} X{suffix_index}"

                canonical = canonicalize_username(new_username)

                if not canonical:
                    logger.debug(
                        "Skipping candidate username '%s' for guest %s due to empty canonical",
                        new_username,
                        guest.player_id,
                    )
                    break

                if canonical in reserved_canonicals:
                    suffix_index += 1
                    continue

                conflict_stmt = (
                    select(Player.player_id)
                    .where(
                        Player.username_canonical == canonical,
                        Player.player_id != guest.player_id,
                    )
                    .limit(1)
                )
                conflict_result = await self.db.execute(conflict_stmt)
                conflict_player_id = conflict_result.scalar_one_or_none()

                if conflict_player_id is not None:
                    suffix_index += 1
                    continue

                await self.db.execute(
                    update(Player)
                    .where(Player.player_id == guest.player_id)
                    .values(username=new_username, username_canonical=canonical)
                )

                reserved_canonicals.add(canonical)
                recycled_count += 1
                updated = True
                break

            if not updated:
                logger.warning(
                    "Unable to recycle username for guest %s after exhausting suffix attempts",
                    guest.player_id,
                )

        if recycled_count == 0:
            logger.debug("No guest usernames to recycle")
            return 0

        await self.db.commit()

        logger.info(f"Recycled {recycled_count} guest username(s)")

        return recycled_count

    # ===== Run All Cleanup Tasks =====

    async def run_all_cleanup_tasks(self) -> dict[str, int]:
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
            "inactive_guests": await self.cleanup_inactive_guest_players(),
            "recycled_guest_usernames": await self.recycle_inactive_guest_usernames(),
        }

        test_player_results = await self.cleanup_test_players()
        results.update(test_player_results)

        total_cleaned = sum(results.values())
        logger.info(f"Cleanup tasks completed. Total items cleaned: {total_cleaned}")

        return results
