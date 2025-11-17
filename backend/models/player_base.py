"""Base Player model with common fields and functionality."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
)
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class PlayerBase(Base):
    """Base player account model with common fields."""

    __abstract__ = True

    player_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    username = Column(String(80), unique=True, nullable=False)
    username_canonical = Column(String(80), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    wallet = Column(Integer, default=1000, nullable=False)
    vault = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_login_date = Column(DateTime(timezone=True), nullable=True)
    is_guest = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Guest vote lockout tracking
    consecutive_incorrect_votes = Column(Integer, default=0, nullable=False)
    vote_lockout_until = Column(DateTime(timezone=True), nullable=True)

    # Tutorial tracking
    tutorial_completed = Column(Boolean, default=False, nullable=False)
    tutorial_progress = Column(String(20), default='not_started', nullable=False)
    tutorial_started_at = Column(DateTime(timezone=True), nullable=True)
    tutorial_completed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return (f"<{self.__class__.__name__}(player_id={self.player_id}, username={self.username}, "
                f"wallet={self.wallet}, vault={self.vault})>")
