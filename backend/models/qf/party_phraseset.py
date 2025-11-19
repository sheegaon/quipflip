"""Party Phraseset model for Party Mode."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import uuid

from backend.models.base import Base, get_uuid_column


class PartyPhraseset(Base):
    """Party Mode phraseset link model.

    Links phrasesets to party sessions for match-scoped voting.
    """
    __tablename__ = "party_phrasesets"

    # Primary key
    party_phraseset_id = get_uuid_column(primary_key=True, default=uuid.uuid4)

    # Foreign keys
    session_id = get_uuid_column(
        ForeignKey("party_sessions.session_id", ondelete="CASCADE"),
        nullable=False
    )
    phraseset_id = get_uuid_column(
        ForeignKey("qf_phrasesets.phraseset_id", ondelete="CASCADE"),
        nullable=False
    )

    # Metadata
    created_in_phase = Column(String(20), nullable=False)
    # Which phase this phraseset was created in: typically 'COPY'

    available_for_voting = Column(Boolean, nullable=False, default=False)
    # Whether this phraseset is ready for party voting

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))

    __table_args__ = (
        UniqueConstraint("session_id", "phraseset_id", name="uq_party_phrasesets_session_phraseset"),
    )

    # Relationships
    session = relationship("PartySession", back_populates="party_phrasesets")
    phraseset = relationship("Phraseset")

    def __repr__(self):
        return f"<PartyPhraseset(id={self.party_phraseset_id}, session_id={self.session_id}, phraseset_id={self.phraseset_id})>"
