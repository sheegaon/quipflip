"""Player-related Pydantic schemas."""
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Literal
from uuid import UUID
from backend.schemas.base import BaseSchema
from backend.schemas.auth import AuthTokenResponse
from backend.schemas.round import RoundAvailability
from backend.schemas.phraseset import PhrasesetDashboardSummary, UnclaimedResult


class PlayerBalance(BaseSchema):
    """Player balance response."""
    username: str
    balance: int
    starting_balance: int
    daily_bonus_available: bool
    daily_bonus_amount: int
    last_login_date: Optional[date]
    outstanding_prompts: int


class ClaimDailyBonusResponse(BaseModel):
    """Daily bonus claim response."""
    success: bool
    amount: int
    new_balance: int


class CurrentRoundResponse(BaseSchema):
    """Current active round response."""
    round_id: Optional[UUID]
    round_type: Optional[str]
    state: Optional[dict]
    expires_at: Optional[datetime]


class PendingResult(BaseSchema):
    """Pending result item."""
    phraseset_id: UUID
    prompt_text: str
    completed_at: datetime
    role: str  # "prompt" or "copy"
    payout_claimed: bool


class PendingResultsResponse(BaseModel):
    """List of pending results."""
    pending: list[PendingResult]


class CreatePlayerResponse(AuthTokenResponse):
    """Create player response returning tokens and onboarding message."""

    balance: int
    message: str


class RoleStatistics(BaseModel):
    """Statistics for a specific role."""
    role: Literal["prompt", "copy", "voter"]
    total_rounds: int
    total_earnings: int
    average_earnings: float
    win_rate: float  # % of rounds that earned positive payout
    total_phrasesets: Optional[int] = None  # For prompt/copy roles
    average_votes_received: Optional[float] = None  # For prompt/copy
    correct_votes: Optional[int] = None  # For voter role
    vote_accuracy: Optional[float] = None  # For voter role


class EarningsBreakdown(BaseModel):
    """Breakdown of earnings by source."""
    prompt_earnings: int
    copy_earnings: int
    vote_earnings: int
    daily_bonuses: int
    total_earnings: int
    prompt_costs: int
    copy_costs: int
    vote_costs: int
    total_costs: int


class PlayFrequency(BaseModel):
    """Play frequency metrics."""
    total_rounds_played: int
    days_active: int
    rounds_per_day: float
    last_active: datetime
    member_since: datetime


class BestPerformingPhrase(BaseModel):
    """Top performing phrase data."""
    phrase: str
    votes: int
    earnings: int


class PlayerStatistics(BaseModel):
    """Comprehensive player statistics."""
    player_id: UUID
    username: str
    email: str
    overall_balance: int

    # Role-specific stats
    prompt_stats: RoleStatistics
    copy_stats: RoleStatistics
    voter_stats: RoleStatistics

    # Earnings
    earnings: EarningsBreakdown

    # Frequency
    frequency: PlayFrequency

    # Additional metrics
    favorite_prompts: list[str]  # Top 5 prompts by earnings
    best_performing_phrases: list[BestPerformingPhrase]  # Top phrases with vote counts


class TutorialStatus(BaseModel):
    """Tutorial status response."""
    tutorial_completed: bool
    tutorial_progress: str
    tutorial_started_at: Optional[datetime]
    tutorial_completed_at: Optional[datetime]


class UpdateTutorialProgressRequest(BaseModel):
    """Request to update tutorial progress."""
    progress: Literal["not_started", "welcome", "dashboard", "prompt_round", "prompt_round_paused", "copy_round",
                      "copy_round_paused", "vote_round", "completed"]


class UpdateTutorialProgressResponse(BaseModel):
    """Response after updating tutorial progress."""
    success: bool
    tutorial_status: TutorialStatus


class DashboardDataResponse(BaseSchema):
    """Batched dashboard data - all info needed for dashboard in one call."""
    # From /player/balance
    player: PlayerBalance

    # From /player/current-round
    current_round: CurrentRoundResponse

    # From /player/pending-results
    pending_results: list[PendingResult]

    # From /player/phrasesets/summary
    phraseset_summary: PhrasesetDashboardSummary

    # From /player/unclaimed-results
    unclaimed_results: list[UnclaimedResult]

    # From /rounds/available
    round_availability: RoundAvailability
