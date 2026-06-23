"""Persisted vote choice ordering for reconnect-safe voting."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class QFVoteChoice(Base):
    """Persists a shuffled vote choice for reconnect and submission."""

    __tablename__ = "qf_vote_choices"

    choice_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    round_id = get_uuid_column(ForeignKey("qf_rounds.round_id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    choice_token = get_uuid_column(nullable=False, unique=True, index=True)
    displayed_phrase = Column(String(100), nullable=False)
    internal_role = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    round = relationship("Round", foreign_keys=[round_id])

    __table_args__ = (
        UniqueConstraint("round_id", "position", name="uq_qf_vote_choices_round_position"),
        Index("ix_qf_vote_choices_round_id", "round_id"),
    )
