"""Pydantic schemas for survey feedback endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from backend.schemas.base import BaseSchema
from pydantic import Field


class SurveyAnswer(BaseSchema):
    """Individual answer payload."""

    question_id: str = Field(..., min_length=1)
    value: Any


class SurveySubmission(BaseSchema):
    """Survey submission payload from the frontend."""

    survey_id: str = Field(..., min_length=1)
    answers: list[SurveyAnswer]


class SurveySubmissionResponse(BaseSchema):
    """Response returned after handling survey submission."""

    status: str
    message: str


class SurveyStatusResponse(BaseSchema):
    """Survey eligibility + completion state for the current player."""

    eligible: bool
    has_submitted: bool
    total_rounds: int


class SurveyResponseRecord(BaseSchema):
    """Representation of a stored survey response."""

    response_id: UUID
    player_id: UUID
    survey_id: str
    payload: dict[str, Any]
    created_at: datetime


class SurveyResponseList(BaseSchema):
    """Envelope for admin survey list endpoint."""

    submissions: list[SurveyResponseRecord]
