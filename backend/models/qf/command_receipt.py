"""Command receipt model for retriable QuipFlip solo commands."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, String, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class QFCommandReceipt(Base):
    """Tracks retriable public command outcomes."""

    __tablename__ = "qf_command_receipts"

    receipt_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    command_id = get_uuid_column(nullable=False)
    command_type = Column(String(64), nullable=False)
    aggregate_type = Column(String(64), nullable=False)
    aggregate_id = get_uuid_column(nullable=True, index=True)
    outcome = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    player = relationship("Player")

    __table_args__ = (
        UniqueConstraint("player_id", "command_id", name="uq_qf_command_receipts_player_command"),
        Index("ix_qf_command_receipts_player_created", "player_id", "created_at"),
    )
