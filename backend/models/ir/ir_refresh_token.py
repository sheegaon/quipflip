"""IR RefreshToken model."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class IRRefreshToken(Base):
    """Refresh tokens for IR JWT authentication."""

    __tablename__ = "ir_refresh_tokens"

    token_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ir_refresh_token_id", token_id),
        Index("ix_ir_refresh_token_player_id", player_id),
        Index("ix_ir_refresh_token_hash", token_hash),
    )

    # Relationships
    player = relationship("IRPlayer", back_populates="refresh_tokens")

    def is_active(self, now: datetime) -> bool:
        """Check if token is active (not expired or revoked)."""
        return self.revoked_at is None and self.expires_at > now
