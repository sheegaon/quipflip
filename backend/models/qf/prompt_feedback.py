"""Prompt feedback model."""
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class PromptFeedback(Base):
    """Prompt feedback model - tracks player feedback on prompts."""
    __tablename__ = "qf_prompt_feedback"

    feedback_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_id = get_uuid_column(ForeignKey("qf_prompts.prompt_id", ondelete="CASCADE"), nullable=False, index=True)
    round_id = get_uuid_column(ForeignKey("qf_rounds.round_id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_type = Column(String(10), nullable=False)  # 'like' or 'dislike'
    last_updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Unique constraint: one feedback per player per round
    __table_args__ = (
        UniqueConstraint("player_id", "round_id", name="uq_prompt_feedback_player_round"),
    )

    # Relationships
    player = relationship("Player", backref="prompt_feedbacks")
    prompt = relationship("Prompt", backref="feedbacks")
    round = relationship("Round", backref="prompt_feedbacks")

    def __repr__(self):
        return f"<PromptFeedback(feedback_id={self.feedback_id}, feedback_type={self.feedback_type})>"
