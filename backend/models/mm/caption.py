"""Meme Mint caption model with stats and economy aggregates."""
import uuid
from datetime import datetime, UTC

from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    Boolean,
    Float,
)
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMCaption(Base):
    """Captions tied to meme images with selection stats."""

    __tablename__ = "mm_captions"

    caption_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    image_id = get_uuid_column(
        ForeignKey("mm_images.image_id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind = Column(String(20), nullable=False)
    parent_caption_id = get_uuid_column(
        ForeignKey("mm_captions.caption_id", ondelete="SET NULL"), nullable=True, index=True
    )
    text = Column(String(240), nullable=False)
    status = Column(String(20), default="active", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    shows = Column(Integer, default=0, nullable=False)
    picks = Column(Integer, default=0, nullable=False)
    first_vote_awarded = Column(Boolean, default=False, nullable=False)
    quality_score = Column(Float, default=0.0, nullable=False)

    lifetime_earnings_gross = Column(Integer, default=0, nullable=False)
    lifetime_to_wallet = Column(Integer, default=0, nullable=False)
    lifetime_to_vault = Column(Integer, default=0, nullable=False)

    # Relationships
    image = relationship("MMImage", back_populates="captions")
    author = relationship("MMPlayer", back_populates="captions", foreign_keys=[author_player_id])
    parent_caption = relationship("MMCaption", remote_side=[caption_id])
    vote_rounds = relationship("MMVoteRound", back_populates="chosen_caption", foreign_keys="MMVoteRound.chosen_caption_id")
    seen_records = relationship("MMCaptionSeen", back_populates="caption", cascade="all, delete-orphan")
    riff_children = relationship(
        "MMCaption",
        back_populates="parent_caption",
        cascade="all, delete-orphan",
        foreign_keys=[parent_caption_id],
    )

    __table_args__ = (
        Index("ix_mm_captions_image_status", "image_id", "status"),
        Index("ix_mm_captions_author", "author_player_id"),
        Index("ix_mm_captions_parent", "parent_caption_id"),
        Index("ix_mm_captions_status_quality", "status", "quality_score"),
    )

    def __repr__(self) -> str:
        return f"<MMCaption(caption_id={self.caption_id}, status={self.status})>"
