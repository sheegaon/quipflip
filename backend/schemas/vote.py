"""Vote-related Pydantic schemas."""
from backend.schemas.base import BaseSchema
from datetime import datetime
from uuid import UUID


class VoteDetail(BaseSchema):
    """Vote detail."""
    vote_id: UUID
    player_id: UUID
    voted_word: str
    correct: bool
    payout: int
    created_at: datetime
