"""IR Player model."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class IRPlayer(Base):
    """Initial Reaction player account model."""

    __tablename__ = "ir_players"

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

    __table_args__ = (
        UniqueConstraint("username_canonical", name="uq_ir_players_username_canonical"),
    )

    # Relationships
    backronym_entries = relationship(
        "IRBackronymEntry", back_populates="player", cascade="all, delete-orphan"
    )
    backronym_votes = relationship(
        "IRBackronymVote", back_populates="player", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "IRTransaction", back_populates="player", cascade="all, delete-orphan"
    )
    result_views = relationship(
        "IRResultView", back_populates="player", cascade="all, delete-orphan"
    )
    refresh_tokens = relationship(
        "IRRefreshToken", back_populates="player", cascade="all, delete-orphan"
    )
    daily_bonuses = relationship(
        "IRDailyBonus", back_populates="player", cascade="all, delete-orphan"
    )
