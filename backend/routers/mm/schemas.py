"""Schemas for Meme Mint API responses."""

from pydantic import BaseModel


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
