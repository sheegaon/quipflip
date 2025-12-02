"""Per-player caption history to avoid repeats."""
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMCaptionSeen(Base):
    """Tracks captions a player has already seen for a given image."""

    __tablename__ = "mm_captions_seen"

    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), primary_key=True
    )
    caption_id = get_uuid_column(
        ForeignKey("mm_captions.caption_id", ondelete="CASCADE"), primary_key=True
    )
    image_id = get_uuid_column(
        ForeignKey("mm_images.image_id", ondelete="CASCADE"), nullable=False
    )
    first_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    player = relationship("MMPlayer", back_populates="caption_seen_records")
    caption = relationship("MMCaption", back_populates="seen_records")
    image = relationship("MMImage")

    __table_args__ = (
        Index("ix_mm_caption_seen_player_image", "player_id", "image_id"),
        Index("ix_mm_caption_seen_caption", "caption_id"),
    )

    def __repr__(self) -> str:
        return f"<MMCaptionSeen(player_id={self.player_id}, caption_id={self.caption_id})>"
