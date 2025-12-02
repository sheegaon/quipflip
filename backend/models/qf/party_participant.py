"""Party Participant model for Party Mode."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid

from backend.database import Base
from backend.models.base import get_uuid_column


class PartyParticipant(Base):
    """Party Mode participant model.

    Tracks individual player participation and progress in a party session.
    """
    __tablename__ = "party_participants"

    # Primary key
    participant_id = get_uuid_column(primary_key=True, default=uuid.uuid4)

    # Foreign keys
    session_id = get_uuid_column(
        ForeignKey("party_sessions.session_id", ondelete="CASCADE"),
        nullable=False
    )
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False
    )

    # Status tracking
    status = Column(String(20), nullable=False, default='JOINED')
    # Possible values: 'JOINED', 'READY', 'ACTIVE', 'COMPLETED', 'DISCONNECTED'

    is_host = Column(Boolean, nullable=False, default=False)

    # Progress tracking
    prompts_submitted = Column(Integer, nullable=False, default=0)
    copies_submitted = Column(Integer, nullable=False, default=0)
    votes_submitted = Column(Integer, nullable=False, default=0)

    # Timestamps
    joined_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    ready_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    disconnected_at = Column(DateTime(timezone=True), nullable=True)

    # Connection tracking
    connection_status = Column(String(20), nullable=False, default='connected')
    # Possible values: 'connected', 'disconnected'

    __table_args__ = (
        UniqueConstraint("session_id", "player_id", name="uq_party_participants_session_player"),
    )

    # Relationships
    session = relationship("PartySession", back_populates="participants")
    player = relationship("Player")
    party_rounds = relationship(
        "PartyRound",
        back_populates="participant",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<PartyParticipant(id={self.participant_id}, player_id={self.player_id}, session_id={self.session_id}, status={self.status})>"
