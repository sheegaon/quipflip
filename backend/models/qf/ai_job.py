"""Durable AI job intent for QuipFlip backup and stale handling."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, Integer, JSON, String, UniqueConstraint, Index

from backend.database import Base
from backend.models.base import get_uuid_column


class QFAIJob(Base):
    """Tracks durable AI work to be applied later."""

    __tablename__ = "qf_ai_jobs"

    job_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    job_type = Column(String(64), nullable=False, index=True)
    target_id = get_uuid_column(nullable=False, index=True)
    expected_version = Column(Integer, nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    provider_metadata = Column(JSON, nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("job_type", "target_id", "expected_version", name="uq_qf_ai_jobs_target_version"),
        Index("ix_qf_ai_jobs_status_created", "status", "created_at"),
    )
