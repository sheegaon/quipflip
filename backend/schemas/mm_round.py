"""Meme Mint round-related Pydantic schemas."""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal
from uuid import UUID
from backend.schemas.base import BaseSchema
import re


class StartVoteRoundResponse(BaseSchema):
    """Start vote round response."""
    round_id: UUID
    image_id: UUID
    image_url: str
    thumbnail_url: str | None
    attribution_text: str | None
    captions: list[dict]  # List of {caption_id, text}
    expires_at: datetime
    cost: int


class StartCaptionRoundResponse(BaseSchema):
    """Start caption submission round response."""
    round_id: UUID
    image_id: UUID
    image_url: str
    thumbnail_url: str | None
    attribution_text: str | None
    expires_at: datetime
    cost: int  # 0 if using free quota, otherwise caption_submission_cost
    used_free_slot: bool


class SubmitVoteRequest(BaseModel):
    """Submit vote request."""
    caption_id: UUID = Field(..., description="ID of the chosen caption")


class SubmitCaptionRequest(BaseModel):
    """Submit caption request."""
    round_id: UUID = Field(..., description="Round ID from vote round")
    caption_text: str = Field(..., min_length=1, max_length=240, description="Caption text", alias="text")
    caption_type: Literal["original", "riff"] = Field(default="original", description="Caption type", alias="kind")
    parent_caption_id: UUID | None = Field(default=None, description="Parent caption ID for riffs")

    class Config:
        populate_by_name = True  # Allow both field name and alias

    @field_validator('caption_text')
    @classmethod
    def text_must_be_valid(cls, v: str) -> str:
        """Validate caption text."""
        # Normalize whitespace
        v = re.sub(r'\s+', ' ', v.strip())
        if not v:
            raise ValueError('Caption text cannot be empty')
        return v

    @field_validator('parent_caption_id')
    @classmethod
    def validate_riff_parent(cls, v: UUID | None, info) -> UUID | None:
        """Validate parent_caption_id is provided for riffs."""
        caption_type = info.data.get('caption_type')
        if caption_type == 'riff' and v is None:
            raise ValueError('parent_caption_id is required for riff captions')
        if caption_type == 'original' and v is not None:
            raise ValueError('parent_caption_id should not be provided for original captions')
        return v


class SubmitVoteResponse(BaseModel):
    """Submit vote response."""
    success: bool
    chosen_caption_id: UUID
    payout: int  # Payout for this vote (may be 0 or negative if incorrect)
    correct: bool  # Whether the vote was correct (implementation-specific)
    new_wallet: int
    new_vault: int


class SubmitCaptionResponse(BaseModel):
    """Submit caption response."""
    success: bool
    caption_id: UUID
    cost: int
    used_free_slot: bool
    new_wallet: int


class RoundAvailability(BaseModel):
    """Round availability status with game constants."""
    can_vote: bool
    can_submit_caption: bool
    current_round_id: UUID | None
    # Game constants (from config)
    round_entry_cost: int
    caption_submission_cost: int
    free_captions_remaining: int
    daily_bonus_available: bool


class RoundDetails(BaseSchema):
    """Round details response."""
    round_id: UUID
    type: Literal["vote", "caption_submission"]
    status: str
    expires_at: datetime
    image_id: UUID
    image_url: str
    cost: int
    # For vote rounds
    captions: list[dict] | None = None
    chosen_caption_id: UUID | None = None
    # For caption submission rounds
    submitted_caption_id: UUID | None = None
    submitted_caption_text: str | None = None


class AbandonRoundResponse(BaseModel):
    """Response when a player abandons an active round."""
    round_id: UUID
    round_type: Literal["vote", "caption_submission"]
    status: Literal["abandoned"]
    refund_amount: int
    penalty_kept: int
    message: str
