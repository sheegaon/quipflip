"""Base SurveyResponse model with common fields and functionality."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, JSON, String, Index, ForeignKey
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class SurveyResponseBase(Base):
    """Base survey response model for beta surveys."""
    
    __abstract__ = True

    response_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(nullable=False, index=True)
    survey_id = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}(response_id={self.response_id}, player_id={self.player_id}, survey_id={self.survey_id})>")