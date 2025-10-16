"""Phraseset-related Pydantic schemas."""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from backend.schemas.base import BaseSchema
import re


class VoteRequest(BaseModel):
    """Vote submission request."""
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


class VoteResponse(BaseModel):
    """Immediate vote feedback."""
    correct: bool
    payout: int
    original_phrase: str
    your_choice: str


class PhraseVoteCount(BaseModel):
    """Phrase with vote count."""
    phrase: str
    vote_count: int
    is_original: bool


class PhraseSetResults(BaseSchema):
    """Complete phraseset results."""
    prompt_text: str
    votes: list[PhraseVoteCount]
    your_phrase: str
    your_role: str  # "prompt" or "copy"
    your_points: int
    your_payout: int
    total_pool: int
    total_votes: int
    already_collected: bool
    finalized_at: datetime


class PhrasesetSummary(BaseSchema):
    """Summary information for a player's phraseset contribution."""
    phraseset_id: Optional[UUID]
    prompt_round_id: UUID
    prompt_text: str
    your_role: Literal["prompt", "copy"]
    your_phrase: Optional[str]
    status: Literal["waiting_copies", "waiting_copy1", "active", "voting", "closing", "finalized", "abandoned"]
    created_at: datetime
    updated_at: Optional[datetime]
    vote_count: Optional[int]
    third_vote_at: Optional[datetime]
    fifth_vote_at: Optional[datetime]
    finalized_at: Optional[datetime]
    has_copy1: bool
    has_copy2: bool
    your_payout: Optional[int]
    payout_claimed: Optional[bool]
    new_activity_count: int = 0


class PhrasesetListResponse(BaseSchema):
    """Paginated list of player's phrasesets."""
    phrasesets: list[PhrasesetSummary]
    total: int
    has_more: bool


class PhrasesetDashboardCounts(BaseSchema):
    prompts: int
    copies: int
    unclaimed_prompts: int = 0
    unclaimed_copies: int = 0


class PhrasesetDashboardSummary(BaseSchema):
    """Quick summary for dashboard display."""
    in_progress: PhrasesetDashboardCounts
    finalized: PhrasesetDashboardCounts
    total_unclaimed_amount: int = 0


class PhrasesetContributor(BaseSchema):
    """Contributor information."""
    player_id: UUID
    username: str
    is_you: bool
    phrase: Optional[str] = None


class PhrasesetVote(BaseSchema):
    """Vote entry for phraseset details."""
    vote_id: UUID
    voter_id: UUID
    voter_username: str
    voted_phrase: str
    correct: bool
    voted_at: datetime


class PhrasesetActivityEntry(BaseSchema):
    """Timeline activity entry."""
    activity_id: UUID
    activity_type: str
    created_at: datetime
    player_id: Optional[UUID]
    player_username: Optional[str] = None
    metadata: dict


class PhrasesetDetails(BaseSchema):
    """Full details for a phraseset."""
    phraseset_id: UUID
    prompt_round_id: UUID
    prompt_text: str
    status: Literal["waiting_copies", "waiting_copy1", "active", "voting", "closing", "finalized", "abandoned"]
    original_phrase: Optional[str]
    copy_phrase_1: Optional[str]
    copy_phrase_2: Optional[str]
    contributors: list[PhrasesetContributor]
    vote_count: int
    third_vote_at: Optional[datetime]
    fifth_vote_at: Optional[datetime]
    closes_at: Optional[datetime]
    votes: list[PhrasesetVote]
    total_pool: int
    results: Optional[dict]
    your_role: Literal["prompt", "copy"]
    your_phrase: Optional[str]
    your_payout: Optional[int]
    payout_claimed: bool
    activity: list[PhrasesetActivityEntry]
    created_at: datetime
    finalized_at: Optional[datetime]


class ClaimPrizeResponse(BaseSchema):
    """Response payload for prize claim endpoint."""
    success: bool
    amount: int
    new_balance: int
    already_claimed: bool


class UnclaimedResult(BaseSchema):
    """Unclaimed result entry for dashboard."""
    phraseset_id: UUID
    prompt_text: str
    your_role: Literal["prompt", "copy"]
    your_phrase: Optional[str]
    finalized_at: datetime
    your_payout: int


class UnclaimedResultsResponse(BaseSchema):
    """Collection of unclaimed results and totals."""
    unclaimed: list[UnclaimedResult]
    total_unclaimed_amount: int
