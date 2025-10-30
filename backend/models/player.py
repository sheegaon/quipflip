"""Player model."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class Player(Base):
    """Player account model."""
    __tablename__ = "players"

    player_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    username = Column(String(80), unique=True, nullable=False)
    username_canonical = Column(String(80), nullable=False)
    pseudonym = Column(String(80), nullable=False, index=True)
    pseudonym_canonical = Column(String(80), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    balance = Column(Integer, default=1000, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    last_login_date = Column(DateTime(timezone=True), nullable=True)
    active_round_id = get_uuid_column(ForeignKey("rounds.round_id", ondelete="SET NULL"), nullable=True)
    is_guest = Column(Boolean, default=False, nullable=False)

    # Tutorial tracking
    tutorial_completed = Column(Boolean, default=False, nullable=False)
    tutorial_progress = Column(String(20), default='not_started', nullable=False)
    tutorial_started_at = Column(DateTime(timezone=True), nullable=True)
    tutorial_completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("username_canonical", name="uq_players_username_canonical"),
    )

    # Relationships
    active_round = relationship("Round", foreign_keys=[active_round_id], post_update=True)
    rounds = relationship("Round", back_populates="player", foreign_keys="Round.player_id")
    transactions = relationship("Transaction", back_populates="player")
    votes = relationship("Vote", back_populates="player")
    daily_bonuses = relationship("DailyBonus", back_populates="player")
    result_views = relationship("ResultView", back_populates="player")
    abandoned_prompts = relationship("PlayerAbandonedPrompt", back_populates="player")
    phraseset_activities = relationship("PhrasesetActivity", back_populates="player")
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="player",
        cascade="all, delete-orphan",
    )
    quests = relationship("Quest", back_populates="player")

    def __repr__(self):
        return f"<Player(player_id={self.player_id}, username={self.username}, balance={self.balance})>"
