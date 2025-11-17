"""Schemas for flagged prompt administration."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal, Optional
from uuid import UUID

from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover - for typing only
    from backend.services import FlaggedPromptRecord


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

    @classmethod
    def from_record(cls, record: "FlaggedPromptRecord") -> "FlaggedPromptItem":
        """Build a response item from a service-layer record."""

        flag = record.flag
        return cls(
            flag_id=flag.flag_id,
            prompt_round_id=flag.prompt_round_id,
            copy_round_id=flag.copy_round_id,
            reporter_player_id=flag.reporter_player_id,
            reporter_username=record.reporter_username,
            prompt_player_id=flag.prompt_player_id,
            prompt_username=record.prompt_username,
            reviewer_player_id=flag.reviewer_player_id,
            reviewer_username=record.reviewer_username,
            status=flag.status,
            original_phrase=flag.original_phrase,
            prompt_text=flag.prompt_text,
            round_cost=flag.round_cost,
            partial_refund_amount=flag.partial_refund_amount,
            penalty_kept=flag.penalty_kept,
            queue_removed=flag.queue_removed,
            previous_phraseset_status=flag.previous_phraseset_status,
            created_at=flag.created_at,
            reviewed_at=flag.reviewed_at,
        )


class FlaggedPromptListResponse(BaseModel):
    """List response for flagged prompts."""

    flags: list[FlaggedPromptItem]


class ResolveFlaggedPromptRequest(BaseModel):
    """Resolution action payload for flagged prompts."""

    action: Literal["confirm", "dismiss"]
