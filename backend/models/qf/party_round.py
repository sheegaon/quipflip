"""Party Round model for Party Mode."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid

from backend.database import Base
from backend.models.base import get_uuid_column


class PartyRound(Base):
    """Party Mode round link model.

    Links existing rounds to party sessions for tracking and filtering.
    """
    __tablename__ = "party_rounds"

    # Primary key
    party_round_id = get_uuid_column(primary_key=True, default=uuid.uuid4)

    # Foreign keys
    session_id = get_uuid_column(
        ForeignKey("party_sessions.session_id", ondelete="CASCADE"),
        nullable=False
    )
    round_id = get_uuid_column(
        ForeignKey("qf_rounds.round_id", ondelete="CASCADE"),
        nullable=False
    )
    participant_id = get_uuid_column(
        ForeignKey("party_participants.participant_id", ondelete="CASCADE"),
        nullable=False
    )

    # Round classification
    round_type = Column(String(10), nullable=False)
    # Possible values: 'prompt', 'copy', 'vote'

    phase = Column(String(20), nullable=False)
    # Which party phase this round belongs to: 'PROMPT', 'COPY', 'VOTE'

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("session_id", "round_id", name="uq_party_rounds_session_round"),
    )

    # Relationships
    session = relationship("PartySession", back_populates="party_rounds")
    round = relationship("Round")
    participant = relationship("PartyParticipant", back_populates="party_rounds")

    def __repr__(self):
        return f"<PartyRound(id={self.party_round_id}, session_id={self.session_id}, round_type={self.round_type}, phase={self.phase})>"
