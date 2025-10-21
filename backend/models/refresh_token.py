"""Refresh token persistence model."""
from datetime import datetime, UTC
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class RefreshToken(Base):
    """Stored refresh tokens for JWT authentication."""

    __tablename__ = "refresh_tokens"

    token_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    player = relationship("Player", back_populates="refresh_tokens")

    def is_active(self, now: datetime | None = None) -> bool:
        """Return True if token has not expired or been revoked."""
        current_time = now or datetime.now(UTC)
        expires_at = self.expires_at

        if expires_at is None:
            return False

        # SQLite stores timestamps without timezone info; normalize to UTC so comparisons work.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        return self.revoked_at is None and expires_at > current_time
