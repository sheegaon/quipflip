"""Survey response model for beta surveys."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, JSON, String, Index, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class SurveyResponse(Base):
    """Persisted survey response payloads for in-app surveys."""

    __tablename__ = "survey_responses"

    response_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), index=True, nullable=False
    )
    survey_id = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    player = relationship("Player", backref="survey_responses")

    __table_args__ = (
        Index("ix_survey_responses_player_survey", "player_id", "survey_id", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<SurveyResponse(response_id={self.response_id}, player_id={self.player_id}, survey_id={self.survey_id})>")
