"""Tests for datetime helper utilities."""
from datetime import UTC, datetime, timedelta, timezone

from backend.utils.datetime_helpers import ensure_utc


def test_ensure_utc_none_returns_none():
    """The helper should gracefully handle ``None`` inputs."""

    assert ensure_utc(None) is None


def test_ensure_utc_attaches_timezone_to_naive_datetime():
    """Naive datetimes should be marked as UTC without adjusting the clock."""

    naive = datetime(2024, 5, 1, 12, 30, 0)

    result = ensure_utc(naive)

    assert result.tzinfo is UTC
    assert result.replace(tzinfo=None) == naive


def test_ensure_utc_converts_from_other_timezones_to_utc():
    """Timezone-aware datetimes not already UTC should be converted."""

    eastern = timezone(timedelta(hours=-4))
    aware = datetime(2024, 5, 1, 8, 0, tzinfo=eastern)

    result = ensure_utc(aware)

    assert result.tzinfo is UTC
    assert result.hour == 12
    assert result.replace(tzinfo=None) == datetime(2024, 5, 1, 12, 0)
