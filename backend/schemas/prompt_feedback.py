"""Prompt feedback Pydantic schemas."""
from pydantic import Field
from backend.schemas.base import BaseSchema
from datetime import datetime
from uuid import UUID
from typing import Literal


class SubmitPromptFeedbackRequest(BaseSchema):
    """Request to submit feedback on a prompt."""
    feedback_type: Literal['like', 'dislike'] = Field(
        ...,
        description="Type of feedback: 'like' for thumbs up, 'dislike' for thumbs down"
    )


class PromptFeedbackResponse(BaseSchema):
    """Response after submitting feedback."""
    success: bool
    feedback_type: Literal['like', 'dislike']
    message: str = "Feedback submitted successfully"


class GetPromptFeedbackResponse(BaseSchema):
    """Response when retrieving feedback for a round."""
    feedback_type: Literal['like', 'dislike'] | None
    feedback_id: UUID | None = None
    last_updated_at: datetime | None = None
