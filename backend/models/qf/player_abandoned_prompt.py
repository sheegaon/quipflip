"""Player abandoned prompt tracking for cooldown."""
from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class PlayerAbandonedPrompt(Base):
    """Tracks which prompts a player has abandoned (24h cooldown)."""
    __tablename__ = "qf_player_abandoned_prompts"

    id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(ForeignKey("qf_players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_round_id = get_uuid_column(ForeignKey("qf_rounds.round_id"), nullable=False)
    abandoned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    player = relationship("QFPlayer", back_populates="abandoned_prompts")

    # Constraints
    __table_args__ = (
        UniqueConstraint('player_id', 'prompt_round_id', name='uq_player_abandoned_prompt'),
    )

    def __repr__(self):
        return f"<PlayerAbandonedPrompt(player_id={self.player_id}, abandoned_at={self.abandoned_at})>"
