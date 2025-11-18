"""Base DailyBonus model with common fields and functionality."""
from sqlalchemy import (
    Column,
    Integer,
    Date,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class DailyBonusBase(Base):
    """Base daily bonus tracking model with common fields."""
    
    __abstract__ = True

    bonus_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(nullable=False, index=True)
    amount = Column(Integer, default=100, nullable=False)
    claimed_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    date = Column(Date, nullable=False, index=True)

    def __repr__(self):
        return (f"<{self.__class__.__name__}(bonus_id={self.bonus_id}, player_id={self.player_id}, date={self.date},"
                f" amount={self.amount})>")
