"""Base utilities for SQLAlchemy models."""
from enum import Enum
import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import sqltypes


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
        """A UUID type that adapts to the database dialect."""
        impl = sqltypes.String
        cache_ok = True
        
        def load_dialect_impl(self, dialect):
            if dialect.name == 'postgresql':
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            else:
                return dialect.type_descriptor(String(36))
        
        def process_bind_param(self, value, dialect):
            """Convert UUID to string for non-PostgreSQL databases."""
            if value is None:
                return value
            elif dialect.name == 'postgresql':
                return value  # PostgreSQL handles UUID objects directly
            else:
                # Convert UUID to string for SQLite and other databases
                if isinstance(value, uuid.UUID):
                    return str(value)
                return str(value)
        
        def process_result_value(self, value, dialect):
            """Convert string back to UUID for non-PostgreSQL databases."""
            if value is None:
                return value
            elif dialect.name == 'postgresql':
                return value  # PostgreSQL returns UUID objects directly
            else:
                # Convert string back to UUID for SQLite and other databases
                if isinstance(value, str):
                    return uuid.UUID(value)
                return value
    
    return Column(
        AdaptiveUUID(),
        *args,
        **kwargs
    )
