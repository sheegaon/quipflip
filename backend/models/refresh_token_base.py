"""Base RefreshToken model with common fields and functionality."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class RefreshTokenBase(Base):
    """Base refresh token model for JWT authentication."""
    
    __abstract__ = True

    token_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    def is_active(self, now: datetime | None = None) -> bool:
        """Return True if token has not expired or been revoked."""
        current_time = now or datetime.now(UTC)
        expires_at = self.expires_at

        # SQLite stores timestamps without timezone info; normalize to UTC so comparisons work.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        return self.revoked_at is None and expires_at > current_time

    def __repr__(self):
        return (f"<{self.__class__.__name__}(token_id={self.token_id}, player_id={self.player_id}, "
                f"expires_at={self.expires_at})>")
