"""Quest-related Pydantic schemas."""
from backend.schemas.base import BaseSchema, ConfigDict
from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID


class QuestProgress(BaseSchema):
    """Quest progress data."""
    current: int = 0
    target: int
    percentage: Optional[float] = None

    # Quest-specific optional fields
    current_streak: Optional[int] = None
    highest_streak: Optional[int] = None
    rounds_completed: Optional[int] = None
    window_start: Optional[str] = None
    round_timestamps: Optional[list[str]] = None
    prompts: Optional[int] = None
    copies: Optional[int] = None
    votes: Optional[int] = None
    consecutive_days: Optional[int] = None
    last_login_date: Optional[str] = None
    login_dates: Optional[list[str]] = None
    phraseset_id: Optional[str] = None
    vote_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True, extra="allow")  # Allow additional fields from JSON


class QuestResponse(BaseSchema):
    """Quest response schema."""
    quest_id: UUID
    quest_type: str
    name: str
    description: str
    status: str  # active, completed, claimed
    progress: Dict[str, Any]  # Raw progress dict from database
    reward_amount: int
    category: str  # streak, quality, activity, milestone
    created_at: datetime
    completed_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None

    # Computed fields
    progress_percentage: float
    progress_current: int
    progress_target: int

class ClaimQuestRewardResponse(BaseSchema):
    """Response after claiming a quest reward."""
    success: bool
    quest_type: str
    reward_amount: int
    new_wallet: int
    new_vault: int


class QuestListResponse(BaseSchema):
    """List of quests response."""
    quests: list[QuestResponse]
    total_count: int
    active_count: int
    completed_count: int
    claimed_count: int
    claimable_count: int
