"""Custom JSON encoder for FastAPI responses."""
from fastapi.encoders import jsonable_encoder
from datetime import datetime, UTC
from typing import Any


def custom_jsonable_encoder(obj: Any) -> Any:
    """
    Custom JSON encoder that ensures datetimes are serialized with UTC timezone.

    SQLite stores datetimes as naive strings. When FastAPI serializes them,
    we need to ensure they include the 'Z' suffix so JavaScript interprets them as UTC.
    """
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            # Treat naive datetimes as UTC
            obj = obj.replace(tzinfo=UTC)
        # Format as ISO 8601 with 'Z' suffix
        return obj.astimezone(UTC).isoformat().replace('+00:00', 'Z')

    if isinstance(obj, dict):
        return {key: custom_jsonable_encoder(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [custom_jsonable_encoder(item) for item in obj]

    # Use FastAPI's default encoder for other types
    return jsonable_encoder(obj)
