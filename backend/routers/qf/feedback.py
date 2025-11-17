"""Router handling player feedback and surveys."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.qf.round import Round
from backend.models.qf.survey_response import QFSurveyResponse
from backend.schemas.feedback import (
    SurveySubmission,
    SurveySubmissionResponse,
    SurveyStatusResponse,
    SurveyResponseList,
    SurveyResponseRecord,
)
from backend.models.base import RoundStatus

logger = logging.getLogger(__name__)

SURVEY_ID = "beta_oct_2025"

router = APIRouter(prefix="/feedback")


def _normalize_answer_value(value: Any) -> Any:
    """Ensure answer values are serializable."""

    if isinstance(value, set):
        return sorted(value)
    return value


@router.post("/beta-survey", response_model=SurveySubmissionResponse)
async def submit_beta_survey(
    submission: SurveySubmission,
    player=Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> SurveySubmissionResponse:
    """Persist a beta survey submission for the authenticated player."""

    if submission.survey_id != SURVEY_ID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown_survey")

    existing = await db.execute(
        select(QFSurveyResponse).where(
            QFSurveyResponse.player_id == player.player_id,
            QFSurveyResponse.survey_id == SURVEY_ID,
        )
    )
    if existing.scalar_one_or_none():
        logger.info(f"Player {player.player_id} attempted to resubmit beta survey")
        return SurveySubmissionResponse(status="already_submitted", message="already submitted")

    payload = {
        "answers": [
            {"question_id": answer.question_id, "value": _normalize_answer_value(answer.value)}
            for answer in submission.answers
        ]
    }

    response = QFSurveyResponse(
        response_id=uuid.uuid4(),
        player_id=player.player_id,
        survey_id=SURVEY_ID,
        payload=payload,
    )
    db.add(response)
    await db.flush()
    await db.commit()

    logger.info(f"Stored beta survey response {response.response_id} for player {player.player_id}")
    return SurveySubmissionResponse(status="submitted", message="thank you")


@router.get("/beta-survey", response_model=SurveyResponseList)
async def list_beta_survey_submissions(
    player=Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> SurveyResponseList:
    """Return the last 100 beta survey submissions (admin only)."""

    if not player.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    result = await db.execute(
        select(QFSurveyResponse)
        .where(QFSurveyResponse.survey_id == SURVEY_ID)
        .order_by(QFSurveyResponse.created_at.desc())
        .limit(100)
    )
    submissions = result.scalars().all()
    records = [
        SurveyResponseRecord(
            response_id=sub.response_id,
            player_id=sub.player_id,
            survey_id=sub.survey_id,
            payload=sub.payload or {},
            created_at=sub.created_at,
        )
        for sub in submissions
    ]
    return SurveyResponseList(submissions=records)


@router.get("/beta-survey/status", response_model=SurveyStatusResponse)
async def get_beta_survey_status(
    player=Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
) -> SurveyStatusResponse:
    """Return eligibility + completion status for the beta survey."""

    total_rounds_result = await db.execute(
        select(func.count())
        .select_from(Round)
        .where(
            Round.player_id == player.player_id,
            Round.status == RoundStatus.SUBMITTED.value,
        )
    )
    total_rounds = int(total_rounds_result.scalar_one())

    submission_check = await db.execute(
        select(func.count())
        .select_from(QFSurveyResponse)
        .where(
            QFSurveyResponse.player_id == player.player_id,
            QFSurveyResponse.survey_id == SURVEY_ID,
        )
    )
    has_submitted = submission_check.scalar_one() > 0

    eligible = total_rounds >= 10
    return SurveyStatusResponse(
        eligible=eligible,
        has_submitted=has_submitted,
        total_rounds=total_rounds,
    )
