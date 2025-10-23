"""Base utilities for SQLAlchemy models."""
from enum import Enum
import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import sqltypes, operators
from sqlalchemy.sql import func
from sqlalchemy.sql.elements import ClauseElement


class RoundType(str, Enum):
    """Round type enumeration for type safety."""
    PROMPT = "prompt"
    COPY = "copy"
    VOTE = "vote"


class RoundStatus(str, Enum):
    """Round status enumeration for type safety."""
    ACTIVE = "active"
    SUBMITTED = "submitted"
    EXPIRED = "expired"
    ABANDONED = "abandoned"


class WordSetStatus(str, Enum):
    """WordSet status enumeration for type safety."""
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"
    FINALIZED = "finalized"


def get_uuid_column(*args, **kwargs):
    """Get UUID column type based on database dialect.

    Returns a SQLAlchemy Column configured for UUID storage.
    Uses a type that adapts based on the actual database dialect at runtime.

    Args:
        *args: Positional arguments to pass to Column (e.g., ForeignKey)
        **kwargs: Keyword arguments to pass to Column (e.g., primary_key=True)

    Returns:
        Column: Configured SQLAlchemy Column for UUID storage

    Example:
        player_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
        foreign_id = get_uuid_column(ForeignKey("table.id"), nullable=True)
    """
    class AdaptiveUUID(sqltypes.TypeDecorator):
        """UUID type that keeps legacy hex-with-no-hyphen values compatible."""

        impl = sqltypes.String
        cache_ok = True

        class Comparator(sqltypes.TypeDecorator.Comparator):
            """Comparator that normalizes UUIDs for legacy SQLite rows."""

            def _is_native_uuid(self) -> bool:
                return getattr(self.type, "_uses_native_uuid", False)

            def _normalize_single(self, value):
                if value is None:
                    return None
                if isinstance(value, ClauseElement) or hasattr(value, "__clause_element__"):
                    return value
                if self._is_native_uuid():
                    if isinstance(value, uuid.UUID):
                        return value
                    return uuid.UUID(str(value))
                if isinstance(value, uuid.UUID):
                    return value.hex
                return str(value).replace("-", "").lower()

            def _normalize(self, other):
                if isinstance(other, (list, tuple, set)):
                    return [self._normalize_single(v) for v in other]
                return self._normalize_single(other)

            def _normalized_expr(self):
                if self._is_native_uuid():
                    return self.expr
                # Remove hyphens/lowercase so legacy hex IDs still match.
                return func.lower(func.replace(self.expr, "-", ""))

            def operate(self, op, other, **kwargs):
                if isinstance(other, ClauseElement) or hasattr(other, "__clause_element__"):
                    return super().operate(op, other, **kwargs)
                if op in (operators.eq, operators.ne):
                    return op(self._normalized_expr(), self._normalize(other))
                if op in (operators.in_op, operators.notin_op):
                    return op(self._normalized_expr(), self._normalize(other))
                return super().operate(op, other, **kwargs)

        comparator_factory = Comparator

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._uses_native_uuid = False

        def load_dialect_impl(self, dialect):
            self._uses_native_uuid = dialect.name == "postgresql"
            if self._uses_native_uuid:
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(String(36))

        @staticmethod
        def _coerce_uuid(value):
            if value is None or isinstance(value, uuid.UUID):
                return value
            return uuid.UUID(str(value))

        def process_bind_param(self, value, dialect):
            value = self._coerce_uuid(value)
            if value is None:
                return None
            if self._uses_native_uuid:
                return value
            # Store as lowercase hex so both legacy and new rows share format.
            return value.hex

        def process_result_value(self, value, dialect):
            if value is None:
                return None
            if self._uses_native_uuid:
                return self._coerce_uuid(value)
            # Stored as text/hex – convert back to UUID.
            return uuid.UUID(str(value))

    return Column(
        AdaptiveUUID(),
        *args,
        **kwargs
    )
