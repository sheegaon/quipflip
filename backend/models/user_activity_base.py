"""Base UserActivity model with common fields and functionality for "Who's Online" feature."""
from datetime import datetime, UTC
from uuid import UUID
from sqlalchemy import DateTime, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class UserActivityBase(Base):
    """Base user activity tracking model for online status.

    Tracks the most recent API call made by each authenticated user to determine
    who is currently online (active in the last 30 minutes).
    """
    
    __abstract__ = True

    player_id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    last_action: Mapped[str] = mapped_column(String(100), nullable=False)
    last_action_category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    last_action_path: Mapped[str] = mapped_column(Text, nullable=False)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC)
    )

    def __repr__(self):
        return (f"<{self.__class__.__name__}"
                f"(player_id={self.player_id}, username={self.username}, last_activity={self.last_activity})>")
