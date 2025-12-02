"""Quipflip player data model."""
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


class QFPlayerData(Base):
    """Quipflip-specific player data.

    Contains wallet, vault, tutorial progress, and other QF-specific
    fields. One entry per player per game.
    """

    __tablename__ = "qf_player_data"

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

    # QF-specific fields
    active_round_id = get_uuid_column(
        ForeignKey("qf_rounds.round_id", ondelete="SET NULL"),
        nullable=True
    )
    flag_dismissal_streak = Column(Integer, default=0, nullable=False)

    # Relationships
    active_round = relationship("Round", foreign_keys=[active_round_id], post_update=True)
    rounds = relationship("Round", back_populates="player", foreign_keys="Round.player_id")
    transactions = relationship("QFTransaction", back_populates="player")
    votes = relationship("Vote", back_populates="player")
    daily_bonuses = relationship("QFDailyBonus", back_populates="player")
    result_views = relationship("QFResultView", back_populates="player")
    abandoned_prompts = relationship("PlayerAbandonedPrompt", back_populates="player")
    phraseset_activities = relationship("PhrasesetActivity", back_populates="player")
    quests = relationship("QFQuest", back_populates="player")

    @property
    def balance(self) -> int:
        """Return the player's total liquid balance (wallet + vault)."""
        return int(self.wallet or 0) + int(self.vault or 0)

    def __repr__(self):
        return (f"<QFPlayerData(player_id={self.player_id}, "
                f"wallet={self.wallet}, vault={self.vault})>")
