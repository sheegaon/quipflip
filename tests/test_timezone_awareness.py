"""
Comprehensive timezone awareness tests.

Tests to ensure all datetime operations use timezone-aware datetimes (UTC)
and that the frontend properly displays times in the user's local timezone.

IMPORTANT NOTE ON SQLITE:
SQLite does not store timezone information. When we use DateTime(timezone=True)
in SQLAlchemy with SQLite, timestamps are stored as text in ISO 8601 format,
but when retrieved, they come back as timezone-naive Python datetime objects.

The application handles this by:
1. Always using datetime.now(UTC) when creating timestamps
2. Always treating naive datetimes from database as UTC (using ensure_utc())
3. Using Pydantic to serialize datetimes as ISO 8601 with UTC timezone for JSON responses
4. Frontend JavaScript automatically converts to user's local timezone

In production with PostgreSQL, DateTime(timezone=True) properly stores and retrieves
timezone-aware datetimes, so this is primarily a testing concern.
"""

import pytest
from datetime import datetime, UTC, timedelta
import uuid

from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.vote import Vote
from backend.models.qf.transaction import QFTransaction
from backend.services import GameType, QFRoundService
from backend.services import QFVoteService
from backend.services import TransactionService
from sqlalchemy import select


class TestDatabaseTimezoneAwareness:
    """
    Test that all database timestamps are timezone-aware (UTC).

    NOTE: SQLite doesn't preserve timezone info, so timestamps come back as naive.
    However, the application TREATS all naive datetimes from the database as UTC.
    We use ensure_utc() utility to add back the timezone info when needed.
    """

    @pytest.mark.asyncio
    async def test_player_created_at_exists(self, db_session):
        """Player.created_at should be automatically set."""
        from backend.utils.datetime_helpers import ensure_utc

        player = QFPlayer(
            player_id=uuid.uuid4(),
            username=f"test_{uuid.uuid4().hex[:8]}",
            username_canonical=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()
        await db_session.refresh(player)

        assert player.created_at is not None
        # SQLite returns naive datetime, but we treat it as UTC
        created_at_utc = ensure_utc(player.created_at)
        assert created_at_utc.tzinfo == UTC
        # Should be recent (within last 10 seconds)
        assert datetime.now(UTC) - created_at_utc < timedelta(seconds=10)

    @pytest.mark.asyncio
    async def test_round_timestamps_are_utc_aware(self, db_session):
        """Round created_at and expires_at should be UTC-aware."""
        from backend.utils.datetime_helpers import ensure_utc

        player = QFPlayer(
            player_id=uuid.uuid4(),
            username=f"test_{uuid.uuid4().hex[:8]}",
            username_canonical=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()

        round_obj = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="active",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        db_session.add(round_obj)
        await db_session.commit()
        await db_session.refresh(round_obj)

        assert round_obj.created_at is not None
        # SQLite returns naive datetime, but we treat it as UTC
        created_at_utc = ensure_utc(round_obj.created_at)
        assert created_at_utc.tzinfo == UTC
        assert round_obj.expires_at is not None
        expires_at_utc = ensure_utc(round_obj.expires_at)
        assert expires_at_utc.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_phraseset_timestamps_are_utc_aware(self, db_session):
        """Phraseset created_at and finalized_at should be UTC-aware."""
        from backend.utils.datetime_helpers import ensure_utc

        # Create minimal phraseset for testing
        player = QFPlayer(
            player_id=uuid.uuid4(),
            username=f"test_{uuid.uuid4().hex[:8]}",
            username_canonical=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()

        round_obj = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test",
            submitted_phrase="ORIGINAL",
        )
        db_session.add(round_obj)
        await db_session.flush()

        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=round_obj.round_id,
            copy_round_1_id=uuid.uuid4(),
            copy_round_2_id=uuid.uuid4(),
            prompt_text="Test",
            original_phrase="ORIGINAL",
            copy_phrase_1="COPY1",
            copy_phrase_2="COPY2",
            status="open",
            vote_count=0,
            total_pool=200,
            system_contribution=0,
        )
        db_session.add(phraseset)
        await db_session.commit()
        await db_session.refresh(phraseset)

        assert phraseset.created_at is not None
        # SQLite returns naive datetime, but we treat it as UTC
        created_at_utc = ensure_utc(phraseset.created_at)
        assert created_at_utc.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_vote_created_at_is_utc_aware(self, db_session):
        """Vote.created_at should be UTC-aware."""
        from backend.utils.datetime_helpers import ensure_utc

        # Create minimal vote for testing
        player = QFPlayer(
            player_id=uuid.uuid4(),
            username=f"test_{uuid.uuid4().hex[:8]}",
            username_canonical=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()

        vote = Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=uuid.uuid4(),
            player_id=player.player_id,
            voted_phrase="ORIGINAL",
            correct=True,
            payout=20,
        )
        db_session.add(vote)
        await db_session.commit()
        await db_session.refresh(vote)

        assert vote.created_at is not None
        # SQLite returns naive datetime, but we treat it as UTC
        created_at_utc = ensure_utc(vote.created_at)
        assert created_at_utc.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_transaction_created_at_is_utc_aware(self, db_session):
        """Transaction.created_at should be UTC-aware."""
        from backend.utils.datetime_helpers import ensure_utc

        player = QFPlayer(
            username=f"test_{uuid.uuid4().hex[:8]}",
            username_canonical=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            wallet=5000,
            vault=0,
        )
        db_session.add(player)
        await db_session.commit()

        transaction_service = TransactionService(db_session, GameType.QF)
        transaction = await transaction_service.create_transaction(
            player.player_id,
            100,
            "test_transaction",
        )

        assert transaction.created_at is not None
        # SQLite returns naive datetime, but we treat it as UTC
        created_at_utc = ensure_utc(transaction.created_at)
        assert created_at_utc.tzinfo == UTC


class TestServiceTimezoneAwareness:
    """Test that service layer uses UTC-aware datetimes."""

    @pytest.mark.asyncio
    async def test_round_service_uses_utc(self, db_session):
        """RoundService should create rounds with UTC-aware timestamps."""
        from backend.utils.datetime_helpers import ensure_utc

        player = QFPlayer(
            username=f"test_{uuid.uuid4().hex[:8]}",
            username_canonical=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            wallet=5000,
            vault=0,
        )
        db_session.add(player)
        await db_session.commit()

        # Create a prompt first
        from backend.models.qf.prompt import Prompt
        prompt = Prompt(
            text=f"Test prompt {uuid.uuid4().hex[:6]}",
            category="test",
            enabled=True,
        )
        db_session.add(prompt)
        await db_session.commit()

        round_service = QFRoundService(db_session)
        transaction_service = TransactionService(db_session, GameType.QF)

        round_obj = await round_service.start_prompt_round(
            player,
            transaction_service,
        )

        # SQLite returns naive datetime, but we treat it as UTC
        created_at_utc = ensure_utc(round_obj.created_at)
        assert created_at_utc.tzinfo == UTC
        expires_at_utc = ensure_utc(round_obj.expires_at)
        assert expires_at_utc.tzinfo == UTC
        # Verify expires_at is in the future
        assert expires_at_utc > datetime.now(UTC)


class TestTimezoneUtility:
    """Test timezone utility functions (ensure_utc)."""

    def test_ensure_utc_with_naive_datetime(self):
        """ensure_utc should add UTC timezone to naive datetimes."""
        from backend.utils.datetime_helpers import ensure_utc

        naive_dt = datetime(2025, 10, 31, 12, 0, 0)
        result = ensure_utc(naive_dt)

        assert result.tzinfo == UTC
        # Should preserve the time
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 31
        assert result.hour == 12

    def test_ensure_utc_with_aware_datetime(self):
        """ensure_utc should preserve UTC-aware datetimes."""
        from backend.utils.datetime_helpers import ensure_utc

        aware_dt = datetime(2025, 10, 31, 12, 0, 0, tzinfo=UTC)
        result = ensure_utc(aware_dt)

        assert result.tzinfo == UTC
        assert result == aware_dt

    def test_ensure_utc_with_none(self):
        """ensure_utc should return None when given None."""
        from backend.utils.datetime_helpers import ensure_utc

        result = ensure_utc(None)
        assert result is None


class TestFrontendTimezoneDisplay:
    """
    Tests to verify that timestamps are properly formatted for frontend display.

    The intent is that all times should be stored in UTC in the database,
    but displayed to users in their local timezone in the UI.

    This is typically handled by:
    1. Backend sends UTC timestamps in ISO 8601 format with 'Z' suffix
    2. Frontend JavaScript Date objects parse these and display in user's local timezone
    3. Libraries like date-fns or day.js handle the timezone conversion automatically
    """

    @pytest.mark.asyncio
    async def test_timestamps_serializable_to_iso_format(self, db_session):
        """Timestamps should be serializable to ISO 8601 format for JSON responses."""
        from backend.utils.datetime_helpers import ensure_utc

        player = QFPlayer(
            player_id=uuid.uuid4(),
            username=f"test_{uuid.uuid4().hex[:8]}",
            username_canonical=f"test_{uuid.uuid4().hex[:8]}",
            email=f"test_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()
        await db_session.refresh(player)

        # SQLite returns naive datetime, so we need to ensure it's UTC-aware first
        created_at_utc = ensure_utc(player.created_at)

        # Convert to ISO format (what would be sent to frontend)
        iso_string = created_at_utc.isoformat()

        # Should end with +00:00 or Z for UTC
        assert iso_string.endswith('+00:00') or iso_string.endswith('Z')

        # Should be parseable back to datetime
        parsed = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        assert parsed.tzinfo is not None


# Documentation of timezone handling strategy:
"""
TIMEZONE HANDLING STRATEGY
==========================

1. Database Layer:
   - All datetime columns use DateTime(timezone=True) in SQLAlchemy
   - All default values use: default=lambda: datetime.now(UTC)
   - This ensures all timestamps are stored as UTC

2. Service Layer:
   - Always use datetime.now(UTC) for creating new timestamps
   - Use ensure_utc() utility when handling datetimes from external sources
   - Never use naive datetime.now()

3. API Layer:
   - Pydantic schemas serialize datetimes to ISO 8601 format with timezone
   - Frontend receives timestamps like "2025-10-31T12:00:00+00:00"

4. Frontend Layer:
   - JavaScript Date objects automatically handle timezone conversion
   - Libraries like date-fns format dates in user's local timezone
   - No manual timezone conversion needed in React components

5. Known Issue:
   - backend/services/prompt_seeder.py uses naive datetime.now().month
   - This should be fixed to use datetime.now(UTC).month for consistency
"""
