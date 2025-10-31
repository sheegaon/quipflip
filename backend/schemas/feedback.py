"""Pydantic schemas for survey feedback endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SurveyAnswer(BaseModel):
    """Individual answer payload."""

    question_id: str = Field(..., min_length=1)
    value: Any


class SurveySubmission(BaseModel):
    """Survey submission payload from the frontend."""

    survey_id: str = Field(..., min_length=1)
    answers: list[SurveyAnswer]


class SurveySubmissionResponse(BaseModel):
    """Response returned after handling survey submission."""

    status: str
    message: str


class SurveyStatusResponse(BaseModel):
    """Survey eligibility + completion state for the current player."""

    eligible: bool
    has_submitted: bool
    total_rounds: int


class SurveyResponseRecord(BaseModel):
    """Representation of a stored survey response."""

    response_id: UUID
    player_id: UUID
    survey_id: str
    payload: dict[str, Any]
    created_at: datetime


class SurveyResponseList(BaseModel):
    """Envelope for admin survey list endpoint."""

    submissions: list[SurveyResponseRecord]
