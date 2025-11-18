"""Quest and achievement system models."""
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import relationship
from enum import Enum
from backend.models.quest_base import QuestBase, QuestTemplateBase, QuestStatus, QuestCategory
from backend.models.base import get_uuid_column


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


class QFQuest(QuestBase):
    """Quest progress tracking model."""
    __tablename__ = "qf_quests"

    # Override player_id to add QF-specific foreign key constraint
    player_id = get_uuid_column(ForeignKey("qf_players.player_id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    player = relationship("QFPlayer", back_populates="quests")

    # Indexes and constraints
    __table_args__ = (
        Index('ix_quests_player_status', 'player_id', 'status'),
        Index('ix_quests_player_type', 'player_id', 'quest_type', unique=True),
    )


class QuestTemplate(QuestTemplateBase):
    """Quest template configuration."""
    __tablename__ = "qf_quest_templates"
