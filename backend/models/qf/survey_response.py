"""Survey response model for beta surveys."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, JSON, String, Index, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.survey_response_base import SurveyResponseBase
from backend.models.base import get_uuid_column


class QFSurveyResponse(SurveyResponseBase):
    """Persisted survey response payloads for in-app surveys."""

    __tablename__ = "qf_survey_responses"

    # Override player_id to add QF-specific foreign key constraint
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), index=True, nullable=False
    )

    player = relationship("Player", backref="survey_responses")

    __table_args__ = (
        Index("ix_survey_responses_player_survey", "player_id", "survey_id", unique=True),
    )
