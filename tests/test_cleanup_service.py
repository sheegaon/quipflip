"""Tests for cleanup service database maintenance tasks."""

import pytest
from datetime import datetime, UTC, timedelta
from uuid import uuid4
from sqlalchemy import select

from backend.services import CleanupService
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
    Phraseset,
)
from backend.utils.passwords import hash_password


class TestRefreshTokenCleanup:
    """Test refresh token cleanup methods."""

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_refresh_tokens(self, db_session, player_factory):
        """Should remove tokens referencing non-existent players."""
        cleanup_service = CleanupService(db_session)

        # Create a valid player with token
        player = await player_factory()
        valid_token = RefreshToken(
            token_id=uuid4(),
            player_id=player.player_id,
            token_hash="valid_token_hash",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(valid_token)

        # Create orphaned token (non-existent player_id)
        orphaned_token = RefreshToken(
            token_id=uuid4(),
            player_id=uuid4(),  # Non-existent player
            token_hash="orphaned_token_hash",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(orphaned_token)
        await db_session.commit()

        # Cleanup should remove orphaned token
        deleted_count = await cleanup_service.cleanup_orphaned_refresh_tokens()

        assert deleted_count == 1

        # Verify valid token still exists
        await db_session.refresh(valid_token)
        assert valid_token.token_hash == "valid_token_hash"

    @pytest.mark.asyncio
    async def test_cleanup_expired_refresh_tokens(self, db_session, player_factory):
        """Should remove expired refresh tokens."""
        cleanup_service = CleanupService(db_session)
        player = await player_factory()

        # Create expired token
        expired_token = RefreshToken(
            token_id=uuid4(),
            player_id=player.player_id,
            token_hash="expired_token_hash",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.add(expired_token)

        # Create valid token
        valid_token = RefreshToken(
            token_id=uuid4(),
            player_id=player.player_id,
            token_hash="valid_token_hash",
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db_session.add(valid_token)
        await db_session.commit()

        # Cleanup should remove expired token
        deleted_count = await cleanup_service.cleanup_expired_refresh_tokens()

        assert deleted_count == 1

        # Verify valid token still exists
        await db_session.refresh(valid_token)
        assert valid_token.token_hash == "valid_token_hash"

    @pytest.mark.asyncio
    async def test_cleanup_expired_includes_revoked_tokens(self, db_session, player_factory):
        """Should remove expired tokens including revoked ones."""
        cleanup_service = CleanupService(db_session)
        player = await player_factory()

        # Create revoked token (still valid expiry but revoked)
        revoked_token = RefreshToken(
            token_id=uuid4(),
            player_id=player.player_id,
            token_hash="revoked_token_hash",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            revoked_at=datetime.now(UTC),
        )
        db_session.add(revoked_token)

        # Create non-revoked token
        valid_token = RefreshToken(
            token_id=uuid4(),
            player_id=player.player_id,
            token_hash="valid_token_hash",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            revoked_at=None,
        )
        db_session.add(valid_token)
        await db_session.commit()

        # Cleanup expired tokens (which includes revoked tokens)
        deleted_count = await cleanup_service.cleanup_expired_refresh_tokens()

        assert deleted_count == 1

        # Verify valid token still exists
        await db_session.refresh(valid_token)
        assert valid_token.token_hash == "valid_token_hash"

    @pytest.mark.asyncio
    async def test_cleanup_old_revoked_tokens(self, db_session, player_factory):
        """Should remove revoked tokens older than specified days."""
        cleanup_service = CleanupService(db_session)
        player = await player_factory()

        # Create old revoked token
        old_revoked_token = RefreshToken(
            token_id=uuid4(),
            player_id=player.player_id,
            token_hash="old_revoked_token_hash",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            revoked_at=datetime.now(UTC) - timedelta(days=31),
        )
        db_session.add(old_revoked_token)

        # Create recently revoked token (< 30 days)
        recent_revoked_token = RefreshToken(
            token_id=uuid4(),
            player_id=player.player_id,
            token_hash="recent_revoked_token_hash",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            revoked_at=datetime.now(UTC) - timedelta(days=15),
        )
        db_session.add(recent_revoked_token)
        await db_session.commit()

        # Cleanup should remove old revoked token
        deleted_count = await cleanup_service.cleanup_old_revoked_tokens(days_old=30)

        assert deleted_count == 1

        # Verify recent revoked token still exists
        await db_session.refresh(recent_revoked_token)
        assert recent_revoked_token.token_hash == "recent_revoked_token_hash"


class TestOrphanedRoundsCleanup:
    """Test orphaned rounds cleanup methods."""

    @pytest.mark.asyncio
    async def test_count_orphaned_rounds(self, db_session, player_factory):
        """Should count orphaned rounds correctly."""
        cleanup_service = CleanupService(db_session)
        player = await player_factory()

        # Create valid round
        valid_round = Round(
            round_id=uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test prompt",
            submitted_phrase="TEST",
        )
        db_session.add(valid_round)

        # Create orphaned rounds
        for i in range(3):
            orphaned_round = Round(
                round_id=uuid4(),
                player_id=uuid4(),  # Non-existent player
                round_type="copy" if i < 2 else "prompt",
                status="submitted",
                cost=100,
                expires_at=datetime.now(UTC) + timedelta(minutes=3),
            )
            db_session.add(orphaned_round)

        await db_session.commit()

        # Count orphaned rounds
        orphaned_count, by_type = await cleanup_service.count_orphaned_rounds()

        assert orphaned_count == 3
        assert by_type["copy"] == 2
        assert by_type["prompt"] == 1

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_rounds(self, db_session, player_factory):
        """Should remove orphaned rounds."""
        cleanup_service = CleanupService(db_session)
        player = await player_factory()

        # Count existing orphaned rounds before adding ours
        initial_count, _ = await cleanup_service.count_orphaned_rounds()

        # Create valid round
        valid_round = Round(
            round_id=uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test prompt",
            submitted_phrase="TEST",
        )
        db_session.add(valid_round)

        # Create orphaned round
        orphaned_round = Round(
            round_id=uuid4(),
            player_id=uuid4(),  # Non-existent player
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        db_session.add(orphaned_round)
        await db_session.commit()

        # Cleanup should remove orphaned round(s)
        deleted_count = await cleanup_service.cleanup_orphaned_rounds()

        # Should have removed at least our orphaned round plus any pre-existing
        assert deleted_count >= 1

        # Verify valid round still exists
        await db_session.refresh(valid_round)
        assert valid_round.round_type == "prompt"


class TestTestPlayerCleanup:
    """Test test player identification and cleanup."""

    @pytest.mark.asyncio
    async def test_get_test_players_identifies_patterns(self, db_session):
        """Should identify test players by username and email patterns."""
        cleanup_service = CleanupService(db_session)

        # Create test players matching patterns
        test_players_data = [
            ("testplayer123_456", "testplayer123_456@example.com"),
            ("stresstest789_012", "stresstest789_012@example.com"),
            ("test_user_abcd1234", "test_user_abcd1234@example.com"),
        ]

        for username, email in test_players_data:
            player = Player(
                player_id=uuid4(),
                username=username,
                username_canonical=username.lower(),
                email=email,
                password_hash=hash_password("test123"),
            )
            db_session.add(player)

        # Create regular player
        regular_player = Player(
            player_id=uuid4(),
            username="regularuser",
            username_canonical="regularuser",
            email="regular@example.com",
            password_hash=hash_password("password123"),
        )
        db_session.add(regular_player)
        await db_session.commit()

        # Get test players
        test_players = await cleanup_service.get_test_players()

        assert len(test_players) == 3
        test_usernames = {p.username for p in test_players}
        assert "testplayer123_456" in test_usernames
        assert "stresstest789_012" in test_usernames
        assert "test_user_abcd1234" in test_usernames
        assert "regularuser" not in test_usernames

    @pytest.mark.asyncio
    async def test_cleanup_test_players_dry_run(self, db_session):
        """Should return count without deleting in dry run mode."""
        cleanup_service = CleanupService(db_session)

        # Create test player with unique identifier to avoid conflicts
        unique_id = uuid4().hex[:8]
        test_player = Player(
            player_id=uuid4(),
            username=f"testplayer{unique_id}_999",
            username_canonical=f"testplayer{unique_id}_999",
            email=f"testplayer{unique_id}_999@example.com",
            password_hash=hash_password("test123"),
        )
        db_session.add(test_player)
        await db_session.commit()

        # Dry run cleanup
        result = await cleanup_service.cleanup_test_players(dry_run=True)

        # Should report at least our test player
        assert result["would_delete_players"] >= 1

        # Verify player still exists (dry run shouldn't delete)
        await db_session.refresh(test_player)
        assert test_player.username.startswith("testplayer")

    @pytest.mark.asyncio
    async def test_cleanup_test_players_deletes_related_data(self, db_session, player_factory):
        """Should delete test players and all related data."""
        cleanup_service = CleanupService(db_session)

        # Count existing test players
        initial_test_players = await cleanup_service.get_test_players()
        initial_count = len(initial_test_players)

        # Create test player
        test_player = Player(
            player_id=uuid4(),
            username="testplayer987_654",
            username_canonical="testplayer987_654",
            email="testplayer987_654@example.com",
            password_hash=hash_password("test123"),
        )
        db_session.add(test_player)
        await db_session.flush()

        # Create related data
        test_round = Round(
            round_id=uuid4(),
            player_id=test_player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test",
            submitted_phrase="TEST",
        )
        db_session.add(test_round)

        test_transaction = Transaction(
            transaction_id=uuid4(),
            player_id=test_player.player_id,
            amount=100,
            balance_after=1100,
            type="prompt_entry",
        )
        db_session.add(test_transaction)
        await db_session.commit()

        # Cleanup test players
        result = await cleanup_service.cleanup_test_players(dry_run=False)

        # Should anonymize at least our test player plus any pre-existing
        assert result.get("players_anonymized", 0) >= initial_count + 1
        # Note: Only non-submitted rounds are deleted
        assert result.get("transactions", 0) >= 1


class TestInactiveGuestCleanup:
    """Test inactive guest player cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_inactive_guest_players(self, db_session):
        """Should remove old guest accounts with no activity (no rounds, no phraseset activities)."""
        cleanup_service = CleanupService(db_session)

        # Create old inactive guest (hasn't logged in for > 7 days, no activity)
        old_guest = Player(
            player_id=uuid4(),
            username="OldGuest",
            username_canonical="oldguest",
            email="oldguest@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            created_at=datetime.now(UTC) - timedelta(days=10),
            last_login_date=datetime.now(UTC) - timedelta(days=10),
        )
        db_session.add(old_guest)

        # Create recent guest (logged in < 7 days ago)
        recent_guest = Player(
            player_id=uuid4(),
            username="RecentGuest",
            username_canonical="recentguest",
            email="recentguest@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            created_at=datetime.now(UTC) - timedelta(days=10),
            last_login_date=datetime.now(UTC) - timedelta(days=3),
        )
        db_session.add(recent_guest)
        await db_session.commit()

        # Store old_guest_id for verification
        old_guest_id = old_guest.player_id

        # Cleanup should remove old inactive guest
        deleted_count = await cleanup_service.cleanup_inactive_guest_players(hours_old=168)

        assert deleted_count == 1

        # Verify old guest was actually deleted from database
        result = await db_session.execute(
            select(Player).where(Player.player_id == old_guest_id)
        )
        assert result.scalar_one_or_none() is None

        # Verify recent guest still exists
        await db_session.refresh(recent_guest)
        assert recent_guest.username == "RecentGuest"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_active_guests(self, db_session):
        """Should not remove old guests who have played rounds."""
        cleanup_service = CleanupService(db_session)

        # Create old guest with rounds (hasn't logged in for > 7 days)
        active_guest = Player(
            player_id=uuid4(),
            username="ActiveGuest",
            username_canonical="activeguest",
            email="activeguest@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            created_at=datetime.now(UTC) - timedelta(days=10),
            last_login_date=datetime.now(UTC) - timedelta(days=10),  # Old login
        )
        db_session.add(active_guest)
        await db_session.flush()

        # Add round for this guest
        guest_round = Round(
            round_id=uuid4(),
            player_id=active_guest.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test",
            submitted_phrase="TEST",
        )
        db_session.add(guest_round)
        await db_session.commit()

        # Cleanup should not remove active guest (has submitted rounds)
        deleted_count = await cleanup_service.cleanup_inactive_guest_players(hours_old=168)

        assert deleted_count == 0

        # Verify guest still exists
        await db_session.refresh(active_guest)
        assert active_guest.username == "ActiveGuest"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_guests_with_phraseset_activity(self, db_session):
        """Should not remove old guests who have phraseset activity."""
        cleanup_service = CleanupService(db_session)

        # Create old guest with phraseset activity (hasn't logged in for > 7 days)
        active_guest = Player(
            player_id=uuid4(),
            username="ActiveGuestWithActivity",
            username_canonical="activeguestwithactivity",
            email="activeguestwithactivity@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            created_at=datetime.now(UTC) - timedelta(days=10),
            last_login_date=datetime.now(UTC) - timedelta(days=10),  # Old login
        )
        db_session.add(active_guest)
        await db_session.flush()

        # Create a phraseset
        phraseset = Phraseset(
            phraseset_id=uuid4(),
            prompt_round_id=uuid4(),
            copy_round_1_id=uuid4(),
            copy_round_2_id=uuid4(),
            prompt_text="Test prompt",
            original_phrase="TEST",
            copy_phrase_1="COPY1",
            copy_phrase_2="COPY2",
            created_at=datetime.now(UTC),
        )
        db_session.add(phraseset)
        await db_session.flush()

        # Add phraseset activity for this guest
        activity = PhrasesetActivity(
            activity_id=uuid4(),
            player_id=active_guest.player_id,
            phraseset_id=phraseset.phraseset_id,
            activity_type="vote",
            created_at=datetime.now(UTC) - timedelta(days=5),
        )
        db_session.add(activity)
        await db_session.commit()

        # Cleanup should not remove active guest (has phraseset activity)
        deleted_count = await cleanup_service.cleanup_inactive_guest_players(hours_old=168)

        assert deleted_count == 0

        # Verify guest still exists
        await db_session.refresh(active_guest)
        assert active_guest.username == "ActiveGuestWithActivity"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_new_guests_with_null_login(self, db_session):
        """Should not delete newly-created guests with NULL last_login_date."""
        cleanup_service = CleanupService(db_session)

        # Create newly-created guest with NULL last_login_date (should NOT be deleted)
        new_guest = Player(
            player_id=uuid4(),
            username="NewGuest",
            username_canonical="newguest",
            email="newguest@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            created_at=datetime.now(UTC) - timedelta(hours=1),  # Created 1 hour ago
            last_login_date=None,  # Never logged in
        )
        db_session.add(new_guest)

        # Create old guest with NULL last_login_date AND old created_at (should be deleted)
        old_guest_null_login = Player(
            player_id=uuid4(),
            username="OldGuestNullLogin",
            username_canonical="oldguestnulllogin",
            email="oldguestnulllogin@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            created_at=datetime.now(UTC) - timedelta(days=10),  # Created 10 days ago
            last_login_date=None,  # Never logged in
        )
        db_session.add(old_guest_null_login)
        await db_session.commit()

        # Store old_guest_id for verification
        old_guest_id = old_guest_null_login.player_id

        # Cleanup should only remove the old guest with NULL login
        deleted_count = await cleanup_service.cleanup_inactive_guest_players(hours_old=168)

        assert deleted_count == 1

        # Verify old guest with NULL login was deleted
        result = await db_session.execute(
            select(Player).where(Player.player_id == old_guest_id)
        )
        assert result.scalar_one_or_none() is None

        # Verify new guest still exists (not old enough to be deleted)
        await db_session.refresh(new_guest)
        assert new_guest.username == "NewGuest"


class TestRecycleGuestUsernames:
    """Test guest username recycling."""

    @pytest.mark.asyncio
    async def test_recycle_inactive_guest_usernames(self, db_session):
        """Should append X suffix to inactive guest usernames."""
        cleanup_service = CleanupService(db_session)

        # Create inactive guest (> 30 days since login)
        inactive_guest = Player(
            player_id=uuid4(),
            username="CoolName",
            username_canonical="coolname",
            email="coolname@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            last_login_date=datetime.now(UTC) - timedelta(days=35),
        )
        db_session.add(inactive_guest)
        await db_session.commit()

        # Recycle usernames
        recycled_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)

        assert recycled_count == 1

        # Verify username was recycled
        await db_session.refresh(inactive_guest)
        assert inactive_guest.username == "CoolName X"
        assert inactive_guest.username_canonical == "coolnamex"

    @pytest.mark.asyncio
    async def test_recycle_avoids_duplicate_suffixes(self, db_session):
        """Should not recycle usernames that already have X suffix."""
        cleanup_service = CleanupService(db_session)

        # Create inactive guest with X suffix already
        recycled_guest = Player(
            player_id=uuid4(),
            username="AlreadyRecycled X",
            username_canonical="alreadyrecycledx",
            email="alreadyrecycled@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            last_login_date=datetime.now(UTC) - timedelta(days=35),
            created_at=datetime.now(UTC) - timedelta(days=40),
        )
        db_session.add(recycled_guest)
        await db_session.commit()

        initial_username = recycled_guest.username

        # Recycle usernames
        recycled_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)

        # Verify username unchanged (it already has the X suffix)
        await db_session.refresh(recycled_guest)
        assert recycled_guest.username == initial_username

    @pytest.mark.asyncio
    async def test_recycle_handles_conflicts_with_numeric_suffix(self, db_session):
        """Should add numeric suffixes to avoid conflicts."""
        cleanup_service = CleanupService(db_session)

        # Create existing player with "UniqueName X" canonical
        existing_player = Player(
            player_id=uuid4(),
            username="UniqueName X",
            username_canonical="uniquenamex",
            email="existing_unique@example.com",
            password_hash=hash_password("password123"),
            is_guest=False,
            created_at=datetime.now(UTC) - timedelta(days=100),
        )
        db_session.add(existing_player)

        # Create inactive guest that would conflict
        inactive_guest = Player(
            player_id=uuid4(),
            username="UniqueName",
            username_canonical="uniquename",
            email="uniquename@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            last_login_date=datetime.now(UTC) - timedelta(days=35),
            created_at=datetime.now(UTC) - timedelta(days=40),
        )
        db_session.add(inactive_guest)
        await db_session.commit()

        # Recycle usernames
        recycled_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)

        assert recycled_count >= 1

        # Verify username got numeric suffix to avoid conflict
        await db_session.refresh(inactive_guest)
        assert inactive_guest.username.startswith("UniqueName X")
        assert inactive_guest.username != "UniqueName X"  # Should have number


class TestDeletePlayer:
    """Test individual player deletion."""

    @pytest.mark.asyncio
    async def test_delete_player_removes_all_related_data(self, db_session, player_factory):
        """Should delete player and all associated records."""
        cleanup_service = CleanupService(db_session)

        # Create player
        player = await player_factory()
        player_id = player.player_id

        # Create various related records
        test_round = Round(
            round_id=uuid4(),
            player_id=player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test",
            submitted_phrase="TEST",
        )
        db_session.add(test_round)

        test_transaction = Transaction(
            transaction_id=uuid4(),
            player_id=player_id,
            amount=100,
            balance_after=1100,
            type="prompt_entry",
        )
        db_session.add(test_transaction)

        test_bonus = DailyBonus(
            bonus_id=uuid4(),
            player_id=player_id,
            date=datetime.now(UTC).date(),
            amount=50,
        )
        db_session.add(test_bonus)
        await db_session.commit()

        # Delete player
        result = await cleanup_service.delete_player(player_id)

        assert result.get("players_anonymized", 0) == 1
        # Note: Only non-submitted rounds are deleted (submitted rounds are preserved)
        assert result.get("transactions", 0) >= 1
        assert result.get("daily_bonuses", 0) >= 1

    @pytest.mark.asyncio
    async def test_delete_nonexistent_player(self, db_session):
        """Should handle deletion of non-existent player gracefully."""
        cleanup_service = CleanupService(db_session)

        # Try to delete non-existent player
        result = await cleanup_service.delete_player(uuid4())

        # Should return empty dict or zero counts
        assert result.get("players_anonymized", 0) == 0


class TestRunAllCleanupTasks:
    """Test running all cleanup tasks together."""

    @pytest.mark.asyncio
    async def test_run_all_cleanup_tasks(self, db_session, player_factory):
        """Should run all cleanup tasks and return combined results."""
        cleanup_service = CleanupService(db_session)

        # Create some data to clean up
        player = await player_factory()

        # Expired token
        expired_token = RefreshToken(
            token_id=uuid4(),
            player_id=player.player_id,
            token_hash="expired_token_hash",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.add(expired_token)

        # Orphaned round
        orphaned_round = Round(
            round_id=uuid4(),
            player_id=uuid4(),  # Non-existent player
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        db_session.add(orphaned_round)

        # Old inactive guest
        old_guest = Player(
            player_id=uuid4(),
            username="OldGuest",
            username_canonical="oldguest",
            email="oldguest@example.com",
            password_hash=hash_password("guest123"),
            is_guest=True,
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        db_session.add(old_guest)
        await db_session.commit()

        # Run all cleanup tasks
        results = await cleanup_service.run_all_cleanup_tasks()

        # Verify results contain expected keys
        assert "orphaned_tokens" in results
        assert "expired_tokens" in results
        assert "old_revoked_tokens" in results
        assert "orphaned_rounds" in results
        assert "inactive_guests" in results
        assert "recycled_guest_usernames" in results

        # Should have cleaned up at least some items
        assert results["expired_tokens"] >= 1
        assert results["orphaned_rounds"] >= 1
        assert results["inactive_guests"] >= 1


class TestRecycledSuffixDetection:
    """Test the _has_recycled_suffix helper method."""

    def test_detects_single_x_suffix(self):
        """Should detect ' X' suffix."""
        assert CleanupService._has_recycled_suffix("Username X") is True

    def test_detects_numeric_x_suffix(self):
        """Should detect ' X#' suffix."""
        assert CleanupService._has_recycled_suffix("Username X2") is True
        assert CleanupService._has_recycled_suffix("Username X42") is True

    def test_rejects_non_suffixed_usernames(self):
        """Should return False for usernames without X suffix."""
        assert CleanupService._has_recycled_suffix("Username") is False
        assert CleanupService._has_recycled_suffix("UserX") is False  # No space
        assert CleanupService._has_recycled_suffix("X Username") is False  # X at start

    def test_handles_none_username(self):
        """Should handle None username."""
        assert CleanupService._has_recycled_suffix(None) is False

    def test_handles_empty_username(self):
        """Should handle empty username."""
        assert CleanupService._has_recycled_suffix("") is False
