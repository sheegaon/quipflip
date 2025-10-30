"""Schemas for flagged prompt administration."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel


class FlaggedPromptItem(BaseModel):
    """Single flagged prompt record."""

    flag_id: UUID
    prompt_round_id: UUID
    copy_round_id: Optional[UUID]
    reporter_player_id: UUID
    reporter_username: str
    prompt_player_id: UUID
    prompt_username: str
    reviewer_player_id: Optional[UUID]
    reviewer_username: Optional[str]
    status: Literal["pending", "confirmed", "dismissed"]
    original_phrase: str
    prompt_text: Optional[str]
    round_cost: int
    partial_refund_amount: int
    penalty_kept: int
    queue_removed: bool
    previous_phraseset_status: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]


class FlaggedPromptListResponse(BaseModel):
    """List response for flagged prompts."""

    flags: list[FlaggedPromptItem]


class ResolveFlaggedPromptRequest(BaseModel):
    """Resolution action payload for flagged prompts."""

    action: Literal["confirm", "dismiss"]
