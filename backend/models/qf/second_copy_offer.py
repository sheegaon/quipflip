"""Actor-scoped offer for a second copy submission."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class QFSecondCopyOffer(Base):
    """Tracks an actor-scoped offer for a second copy."""

    __tablename__ = "qf_second_copy_offers"

    offer_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    source_copy_round_id = get_uuid_column(
        ForeignKey("qf_rounds.round_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt_round_id = get_uuid_column(
        ForeignKey("qf_rounds.round_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    offer_token = get_uuid_column(nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    player = relationship("Player")
    source_copy_round = relationship("Round", foreign_keys=[source_copy_round_id])
    prompt_round = relationship("Round", foreign_keys=[prompt_round_id])

    __table_args__ = (
        UniqueConstraint("source_copy_round_id", name="uq_qf_second_copy_offers_source_copy_round"),
        Index("ix_qf_second_copy_offers_player_created", "player_id", "created_at"),
    )
