"""IR BackronymEntry model."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Boolean,
    JSON,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class BackronymEntry(Base):
    """A player's backronym submission for a set."""

    __tablename__ = "ir_backronym_entries"

    entry_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    set_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"), nullable=False
    )
    backronym_text = Column(JSON, nullable=False)  # Array of N words for N letters
    is_ai = Column(Boolean, default=False, nullable=False)
    submitted_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    vote_share_pct = Column(Integer, nullable=True)  # Percentage 0-100
    received_votes = Column(Integer, default=0, nullable=False)
    forfeited_to_vault = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("player_id", "set_id", name="uq_ir_entry_player_set"),
        Index("ix_ir_entry_set", set_id),
        Index("ix_ir_entry_player_set", player_id, set_id),
        Index("ix_ir_entry_submitted", submitted_at),
    )

    # Relationships
    set = relationship("IRBackronymSet", back_populates="entries")
    player = relationship("IRPlayer", back_populates="backronym_entries")
    received_votes_rel = relationship(
        "IRBackronymVote",
        back_populates="chosen_entry",
        foreign_keys="IRBackronymVote.chosen_entry_id",
    )
