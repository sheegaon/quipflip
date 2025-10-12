"""Prompt feedback API router."""
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.player import Player
from backend.models.round import Round
from backend.models.prompt_feedback import PromptFeedback
from backend.schemas.prompt_feedback import (
    SubmitPromptFeedbackRequest,
    PromptFeedbackResponse,
    GetPromptFeedbackResponse,
)
from uuid import UUID, uuid4
from datetime import datetime, UTC
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{round_id}/feedback", response_model=PromptFeedbackResponse)
async def submit_prompt_feedback(
    round_id: UUID = Path(...),
    request: SubmitPromptFeedbackRequest = ...,
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit thumbs up/down feedback for a prompt.

    - Validates round belongs to player
    - Validates round is a prompt round
    - Allows updating existing feedback (upsert behavior)
    """
    # Get round and validate
    round_object = await db.get(Round, round_id)
    if not round_object:
        raise HTTPException(status_code=404, detail="Round not found")

    if round_object.player_id != player.player_id:
        raise HTTPException(status_code=403, detail="Not authorized to submit feedback for this round")

    if round_object.round_type != "prompt":
        raise HTTPException(status_code=400, detail="Feedback can only be submitted for prompt rounds")

    if not round_object.prompt_id:
        raise HTTPException(status_code=400, detail="Round does not have an associated prompt")

    try:
        # Check if feedback already exists for this player/round
        stmt = select(PromptFeedback).where(
            PromptFeedback.player_id == player.player_id,
            PromptFeedback.round_id == round_id
        )
        result = await db.execute(stmt)
        existing_feedback = result.scalar_one_or_none()

        if existing_feedback:
            # Update existing feedback
            existing_feedback.feedback_type = request.feedback_type
            existing_feedback.created_at = datetime.now(UTC)
            await db.commit()
            logger.info(f"Updated feedback for player {player.player_id}, round {round_id}: {request.feedback_type}")
        else:
            # Create new feedback
            feedback = PromptFeedback(
                feedback_id=uuid4(),
                player_id=player.player_id,
                prompt_id=round_object.prompt_id,
                round_id=round_id,
                feedback_type=request.feedback_type,
                created_at=datetime.now(UTC),
            )
            db.add(feedback)
            await db.commit()
            logger.info(f"Created feedback for player {player.player_id}, round {round_id}: {request.feedback_type}")

        return PromptFeedbackResponse(
            success=True,
            feedback_type=request.feedback_type,
            message="Feedback submitted successfully"
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{round_id}/feedback", response_model=GetPromptFeedbackResponse)
async def get_prompt_feedback(
    round_id: UUID = Path(...),
    player: Player = Depends(get_current_player),
    db: AsyncSession = Depends(get_db),
):
    """
    Get existing feedback for a round.

    Returns feedback_type or null if no feedback exists.
    """
    # Get round and validate
    round_object = await db.get(Round, round_id)
    if not round_object:
        raise HTTPException(status_code=404, detail="Round not found")

    if round_object.player_id != player.player_id:
        raise HTTPException(status_code=403, detail="Not authorized to view feedback for this round")

    # Get feedback
    stmt = select(PromptFeedback).where(
        PromptFeedback.player_id == player.player_id,
        PromptFeedback.round_id == round_id
    )
    result = await db.execute(stmt)
    feedback = result.scalar_one_or_none()

    if feedback:
        return GetPromptFeedbackResponse(
            feedback_type=feedback.feedback_type,
            feedback_id=feedback.feedback_id,
            created_at=feedback.created_at
        )
    else:
        return GetPromptFeedbackResponse(
            feedback_type=None,
            feedback_id=None,
            created_at=None
        )
