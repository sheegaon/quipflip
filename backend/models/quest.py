"""Quest and achievement system models."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from enum import Enum
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column
from sqlalchemy.ext.mutable import MutableDict


class QuestType(str, Enum):
    """Quest type enumeration."""
    # Streak quests
    HOT_STREAK_5 = "hot_streak_5"
    HOT_STREAK_10 = "hot_streak_10"
    HOT_STREAK_20 = "hot_streak_20"

    # Quality quests
    DECEPTIVE_COPY = "deceptive_copy"
    OBVIOUS_ORIGINAL = "obvious_original"

    # Activity quests
    ROUND_COMPLETION_5 = "round_completion_5"
    ROUND_COMPLETION_10 = "round_completion_10"
    ROUND_COMPLETION_20 = "round_completion_20"
    BALANCED_PLAYER = "balanced_player"

    # Login streak
    LOGIN_STREAK_7 = "login_streak_7"

    # Feedback quests
    FEEDBACK_CONTRIBUTOR_10 = "feedback_contributor_10"
    FEEDBACK_CONTRIBUTOR_50 = "feedback_contributor_50"

    # Milestone quests
    MILESTONE_VOTES_100 = "milestone_votes_100"
    MILESTONE_PROMPTS_50 = "milestone_prompts_50"
    MILESTONE_COPIES_100 = "milestone_copies_100"
    MILESTONE_PHRASESET_20VOTES = "milestone_phraseset_20votes"


class QuestStatus(str, Enum):
    """Quest status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    CLAIMED = "claimed"


class QuestCategory(str, Enum):
    """Quest category enumeration."""
    STREAK = "streak"
    QUALITY = "quality"
    ACTIVITY = "activity"
    MILESTONE = "milestone"


class Quest(Base):
    """Quest progress tracking model."""
    __tablename__ = "qf_quests"

    quest_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(ForeignKey("qf_players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    quest_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=QuestStatus.ACTIVE.value, index=True)
    progress = Column(
        MutableDict.as_mutable(JSON), nullable=False, default=dict
    )  # Flexible progress tracking
    reward_amount = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    player = relationship("Player", back_populates="quests")

    # Indexes and constraints
    __table_args__ = (
        Index('ix_quests_player_status', 'player_id', 'status'),
        Index('ix_quests_player_type', 'player_id', 'quest_type', unique=True),
    )

    def __repr__(self):
        return f"<Quest(quest_id={self.quest_id}, type={self.quest_type}, status={self.status})>"


class QuestTemplate(Base):
    """Quest template configuration."""
    __tablename__ = "qf_quest_templates"

    template_id = Column(String(50), primary_key=True)  # Matches QuestType
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    reward_amount = Column(Integer, nullable=False)
    target_value = Column(Integer, nullable=False)
    category = Column(String(20), nullable=False)

    def __repr__(self):
        return f"<QuestTemplate(template_id={self.template_id}, name={self.name})>"
