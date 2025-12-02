"""Meme Mint image catalog model."""
import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMImage(Base):
    """Stores meme images available for caption rounds."""

    __tablename__ = "mm_images"

    image_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    source_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    attribution_text = Column(String(255), nullable=True)
    tags = Column(JSON, nullable=True)
    status = Column(String(20), default="active", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    created_by_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    captions = relationship("MMCaption", back_populates="image", cascade="all, delete-orphan")
    vote_rounds = relationship("MMVoteRound", back_populates="image", cascade="all, delete-orphan")
    created_by = relationship("MMPlayer", foreign_keys=[created_by_player_id])

    def __repr__(self) -> str:
        return f"<MMImage(image_id={self.image_id}, status={self.status})>"
