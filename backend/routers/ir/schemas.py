"""Pydantic schemas for Initial Reaction (IR) API routes."""
from datetime import datetime
from pydantic import BaseModel


class IRLoginRequest(BaseModel):
    """IR login request."""

    username: str
    password: str


class IRRegisterRequest(BaseModel):
    """IR registration request."""

    username: str
    email: str
    password: str


class IRPlayerInfo(BaseModel):
    """IR player info for auth response."""

    player_id: str
    username: str
    email: str | None = None
    wallet: int
    vault: int
    is_guest: bool
    created_at: datetime | None = None
    daily_bonus_available: bool = True
    last_login_date: str | None = None


class IRAuthResponse(BaseModel):
    """IR authentication response."""

    access_token: str
    refresh_token: str | None = None
    player: IRPlayerInfo


class IRPlayerResponse(BaseModel):
    """IR player response."""

    player_id: str
    username: str
    email: str
    wallet: int
    vault: int
    created_at: datetime
    is_guest: bool
    is_admin: bool


class IRRefreshRequest(BaseModel):
    """IR token refresh request."""

    refresh_token: str


class IRLogoutRequest(BaseModel):
    """IR logout request."""

    player_id: str


class IRUpgradeGuestRequest(BaseModel):
    """Upgrade guest account request."""

    email: str
    password: str


class IRPlayerBalanceResponse(BaseModel):
    """Balance response payload."""

    wallet: int
    vault: int
    daily_bonus_available: bool


class IRDashboardPlayerSummary(BaseModel):
    player_id: str
    username: str
    wallet: int
    vault: int
    daily_bonus_available: bool
    created_at: datetime


class IRDashboardActiveSession(BaseModel):
    set_id: str
    word: str
    status: str
    has_submitted_entry: bool
    has_voted: bool


class IRPendingResult(BaseModel):
    set_id: str
    word: str
    payout_amount: int
    finalized_at: str | None = None


class IRDashboardResponse(BaseModel):
    player: IRDashboardPlayerSummary
    active_session: IRDashboardActiveSession | None
    pending_results: list[IRPendingResult]
    wallet: int
    vault: int
    daily_bonus_available: bool


class IRClaimDailyBonusResponse(BaseModel):
    bonus_amount: int
    new_balance: int
    next_claim_available_at: str


class BackronymSet(BaseModel):
    """Backronym set details."""

    set_id: str
    word: str
    mode: str  # 'standard' or 'rapid'
    status: str  # 'open', 'voting', 'finalized'
    entry_count: int
    vote_count: int
    non_participant_vote_count: int = 0
    total_pool: int = 0
    creator_final_pool: int = 0
    created_at: str
    transitions_to_voting_at: str | None = None
    voting_finalized_at: str | None = None


class BackronymEntry(BaseModel):
    """Backronym entry details."""

    entry_id: str
    set_id: str
    player_id: str
    backronym_text: list[str]  # Array of words
    is_ai: bool = False
    submitted_at: str
    vote_share_pct: float | None = None
    received_votes: int = 0
    forfeited_to_vault: int = 0


class BackronymVote(BaseModel):
    """Backronym vote details."""

    vote_id: str
    set_id: str
    player_id: str
    chosen_entry_id: str
    is_participant_voter: bool = True
    is_ai: bool = False
    is_correct_popular: bool | None = None
    created_at: str


class PayoutBreakdown(BaseModel):
    """Payout breakdown for a result."""

    entry_cost: int = 0
    vote_cost: int = 0
    gross_payout: int = 0
    vault_rake: int = 0
    net_payout: int = 0
    vote_reward: int = 0


class StartGameRequest(BaseModel):
    """Request to start a backronym battle."""

    pass


class StartGameResponse(BaseModel):
    """Response for starting or joining a game."""

    set_id: str
    word: str
    mode: str
    status: str


class SubmitBackronymRequest(BaseModel):
    """Request to submit a backronym entry."""

    words: list[str]


class SubmitBackronymResponse(BaseModel):
    """Response after submitting backronym."""

    entry_id: str
    set_id: str
    status: str


class SetStatusResponse(BaseModel):
    """Response with current set status."""

    set: BackronymSet
    player_has_submitted: bool
    player_has_voted: bool


class SubmitVoteRequest(BaseModel):
    """Request to submit a vote."""

    entry_id: str


class SubmitVoteResponse(BaseModel):
    """Response after submitting vote."""

    vote_id: str
    set_id: str


class ResultsResponse(BaseModel):
    """Response with finalized results."""

    set: BackronymSet
    entries: list[BackronymEntry]
    votes: list[BackronymVote]
    player_entry: BackronymEntry | None = None
    player_vote: BackronymVote | None = None
    payout_breakdown: PayoutBreakdown | None = None


class PlayerStatsResponse(BaseModel):
    """Player statistics response."""

    player_id: str
    username: str
    wallet: int
    vault: int
    entries_submitted: int
    votes_cast: int
    net_earnings: int


class LeaderboardEntry(BaseModel):
    """Leaderboard entry."""

    rank: int
    player_id: str
    username: str
    vault: int
    value: int
