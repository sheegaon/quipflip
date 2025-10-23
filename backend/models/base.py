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

            def operate(self, op, other, **kwargs):
                # For PostgreSQL with native UUID, use standard comparison
                if self._is_native_uuid():
                    return super().operate(op, other, **kwargs)

                # For SQLite/String storage with legacy data, normalize for comparison
                # but only for explicit equality/membership operations
                if isinstance(other, ClauseElement) or hasattr(other, "__clause_element__"):
                    return super().operate(op, other, **kwargs)

                # For explicit comparisons, normalize both sides
                if op in (operators.eq, operators.ne, operators.in_op, operators.notin_op):
                    normalized_expr = func.lower(func.replace(self.expr, "-", ""))

                    if op in (operators.in_op, operators.notin_op):
                        # Normalize list/tuple values
                        if isinstance(other, (list, tuple, set)):
                            normalized_values = []
                            for v in other:
                                if isinstance(v, uuid.UUID):
                                    normalized_values.append(v.hex)
                                else:
                                    normalized_values.append(str(v).replace("-", "").lower())
                            return op(normalized_expr, normalized_values)

                    # Normalize single value
                    if isinstance(other, uuid.UUID):
                        normalized_value = other.hex
                    else:
                        normalized_value = str(other).replace("-", "").lower()

                    return op(normalized_expr, normalized_value)

                # For all other operations, use default behavior
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
