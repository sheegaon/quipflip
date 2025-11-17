"""Pydantic schemas for Initial Reaction (IR) API routes."""
from datetime import datetime
from pydantic import BaseModel


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
