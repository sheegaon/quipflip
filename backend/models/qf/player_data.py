"""Quipflip player data model."""
from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    Boolean,
    String,
)
from datetime import datetime, UTC
from backend.database import Base
from sqlalchemy.orm import relationship
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
    player = relationship("Player", back_populates="qf_player_data", lazy="selectin")

    @property
    def balance(self) -> int:
        """Return the player's total liquid balance (wallet + vault)."""
        return int(self.wallet or 0) + int(self.vault or 0)

    def __repr__(self):
        return (f"<QFPlayerData(player_id={self.player_id}, "
                f"wallet={self.wallet}, vault={self.vault})>")
