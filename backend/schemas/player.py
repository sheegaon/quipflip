"""Player-related Pydantic schemas."""
from pydantic import BaseModel, constr
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID
from backend.schemas.base import BaseSchema
from backend.schemas.auth import AuthTokenResponse, EmailLike
from backend.schemas.round import RoundAvailability
from backend.schemas.phraseset import PhrasesetDashboardSummary, UnclaimedResult


class PlayerBalance(BaseSchema):
    """Player balance response."""
    player_id: UUID
    username: str
    email: EmailLike
    balance: int
    starting_balance: int
    daily_bonus_available: bool
    daily_bonus_amount: int
    last_login_date: Optional[datetime]
    created_at: datetime
    outstanding_prompts: int
    is_guest: bool = False
    is_admin: bool = False
    locked_until: Optional[datetime] = None
    flag_dismissal_streak: int


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
    result_viewed: bool  # Note: This field is actually tracking result_viewed status in the backend


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
    prompt_spending: int
    copy_spending: int
    vote_spending: int
    total_spending: int


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


class ChangePasswordRequest(BaseModel):
    """Request payload for password change."""

    current_password: constr(min_length=1, max_length=128)
    new_password: constr(min_length=8, max_length=128)


class ChangePasswordResponse(BaseModel):
    """Response after password update."""

    message: str
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class UpdateEmailRequest(BaseModel):
    """Request payload for updating email address."""

    new_email: EmailLike
    password: constr(min_length=1, max_length=128)


class UpdateEmailResponse(BaseModel):
    """Response payload containing updated email."""

    email: EmailLike


class DeleteAccountRequest(BaseModel):
    """Request payload for self-serve account deletion."""

    password: constr(min_length=1, max_length=128)
    confirmation: constr(pattern=r"^DELETE$", min_length=6, max_length=6)


class CreateGuestResponse(AuthTokenResponse):
    """Create guest player response returning tokens and guest credentials."""

    balance: int
    email: str
    password: str  # Auto-generated password to show user
    message: str


class UpgradeGuestRequest(BaseModel):
    """Request payload for upgrading guest account to full account."""

    email: EmailLike
    password: constr(min_length=8, max_length=128)


class UpgradeGuestResponse(AuthTokenResponse):
    """Response after upgrading guest account."""

    message: str


class WeeklyLeaderboardEntry(BaseModel):
    """Weekly leaderboard row."""

    player_id: UUID
    username: str
    total_costs: int
    total_earnings: int
    net_earnings: int
    rank: Optional[int]
    is_current_player: bool = False


class WeeklyLeaderboardResponse(BaseModel):
    """Weekly leaderboard payload."""

    leaders: list[WeeklyLeaderboardEntry]
    generated_at: datetime
