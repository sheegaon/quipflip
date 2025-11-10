"""User activity model for "Who's Online" feature.

Tracks the most recent API call made by each authenticated user to determine
who is currently online (active in the last 30 minutes).

This is distinct from PhrasesetActivity model, which logs historical phraseset
review events and lifecycle information.
"""
from datetime import datetime, UTC
from uuid import UUID
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class UserActivity(Base):
    """Tracks the last API call made by each user for online status.

    Used by the "Who's Online" page to show which users are currently active.
    Each row represents a single user's most recent activity.
    """

    __tablename__ = "user_activity"

    player_id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    last_action: Mapped[str] = mapped_column(String(100), nullable=False)
    last_action_path: Mapped[str] = mapped_column(Text, nullable=False)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC)
    )
