"""Meme Mint player-related Pydantic schemas."""
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from backend.schemas.base import BaseSchema
from backend.schemas.player import PlayerBalance


class MMPlayerBalance(PlayerBalance):
    """Meme Mint player balance with MM-specific fields."""
    free_captions_remaining: int
    # Inherit all fields from PlayerBalance
    # (wallet, vault, daily_bonus_available, etc.)


class MMDailyStateResponse(BaseModel):
    """Daily state payload including free caption quota."""
    free_captions_remaining: int
    free_captions_per_day: int


class MMConfigResponse(BaseModel):
    """Exposed Meme Mint configuration values for clients."""
    round_entry_cost: int
    captions_per_round: int
    caption_submission_cost: int
    free_captions_per_day: int
    house_rake_vault_pct: float
    daily_bonus_amount: int


class MMPlayerStatistics(BaseModel):
    """Meme Mint player statistics."""
    player_id: UUID
    username: str
    total_vote_rounds: int
    total_caption_submissions: int
    total_captions_active: int
    total_votes_cast: int
    total_earnings: int
    total_spending: int
    net_earnings: int
    # Caption author stats
    total_shows: int  # Times their captions were shown
    total_picks: int  # Times their captions were picked
    average_quality_score: float
    # Leaderboard rank
    vault_rank: int | None
    total_players: int


class MMLeaderboardEntry(BaseSchema):
    """Leaderboard entry for Meme Mint."""
    rank: int
    player_id: UUID
    username: str
    vault: int
    total_captions: int
    total_picks: int
    created_at: datetime


class MMLeaderboardResponse(BaseModel):
    """Leaderboard response with pagination."""
    entries: list[MMLeaderboardEntry]
    total: int
    page: int
    page_size: int
    has_more: bool
    # Current player's position if not in current page
    current_player_rank: int | None = None
