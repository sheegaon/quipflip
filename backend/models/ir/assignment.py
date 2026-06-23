"""Durable Initial Reaction entry assignments."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column
from backend.models.versioned_base import VersionedBase


class IRAssignment(VersionedBase, Base):
    """Actor-scoped claim on one backronym set."""

    __tablename__ = "ir_assignments"

    assignment_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    assignment_token = get_uuid_column(
        nullable=False,
        unique=True,
        default=uuid.uuid4,
    )
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    set_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="CASCADE"),
        nullable=False,
    )
    entry_id = get_uuid_column(
        ForeignKey("ir_backronym_entries.entry_id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(20), nullable=False, default="assigned")
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)

    set = relationship("BackronymSet", back_populates="assignments")

    __table_args__ = (
        CheckConstraint(
            "status IN ('assigned', 'submitting', 'submitted', 'completed', 'expired')",
            name="valid_ir_assignment_status",
        ),
        Index(
            "uq_ir_assignment_active_player",
            "player_id",
            unique=True,
            sqlite_where=text("status IN ('assigned', 'submitting', 'submitted')"),
            postgresql_where=text("status IN ('assigned', 'submitting', 'submitted')"),
        ),
        Index(
            "uq_ir_assignment_player_set",
            "player_id",
            "set_id",
            unique=True,
        ),
        Index("ix_ir_assignment_set_status", "set_id", "status"),
    )
