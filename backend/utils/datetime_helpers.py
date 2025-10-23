"""Datetime utility functions for timezone handling."""
from datetime import datetime, UTC
from typing import Optional


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is timezone-aware in UTC.

    This utility handles the common case where datetimes from the database
    may be timezone-naive but should be treated as UTC.

    Args:
        dt: Datetime to normalize (can be None)

    Returns:
        UTC-aware datetime or None if input was None

    Example:
        >>> naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        >>> aware_dt = ensure_utc(naive_dt)
        >>> aware_dt.tzinfo == UTC
        True

        >>> ensure_utc(None) is None
        True

        >>> already_aware = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        >>> ensure_utc(already_aware) == already_aware
        True
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
