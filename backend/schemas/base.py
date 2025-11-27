"""Base schemas with common configuration."""
from datetime import datetime, UTC
from pydantic import BaseModel, ConfigDict, field_serializer


def serialize_datetime_utc(dt: datetime) -> str:
    """
    Serialize datetime to ISO 8601 with explicit UTC timezone.

    This ensures JavaScript's Date constructor interprets the timestamp correctly.
    SQLite stores datetimes as naive strings, so we treat them as UTC.
    """
    if dt.tzinfo is None:
        # Treat naive datetimes as UTC
        dt = dt.replace(tzinfo=UTC)
    # Convert to UTC and format with 'Z' suffix
    return dt.astimezone(UTC).isoformat().replace('+00:00', 'Z')


class BaseSchema(BaseModel):
    """Base schema with common configuration for all API responses."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    @field_serializer("*", when_used="json")
    def serialize_field(self, value):
        """Serialize field values with custom datetime handling."""

        def _convert(value):
            if isinstance(value, datetime):
                return serialize_datetime_utc(value)
            if isinstance(value, list):
                return [_convert(item) for item in value]
            if isinstance(value, dict):
                return {key: _convert(item) for key, item in value.items()}
            return value

        return _convert(value)
