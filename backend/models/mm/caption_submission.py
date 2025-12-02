"""Submission log for Meme Mint captions."""
import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMCaptionSubmission(Base):
    """Logs caption submissions for moderation and analytics."""

    __tablename__ = "mm_caption_submissions"

    submission_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False
    )
    image_id = get_uuid_column(
        ForeignKey("mm_images.image_id", ondelete="CASCADE"), nullable=False
    )
    caption_id = get_uuid_column(
        ForeignKey("mm_captions.caption_id", ondelete="SET NULL"), nullable=True
    )
    submission_text = Column(String(240), nullable=False)
    status = Column(String(20), nullable=False)
    rejection_reason = Column(String(100), nullable=True)
    used_free_slot = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    player = relationship("MMPlayer", back_populates="caption_submissions")
    image = relationship("MMImage")
    caption = relationship("MMCaption")

    __table_args__ = (
        Index("ix_mm_caption_submission_status_created", "status", "created_at"),
        Index("ix_mm_caption_submission_player", "player_id"),
        Index("ix_mm_caption_submission_image", "image_id"),
        Index("ix_mm_caption_submission_caption", "caption_id"),
    )

    def __repr__(self) -> str:
        return f"<MMCaptionSubmission(submission_id={self.submission_id}, status={self.status})>"
