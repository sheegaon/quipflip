"""Cleanup service for database maintenance tasks."""
import logging
import random
import re
from uuid import UUID
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    String,
    case,
    cast,
    delete,
    exists,
    func,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.qf import (
    QFPlayer,
    Round,
    Vote,
    QFTransaction,
    QFDailyBonus,
    QFResultView,
    PlayerAbandonedPrompt,
    PromptFeedback,
    PhrasesetActivity,
    QFQuest,
)
from backend.models.refresh_token import RefreshToken
from backend.services.username_service import canonicalize_username
from backend.services.qf.queue_service import QFQueueService
from backend.services.qf.party_session_service import PartySessionService

logger = logging.getLogger(__name__)


class QFCleanupService:
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
    def _normalize_rowcount(rowcount: int | None) -> int:
        """Return a non-negative rowcount value.

        SQLite (and some drivers) may return -1 when the exact number of rows
        affected is unknown. The tests rely on receiving ``0`` when nothing was
        deleted and a positive integer when rows were removed, so we coerce any
        falsey or negative values to ``0``.
        """

        if not rowcount or rowcount < 0:
            return 0
        return rowcount

    @staticmethod
    def _has_recycled_suffix(username: str | None) -> bool:
        """Return True if the username already carries a recycled suffix."""
        if not username:
            return False
        return username.endswith(" X") or bool(re.search(r" X\d+$", username))

    @staticmethod
    def _normalized_uuid(column):
        """Return a lowercase, hyphen-less string representation of a UUID column.

        Uses SQLAlchemy expressions to remain portable across database dialects
        (e.g., SQLite vs. Postgres) instead of relying on dialect-specific casts
        like ``::text``.
        """

        return func.lower(func.replace(cast(column, String), "-", ""))

    async def _generate_anonymous_username(self) -> tuple[str, str]:
        """Generate a unique anonymous username like 'Deleted User #12345'.

        Returns:
            Tuple of (username, username_canonical)
        """
        while True:
            # Generate random 5-digit number
            random_num = random.randint(10000, 99999)
            username = f"Deleted User #{random_num}"
            username_canonical = canonicalize_username(username)

            # Check if this username is already taken
            result = await self.db.execute(
                select(QFPlayer).where(QFPlayer.username_canonical == username_canonical)
            )
            existing = result.scalar_one_or_none()

            if not existing:
                return username, username_canonical

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
        # Using token_id (the actual primary key column name)
        player_id_normalized = self._normalized_uuid(QFPlayer.player_id)
        token_player_normalized = self._normalized_uuid(RefreshToken.player_id)

        orphaned_tokens = (
            select(RefreshToken.token_id)
            .where(
                ~exists()
                .where(player_id_normalized == token_player_normalized)
                .correlate(RefreshToken)
            )
        )

        result = await self.db.execute(
            delete(RefreshToken).where(RefreshToken.token_id.in_(orphaned_tokens))
        )
        await self.db.commit()

        deleted_count = self._normalize_rowcount(result.rowcount)
        if deleted_count > 0:
            logger.warning(f"Cleaned up {deleted_count} orphaned refresh tokens")
        else:
            logger.info("No orphaned refresh tokens found")

        return deleted_count

    async def cleanup_expired_refresh_tokens(self) -> int:
        """
        Remove expired refresh tokens.

        Returns:
            Number of expired tokens deleted
        """
        now = datetime.now(UTC)

        result = await self.db.execute(
            delete(RefreshToken).where(
                (RefreshToken.expires_at < now) | (RefreshToken.revoked_at.is_not(None))
            )
        )
        await self.db.commit()

        deleted_count = self._normalize_rowcount(result.rowcount)
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired/revoked refresh tokens")
        else:
            logger.info("No expired refresh tokens found")

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
            delete(RefreshToken).where(
                (RefreshToken.revoked_at.is_not(None)) & (RefreshToken.revoked_at < cutoff_date)
            )
        )
        await self.db.commit()

        deleted_count = self._normalize_rowcount(result.rowcount)
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old revoked tokens (>{days_old} days)")

        return deleted_count

    # ===== Orphaned Rounds Cleanup =====

    async def count_orphaned_rounds(self) -> tuple[int, dict[str, int]]:
        """Count orphaned rounds in the database."""
        # Count rounds with player_id not in players table
        result = await self.db.execute(text("""
            SELECT COUNT(*)
            FROM qf_rounds
            WHERE player_id NOT IN (SELECT player_id FROM players)
        """))
        orphaned_count = result.scalar() or 0

        # Count by type
        result = await self.db.execute(text("""
            SELECT round_type, COUNT(*) as count
            FROM qf_rounds
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
            logger.info("No orphaned rounds found")
            return 0

        logger.info(f"Found {orphaned_count} orphaned round(s): {by_type}")

        # Get IDs of orphaned prompt rounds before deleting them
        prompt_result = await self.db.execute(text("""
            SELECT round_id FROM qf_rounds
            WHERE player_id NOT IN (SELECT player_id FROM players)
            AND round_type = 'prompt'
        """))
        orphaned_prompt_ids = [row[0] for row in prompt_result]

        # Delete orphaned rounds
        result = await self.db.execute(text("""
            DELETE FROM qf_rounds
            WHERE player_id NOT IN (SELECT player_id FROM players)
        """))
        await self.db.commit()

        deleted_count = self._normalize_rowcount(result.rowcount)
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} orphaned round(s)")

        # Remove deleted prompt rounds from queue
        if orphaned_prompt_ids:
            removed_from_queue = QFQueueService.remove_prompt_rounds_from_queue(orphaned_prompt_ids)
            logger.info(f"Removed {removed_from_queue} orphaned prompt rounds from queue")

        return deleted_count

    # ===== Test Player Cleanup =====

    async def get_test_players(self) -> list[QFPlayer]:
        """
        Find all players matching test patterns.

        Returns:
            List of Player objects
        """
        if not self._TEST_LIKE_PATTERNS:
            return []

        like_conditions = []
        for column_name, like_pattern in self._TEST_LIKE_PATTERNS:
            column = getattr(QFPlayer, column_name)
            like_conditions.append(column.ilike(like_pattern))

        stmt = select(QFPlayer).where(or_(*like_conditions))
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()

        def matches(player: QFPlayer) -> bool:
            username = player.username or ""
            email = player.email or ""
            return any(regex.match(username) for regex in self._TEST_USERNAME_REGEXES) or any(
                regex.match(email) for regex in self._TEST_EMAIL_REGEXES
            )

        unique_players: dict[str, QFPlayer] = {}
        for player in candidates:
            if matches(player):
                unique_players[player.player_id] = player

        return list(unique_players.values())

    async def _delete_players_by_ids(self, player_ids: list[UUID]) -> dict[str, int]:
        """Anonymize players and delete related non-essential data for the provided IDs.

        Players are anonymized (not deleted) to preserve game history and prevent
        data integrity violations. Submitted rounds are preserved as they are
        referenced by phrasesets.
        """
        if not player_ids:
            return {}

        deletion_counts: dict[str, int] = {}

        # Delete related data first (in order to respect foreign keys)

        # 1. Votes (references player_id)
        result = await self.db.execute(
            delete(Vote).where(Vote.player_id.in_(player_ids))
        )
        deletion_counts['votes'] = self._normalize_rowcount(result.rowcount)

        # 2. Transactions (references player_id)
        result = await self.db.execute(
            delete(QFTransaction).where(QFTransaction.player_id.in_(player_ids))
        )
        deletion_counts['transactions'] = self._normalize_rowcount(result.rowcount)

        # 3. Daily bonuses (references player_id)
        result = await self.db.execute(
            delete(QFDailyBonus).where(QFDailyBonus.player_id.in_(player_ids))
        )
        deletion_counts['daily_bonuses'] = self._normalize_rowcount(result.rowcount)

        # 4. Result views (references player_id)
        result = await self.db.execute(
            delete(QFResultView).where(QFResultView.player_id.in_(player_ids))
        )
        deletion_counts['result_views'] = self._normalize_rowcount(result.rowcount)

        # 5. Abandoned prompts (references player_id)
        result = await self.db.execute(
            delete(PlayerAbandonedPrompt).where(PlayerAbandonedPrompt.player_id.in_(player_ids))
        )
        deletion_counts['abandoned_prompts'] = self._normalize_rowcount(result.rowcount)

        # 6. Prompt feedback (references player_id)
        result = await self.db.execute(
            delete(PromptFeedback).where(PromptFeedback.player_id.in_(player_ids))
        )
        deletion_counts['prompt_feedback'] = self._normalize_rowcount(result.rowcount)

        # 7. Phraseset activities (references player_id)
        result = await self.db.execute(
            delete(PhrasesetActivity).where(PhrasesetActivity.player_id.in_(player_ids))
        )
        deletion_counts['phraseset_activities'] = self._normalize_rowcount(result.rowcount)

        # 8. Refresh tokens (references player_id)
        result = await self.db.execute(
            delete(RefreshToken).where(RefreshToken.player_id.in_(player_ids))
        )
        deletion_counts['refresh_tokens'] = self._normalize_rowcount(result.rowcount)

        # 9. Quests (references player_id)
        result = await self.db.execute(
            delete(QFQuest).where(QFQuest.player_id.in_(player_ids))
        )
        deletion_counts['quests'] = self._normalize_rowcount(result.rowcount)

        # 10. Get IDs of prompt rounds to be deleted from queue (for abandoned prompts only)
        # Note: We do NOT delete submitted rounds as they are part of phrasesets and game history
        prompt_rounds_result = await self.db.execute(
            select(Round.round_id)
            .where(Round.player_id.in_(player_ids))
            .where(Round.round_type == "prompt")
            .where(Round.status != "submitted")  # Only queue cleanup for non-submitted
        )
        prompt_round_ids = [row[0] for row in prompt_rounds_result]

        # 11. Delete ONLY abandoned/incomplete rounds (not submitted rounds)
        # Submitted rounds must be preserved because:
        # - They are referenced by phrasesets
        # - They are part of game history
        # - Deleting them causes data integrity violations
        result = await self.db.execute(
            delete(Round).where(
                Round.player_id.in_(player_ids),
                Round.status != "submitted"  # Preserve submitted rounds
            )
        )
        deletion_counts['rounds'] = self._normalize_rowcount(result.rowcount)

        # Count submitted rounds that were NOT deleted (for logging)
        submitted_rounds_result = await self.db.execute(
            select(func.count(Round.round_id))
            .where(Round.player_id.in_(player_ids))
            .where(Round.status == "submitted")
        )
        preserved_rounds = submitted_rounds_result.scalar() or 0
        if preserved_rounds > 0:
            deletion_counts['rounds_preserved'] = preserved_rounds
            logger.info(f"Preserved {preserved_rounds} submitted rounds (needed for phrasesets)")

        # 12. Anonymize players instead of deleting them
        # This preserves game history and prevents data integrity violations
        anonymized_count = 0
        for player_id in player_ids:
            # Generate unique anonymous username
            anon_username, anon_canonical = await self._generate_anonymous_username()

            # Anonymize the player
            result = await self.db.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == player_id)
                .values(
                    username=anon_username,
                    username_canonical=anon_canonical,
                    email=f"deleted_{player_id}@deleted.local",  # Unique email to avoid conflicts
                    password_hash="",  # Clear password (prevents login)
                    is_guest=True,  # Mark as guest (additional login prevention)
                    locked_until=datetime(2099, 12, 31, tzinfo=UTC),  # Lock account permanently
                )
            )
            if result.rowcount:
                anonymized_count += 1

        deletion_counts['players_anonymized'] = anonymized_count
        logger.info(f"Anonymized {anonymized_count} player(s) (preserved for game history)")

        # Commit the transaction
        await self.db.commit()

        # Remove deleted prompt rounds from queue (after commit to ensure consistency)
        if prompt_round_ids:
            removed_from_queue = QFQueueService.remove_prompt_rounds_from_queue(prompt_round_ids)
            deletion_counts['queue_cleanup'] = removed_from_queue
            logger.info(f"Removed {removed_from_queue} prompt rounds from queue after player deletion")

        return deletion_counts

    async def cleanup_test_players(self, dry_run: bool = False) -> dict[str, int]:
        """
        Anonymize test players and remove their non-essential data from the database.

        Test players are anonymized (not deleted) to preserve game history and
        prevent data integrity violations.

        Args:
            dry_run: If True, return counts without making changes

        Returns:
            Dictionary with counts of deleted/anonymized entities
        """
        # Find test players
        test_players = await self.get_test_players()

        if not test_players:
            logger.info("No test players found")
            return {}

        logger.info(f"Found {len(test_players)} test player(s)")

        if dry_run:
            return {"would_delete_players": len(test_players)}

        # Extract player IDs for anonymization and cleanup
        player_ids = [player.player_id for player in test_players]
        deletion_counts = await self._delete_players_by_ids(player_ids)

        total_processed = sum(deletion_counts.values())
        logger.info(f"Anonymized test players and processed {total_processed} associated records")

        return deletion_counts

    async def delete_player(self, player_id: UUID) -> dict[str, int]:
        """Anonymize a single player and delete associated non-essential data.

        The player is anonymized (not deleted) to preserve game history.
        """
        deletion_counts = await self._delete_players_by_ids([player_id])
        if deletion_counts:
            logger.info(f"Anonymized {player_id=} and deleted related data")
        else:
            logger.info(f"No records processed for {player_id=}")
        return deletion_counts

    # ===== Inactive Guest Player Cleanup =====

    async def cleanup_inactive_guest_players(self, hours_old: int = 1) -> int:
        """
        Remove guest accounts that:
        1. Have is_guest=True
        2. Have not logged in for more than hours_old hours (or never logged in AND old enough)
        3. Have no activity (no submitted rounds, no phraseset activities, and no transactions)

        For guests with NO activity, they are completely deleted from the database.
        For guests WITH activity who are being deleted elsewhere, they get anonymized
        with a random username (handled by _delete_players_by_ids).

        Args:
            hours_old: Delete guests who haven't logged in for this many hours (default: 1)

        Returns:
            Number of inactive guest players deleted
        """
        cutoff_date = datetime.now(UTC) - timedelta(hours=hours_old)

        # Find guests who haven't logged in recently
        # For guests with NULL last_login_date, also check created_at to avoid deleting new accounts
        stmt = select(QFPlayer).where(
            QFPlayer.is_guest == True,  # noqa: E712
            or_(
                QFPlayer.last_login_date < cutoff_date,
                # Never logged in AND old enough (prevents deleting newly-created accounts)
                (QFPlayer.last_login_date.is_(None) & (QFPlayer.created_at < cutoff_date))
            )
        )
        result = await self.db.execute(stmt)
        all_old_guests = result.scalars().all()

        if not all_old_guests:
            logger.info("No inactive guest players found")
            return 0

        # Get all player IDs for batch queries
        guest_ids = [guest.player_id for guest in all_old_guests]

        guests_with_activity = set()
        if guest_ids:
            # Check for rounds
            rounds_result = await self.db.execute(
                select(Round.player_id)
                .where(Round.player_id.in_(guest_ids))
                .distinct()
            )
            guests_with_activity.update(row[0] for row in rounds_result)

            # Check for phraseset activities
            phraseset_result = await self.db.execute(
                select(PhrasesetActivity.player_id)
                .where(PhrasesetActivity.player_id.in_(guest_ids))
                .distinct()
            )
            guests_with_activity.update(row[0] for row in phraseset_result)

            # Check for transactions
            transactions_result = await self.db.execute(
                select(QFTransaction.player_id)
                .where(QFTransaction.player_id.in_(guest_ids))
                .distinct()
            )
            guests_with_activity.update(row[0] for row in transactions_result)

        # Filter to guests with NO activity
        inactive_guest_ids = [guest_id for guest_id in guest_ids if guest_id not in guests_with_activity]

        if not inactive_guest_ids:
            logger.info(f"Found {len(all_old_guests)} guest(s) but all have activity")
            return 0

        logger.info(f"Found {len(inactive_guest_ids)} inactive guest player(s) to clean up")

        # Delete the players - related data will be deleted automatically via CASCADE
        # All related tables have ondelete="CASCADE" configured on their foreign keys
        result = await self.db.execute(
            delete(QFPlayer).where(QFPlayer.player_id.in_(inactive_guest_ids))
        )
        deleted_count = self._normalize_rowcount(result.rowcount)

        # Commit the transaction
        await self.db.commit()

        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} inactive guest player(s) completely from database")

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

        stmt = select(QFPlayer).where(
            QFPlayer.is_guest == True,  # noqa: E712
            QFPlayer.last_login_date < cutoff_date,
            or_(
                QFPlayer.username.is_(None),
                ~QFPlayer.username.like("% X%"),
            ),
        )

        result = await self.db.execute(stmt)
        raw_candidates = [player for player in result.scalars() if player]

        candidates: list[QFPlayer] = [
            player for player in raw_candidates if not self._has_recycled_suffix(player.username)
        ]

        if not candidates:
            logger.info("No guest usernames to recycle")
            return 0

        processed_candidates: list[tuple[QFPlayer, str]] = []
        conflict_prefixes: set[str] = set()

        for guest in candidates:
            base_username = guest.username or ""

            if not base_username.strip():
                logger.info(f"Skipping guest {guest.player_id} with empty username")
                continue

            first_username = f"{base_username} X"
            first_canonical = canonicalize_username(first_username)

            if not first_canonical:
                logger.info(f"Skipping guest {guest.player_id} due to empty canonical for candidate '{first_username}'")
                continue

            processed_candidates.append((guest, base_username))
            conflict_prefixes.add(first_canonical.rstrip("0123456789"))

        if not processed_candidates:
            logger.info("No guest usernames to recycle")
            return 0

        conflict_conditions = [
            QFPlayer.username_canonical.like(f"{prefix}%") for prefix in conflict_prefixes if prefix
        ]

        existing_conflicts: set[str] = set()
        if conflict_conditions:
            conflict_stmt = select(QFPlayer.username_canonical).where(or_(*conflict_conditions))
            conflict_result = await self.db.execute(conflict_stmt)
            existing_conflicts = {row for row in conflict_result.scalars() if row}

        reserved_canonicals: set[str] = set(existing_conflicts)
        updates: list[dict[str, str | UUID]] = []
        updated_player_ids: set[UUID] = set()

        for guest, base_username in processed_candidates:
            suffix_index = 1

            while suffix_index < 1000:  # reasonable guard to avoid infinite loops
                if suffix_index == 1:
                    new_username = f"{base_username} X"
                else:
                    new_username = f"{base_username} X{suffix_index}"

                canonical = canonicalize_username(new_username)

                if not canonical:
                    logger.info(
                        f"Skipping candidate username '{new_username}' for guest {guest.player_id} due to empty canonical")
                    break

                if canonical in reserved_canonicals:
                    suffix_index += 1
                    continue

                reserved_canonicals.add(canonical)
                updates.append(
                    {
                        "player_id": guest.player_id,
                        "username": new_username,
                        "username_canonical": canonical,
                    }
                )
                updated_player_ids.add(guest.player_id)
                break

            if guest.player_id not in updated_player_ids:
                logger.warning(
                    f"Unable to recycle username for guest {guest.player_id} after exhausting suffix attempts")

        if not updates:
            logger.info("No guest usernames to recycle")
            return 0

        logger.info(f"Prepared guest username updates: {updates}")

        player_ids = [update_entry["player_id"] for update_entry in updates]

        username_case = case(
            {
                update_entry["player_id"]: update_entry["username"]
                for update_entry in updates
            },
            value=QFPlayer.player_id,
            else_=QFPlayer.username,
        )
        canonical_case = case(
            {
                update_entry["player_id"]: update_entry["username_canonical"]
                for update_entry in updates
            },
            value=QFPlayer.player_id,
            else_=QFPlayer.username_canonical,
        )

        await self.db.execute(
            update(QFPlayer)
            .where(QFPlayer.player_id.in_(player_ids))
            .values(username=username_case, username_canonical=canonical_case)
            .execution_options(synchronize_session=False)
        )
        await self.db.commit()

        await self.db.run_sync(lambda sync_session: sync_session.expire_all())

        recycled_count = len(updates)

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

        party_service = PartySessionService(self.db)
        party_cleanup = await party_service.cleanup_inactive_sessions()
        results["party_inactive_participants_removed"] = party_cleanup["participants_removed"]
        results["party_sessions_deleted"] = party_cleanup["sessions_deleted"]
        logger.info(
            "Party cleanup stats: %s sessions checked, %s participants removed, %s sessions deleted",
            party_cleanup["sessions_checked"],
            party_cleanup["participants_removed"],
            party_cleanup["sessions_deleted"],
        )

        test_player_results = await self.cleanup_test_players()
        results.update(test_player_results)

        total_cleaned = sum(results.values())
        logger.info(f"Cleanup tasks completed. Total items cleaned: {total_cleaned}")

        return results
