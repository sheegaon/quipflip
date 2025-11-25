"""Party Session model for Party Mode."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
)
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid

from backend.database import Base
from backend.models.base import get_uuid_column


class PartySession(Base):
    """Party Mode session model.

    Tracks the state of a party match including phase, status, and configuration.
    """
    __tablename__ = "party_sessions"

    # Primary key
    session_id = get_uuid_column(primary_key=True, default=uuid.uuid4)

    # Party code for joining
    party_code = Column(String(8), unique=True, nullable=False)

    # Host player reference
    host_player_id = get_uuid_column(
        ForeignKey("qf_players.player_id", ondelete="CASCADE"),
        nullable=False
    )

    # Configuration
    min_players = Column(Integer, nullable=False, default=6)
    max_players = Column(Integer, nullable=False, default=9)
    prompts_per_player = Column(Integer, nullable=False, default=1)
    copies_per_player = Column(Integer, nullable=False, default=2)
    votes_per_player = Column(Integer, nullable=False, default=3)

    # Phase tracking
    current_phase = Column(String(20), nullable=False, default='LOBBY')
    # Possible values: 'LOBBY', 'PROMPT', 'COPY', 'VOTE', 'RESULTS', 'COMPLETED'

    phase_started_at = Column(DateTime(timezone=True), nullable=True)
    phase_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default='OPEN')
    # Possible values: 'OPEN', 'IN_PROGRESS', 'COMPLETED', 'ABANDONED'

    locked_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    host_player = relationship("QFPlayer", foreign_keys=[host_player_id])
    participants = relationship(
        "PartyParticipant",
        back_populates="session",
        cascade="all, delete-orphan"
    )
    party_rounds = relationship(
        "PartyRound",
        back_populates="session",
        cascade="all, delete-orphan"
    )
    party_phrasesets = relationship(
        "PartyPhraseset",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<PartySession(id={self.session_id}, code={self.party_code}, phase={self.current_phase}, status={self.status})>"
