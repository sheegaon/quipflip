"""IR BackronymVote model."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class BackronymVote(Base):
    """A vote cast on a backronym entry."""

    __tablename__ = "ir_backronym_votes"

    vote_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    set_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"), nullable=False
    )
    chosen_entry_id = get_uuid_column(
        ForeignKey("ir_backronym_entries.entry_id", ondelete="CASCADE"),
        nullable=False,
    )
    is_participant_voter = Column(Boolean, nullable=False)  # True if voter is creator
    is_ai = Column(Boolean, default=False, nullable=False)
    is_correct_popular = Column(Boolean, nullable=True)  # Only for non-participants
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("player_id", "set_id", name="uq_ir_vote_player_set"),
        Index("ix_ir_vote_set", set_id),
        Index("ix_ir_vote_player_set", player_id, set_id),
        Index("ix_ir_vote_created", created_at),
    )

    # Relationships
    set = relationship("BackronymSet", back_populates="votes")
    player = relationship("IRPlayer", back_populates="backronym_votes")
    chosen_entry = relationship(
        "BackronymEntry",
        back_populates="received_votes_rel",
        foreign_keys=[chosen_entry_id],
    )
