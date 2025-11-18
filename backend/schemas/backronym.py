"""Backronym-related Pydantic models."""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID
from backend.schemas.base import BaseSchema
import re


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


class ResultsResponse(BaseModel):
    """Response with finalized results."""

    set: BackronymSet
    entries: list[BackronymEntry]
    votes: list[BackronymVote]
    player_entry: BackronymEntry | None = None
    player_vote: BackronymVote | None = None
    payout_breakdown: PayoutBreakdown | None = None


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


class ValidateBackronymRequest(BaseModel):
    """Request to validate backronym words for a set."""

    words: list[str]


class ValidateBackronymResponse(BaseModel):
    """Response from validating a set of backronym words."""

    is_valid: bool
    error: str | None = None


class SubmitVoteResponse(BaseModel):
    """Response after submitting vote."""

    vote_id: str
    set_id: str
