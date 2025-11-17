"""Player model."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Boolean,
    Integer,
)
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from backend.models.player_base import PlayerBase
from backend.models.base import get_uuid_column


class QFPlayer(PlayerBase):
    """Player account model."""
    __tablename__ = "qf_players"

    # QF-specific fields
    active_round_id = get_uuid_column(ForeignKey("qf_rounds.round_id", ondelete="SET NULL"), nullable=True)
    flag_dismissal_streak = Column(Integer, default=0, nullable=False)

    # Tutorial tracking
    tutorial_completed = Column(Boolean, default=False, nullable=False)
    tutorial_progress = Column(String(20), default='not_started', nullable=False)
    tutorial_started_at = Column(DateTime(timezone=True), nullable=True)
    tutorial_completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("username_canonical", name="uq_players_username_canonical"),
    )

    # Relationships
    active_round = relationship("Round", foreign_keys=[active_round_id], post_update=True)
    rounds = relationship("Round", back_populates="player", foreign_keys="Round.player_id")
    transactions = relationship("Transaction", back_populates="player")
    votes = relationship("Vote", back_populates="player")
    daily_bonuses = relationship("DailyBonus", back_populates="player")
    result_views = relationship("ResultView", back_populates="player")
    abandoned_prompts = relationship("PlayerAbandonedPrompt", back_populates="player")
    phraseset_activities = relationship("PhrasesetActivity", back_populates="player")
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="player",
        cascade="all, delete-orphan",
    )
    quests = relationship("Quest", back_populates="player")
