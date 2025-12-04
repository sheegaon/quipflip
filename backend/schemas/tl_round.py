"""ThinkLink (TL) round-related Pydantic schemas."""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from backend.schemas.base import BaseSchema


class StartRoundResponse(BaseSchema):
    """Response when starting a new ThinkLink round."""
    round_id: UUID
    prompt_text: str
    snapshot_answer_count: int
    snapshot_total_weight: float
    created_at: datetime


class SubmitGuessRequest(BaseModel):
    """Request to submit a guess in an active round."""
    guess_text: str = Field(..., min_length=1, max_length=200)

    @field_validator('guess_text')
    @classmethod
    def guess_must_not_be_empty(cls, v: str) -> str:
        """Validate guess is not just whitespace."""
        if not v.strip():
            raise ValueError('Guess cannot be empty or whitespace')
        return v.strip()


class SubmitGuessResponse(BaseSchema):
    """Response when submitting a guess."""
    was_match: bool
    matched_answer_count: int
    matched_cluster_ids: List[str]
    new_strikes: int
    current_coverage: float
    round_status: str
    round_id: UUID


class RoundDetails(BaseSchema):
    """Details of an active or completed round."""
    round_id: UUID
    prompt_id: UUID
    prompt_text: str
    snapshot_answer_count: int
    snapshot_total_weight: float
    matched_clusters: List[str]
    strikes: int
    status: str
    final_coverage: Optional[float]
    gross_payout: Optional[int]
    wallet_award: Optional[int] = None
    vault_award: Optional[int] = None
    created_at: datetime
    ended_at: Optional[datetime]


class RoundHistoryItem(BaseSchema):
    """Summary of a completed or abandoned round."""
    round_id: UUID
    prompt_text: str
    final_coverage: Optional[float]
    gross_payout: Optional[int]
    strikes: int
    status: str
    created_at: datetime
    ended_at: Optional[datetime]


class RoundHistoryResponse(BaseSchema):
    """List of past rounds for a player."""
    rounds: List[RoundHistoryItem]


class RoundAvailability(BaseSchema):
    """Round availability and game status."""
    can_start_round: bool
    error_message: Optional[str]
    # Player state
    tl_wallet: int
    tl_vault: int
    # Game economics
    entry_cost: int
    max_payout: int
    starting_balance: int


class AbandonRoundResponse(BaseSchema):
    """Response when abandoning a round."""
    round_id: UUID
    status: str
    refund_amount: int
