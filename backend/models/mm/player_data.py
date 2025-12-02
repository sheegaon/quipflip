"""Meme Mint player data model."""
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

    def __repr__(self):
        return (f"<MMPlayerData(player_id={self.player_id}, "
                f"wallet={self.wallet}, vault={self.vault})>")
