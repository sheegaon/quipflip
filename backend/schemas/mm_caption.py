"""Meme Mint caption-related Pydantic schemas."""
from pydantic import BaseModel
from datetime import datetime
from typing import Literal
from uuid import UUID
from backend.schemas.base import BaseSchema


class CaptionSummary(BaseSchema):
    """Caption summary for display."""
    caption_id: UUID
    text: str
    kind: Literal["original", "riff"]
    parent_caption_id: UUID | None
    author_username: str | None  # None for system/AI captions
    shows: int
    picks: int
    quality_score: float
    created_at: datetime


class CaptionStats(BaseModel):
    """Caption performance statistics."""
    caption_id: UUID
    shows: int
    picks: int
    quality_score: float
    lifetime_earnings_gross: int
    lifetime_to_wallet: int
    lifetime_to_vault: int
    first_vote_awarded: bool


class CaptionResults(BaseSchema):
    """Detailed caption results after voting."""
    caption_id: UUID
    image_id: UUID
    text: str
    kind: Literal["original", "riff"]
    parent_caption_id: UUID | None
    parent_caption_text: str | None
    author_username: str | None
    shows: int
    picks: int
    quality_score: float
    lifetime_earnings_gross: int
    lifetime_to_wallet: int
    lifetime_to_vault: int
    created_at: datetime


class CaptionListItem(BaseSchema):
    """Caption item for list views."""
    caption_id: UUID
    image_id: UUID
    text: str
    kind: Literal["original", "riff"]
    author_username: str | None
    picks: int
    quality_score: float
    created_at: datetime


class CaptionListResponse(BaseModel):
    """List of captions with pagination."""
    captions: list[CaptionListItem]
    total: int
    page: int
    page_size: int
    has_more: bool


class PlayerCaptionSummary(BaseSchema):
    """Player's caption with earnings summary."""
    caption_id: UUID
    image_id: UUID
    text: str
    kind: Literal["original", "riff"]
    shows: int
    picks: int
    quality_score: float
    lifetime_earnings_gross: int
    lifetime_to_wallet: int
    lifetime_to_vault: int
    status: Literal["active", "retired", "removed"]
    created_at: datetime
