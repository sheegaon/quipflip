"""Meme Mint player data model."""
from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    Boolean,
    String,
)
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class MMPlayerData(Base):
    """Meme Mint-specific player data.

    Contains wallet, vault, tutorial progress, and other MM-specific
    fields. One entry per player per game.
    """

    __tablename__ = "mm_player_data"

    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
    wallet = Column(Integer, default=1000, nullable=False)
    vault = Column(Integer, default=0, nullable=False)

    # Tutorial tracking
    tutorial_completed = Column(Boolean, default=False, nullable=False)
    tutorial_progress = Column(String(20), default='not_started', nullable=False)
    tutorial_started_at = Column(DateTime(timezone=True), nullable=True)
    tutorial_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Guest vote lockout tracking (per-game)
    consecutive_incorrect_votes = Column(Integer, default=0, nullable=False)
    vote_lockout_until = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    transactions = relationship("MMTransaction", back_populates="player", cascade="all, delete-orphan")
    refresh_tokens = relationship("MMRefreshToken", back_populates="player", cascade="all, delete-orphan")
    daily_bonuses = relationship("MMDailyBonus", back_populates="player", cascade="all, delete-orphan")
    vote_rounds = relationship("MMVoteRound", back_populates="player", cascade="all, delete-orphan")
    captions = relationship("MMCaption", back_populates="author", cascade="all, delete-orphan")
    caption_submissions = relationship(
        "MMCaptionSubmission", back_populates="player", cascade="all, delete-orphan"
    )
    caption_seen_records = relationship(
        "MMCaptionSeen", back_populates="player", cascade="all, delete-orphan"
    )
    daily_states = relationship(
        "MMPlayerDailyState", back_populates="player", cascade="all, delete-orphan"
    )
    created_circles = relationship(
        "MMCircle",
        foreign_keys="MMCircle.created_by_player_id",
        back_populates="created_by"
    )
    circle_memberships = relationship(
        "MMCircleMember",
        back_populates="player"
    )
    circle_join_requests = relationship(
        "MMCircleJoinRequest",
        foreign_keys="MMCircleJoinRequest.player_id",
        back_populates="player"
    )

    def __repr__(self):
        return (f"<MMPlayerData(player_id={self.player_id}, "
                f"wallet={self.wallet}, vault={self.vault})>")
