"""Unified player model for cross-game authentication."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
)
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class Player(Base):
    """Unified player account model for all games.

    Contains authentication credentials and account-level settings
    shared across all games. Game-specific data is stored in separate
    game-specific tables (qf_player_data, mm_player_data, ir_player_data).
    """

    __tablename__ = "players"

    player_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    username = Column(String(80), unique=True, nullable=False)
    username_canonical = Column(String(80), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_login_date = Column(DateTime(timezone=True), nullable=True)
    is_guest = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return (f"<Player(player_id={self.player_id}, username={self.username}, "
                f"email={self.email})>")
