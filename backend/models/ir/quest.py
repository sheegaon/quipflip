"""Quest and achievement system models."""
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import relationship
from enum import Enum
from backend.models.quest_base import QuestBase, QuestTemplateBase, QuestStatus, QuestCategory
from backend.models.base import get_uuid_column


class QuestType(str, Enum):
    """Quest type enumeration for IR-specific achievements."""
    # Streak quests
    HOT_STREAK_5 = "hot_streak_5"
    HOT_STREAK_10 = "hot_streak_10"
    HOT_STREAK_20 = "hot_streak_20"

    # Quality quests
    CREATIVE_ENTRY = "creative_entry"
    POPULAR_ENTRY = "popular_entry"

    # Activity quests
    ENTRY_COMPLETION_5 = "entry_completion_5"
    ENTRY_COMPLETION_10 = "entry_completion_10"
    ENTRY_COMPLETION_20 = "entry_completion_20"
    BALANCED_VOTER = "balanced_voter"

    # Login streak
    LOGIN_STREAK_7 = "login_streak_7"

    # Voting quests
    VOTING_CONTRIBUTOR_10 = "voting_contributor_10"
    VOTING_CONTRIBUTOR_50 = "voting_contributor_50"

    # Milestone quests
    MILESTONE_VOTES_100 = "milestone_votes_100"
    MILESTONE_ENTRIES_50 = "milestone_entries_50"
    MILESTONE_BACKRONYM_20VOTES = "milestone_backronym_20votes"


class IRQuest(QuestBase):
    """Quest progress tracking model."""
    __tablename__ = "ir_quests"

    # Override player_id to add IR-specific foreign key constraint
    player_id = get_uuid_column(ForeignKey("ir_players.player_id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    player = relationship("Player", back_populates="quests")

    # Indexes and constraints
    __table_args__ = (
        Index('ix_quests_player_status', 'player_id', 'status'),
        Index('ix_quests_player_type', 'player_id', 'quest_type', unique=True),
    )


class QuestTemplate(QuestTemplateBase):
    """Quest template configuration."""
    __tablename__ = "ir_quest_templates"