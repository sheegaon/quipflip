"""Round-related Pydantic schemas."""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal
from uuid import UUID
from backend.schemas.base import BaseSchema
import re


class StartPromptRoundResponse(BaseSchema):
    """Start prompt round response."""
    round_id: UUID
    prompt_text: str
    expires_at: datetime
    cost: int


class StartCopyRoundResponse(BaseSchema):
    """Start copy round response."""
    round_id: UUID
    original_phrase: str
    prompt_round_id: UUID
    expires_at: datetime
    cost: int
    discount_active: bool


class StartVoteRoundResponse(BaseSchema):
    """Start vote round response."""
    round_id: UUID
    phraseset_id: UUID
    prompt_text: str
    phrases: list[str]
    expires_at: datetime


class SubmitPhraseRequest(BaseModel):
    """Submit phrase request."""
    phrase: str = Field(..., min_length=2, max_length=100)

    @field_validator('phrase')
    @classmethod
    def phrase_must_be_valid(cls, v: str) -> str:
        """Validate phrase contains only letters and spaces."""
        if not re.match(r'^[a-zA-Z\s]+$', v):
            raise ValueError('Phrase must contain only letters A-Z and spaces')
        # Normalize whitespace
        v = re.sub(r'\s+', ' ', v.strip())
        return v.upper()


class SubmitPhraseResponse(BaseModel):
    """Submit phrase response."""
    success: bool
    phrase: str


class RoundAvailability(BaseModel):
    """Round availability status with game constants."""
    can_prompt: bool
    can_copy: bool
    can_vote: bool
    prompts_waiting: int
    phrasesets_waiting: int
    copy_discount_active: bool
    copy_cost: int
    current_round_id: UUID | None
    # Game constants (from config)
    prompt_cost: int
    vote_cost: int
    vote_payout_correct: int
    abandoned_penalty: int


class RoundDetails(BaseSchema):
    """Round details response."""
    round_id: UUID
    type: str
    status: str
    expires_at: datetime
    prompt_text: str | None = None
    original_phrase: str | None = None
    submitted_phrase: str | None = None
    cost: int


class FlagCopyRoundResponse(BaseModel):
    """Response when a copy round is flagged by a player."""

    flag_id: UUID
    refund_amount: int
    penalty_kept: int
    status: Literal["pending", "confirmed", "dismissed"]
    message: str
