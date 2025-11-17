"""Base Quest model with common fields and functionality."""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from enum import Enum
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column
from sqlalchemy.ext.mutable import MutableDict


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


class QuestBase(Base):
    """Base quest progress tracking model."""
    
    __abstract__ = True

    quest_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(nullable=False, index=True)
    quest_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=QuestStatus.ACTIVE.value, index=True)
    progress = Column(
        MutableDict.as_mutable(JSON), nullable=False, default=dict
    )  # Flexible progress tracking
    reward_amount = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<{self.__class__.__name__}(quest_id={self.quest_id}, type={self.quest_type}, status={self.status})>"


class QuestTemplateBase(Base):
    """Base quest template configuration."""
    
    __abstract__ = True

    template_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=False)
    reward_amount = Column(Integer, nullable=False)
    target_value = Column(Integer, nullable=False)
    category = Column(String(20), nullable=False)

    def __repr__(self):
        return f"<{self.__class__.__name__}(template_id={self.template_id}, name={self.name})>"