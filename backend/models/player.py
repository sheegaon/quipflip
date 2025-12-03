"""Unified player model for cross-game authentication."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column
from backend.utils.model_registry import GameType


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

    # Relationships
    phraseset_activities = relationship(
        "PhrasesetActivity",
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    rounds = relationship(
        "Round",
        back_populates="player",
        foreign_keys="Round.player_id",
        lazy="selectin",
    )
    votes = relationship("Vote", back_populates="player", lazy="selectin")
    transactions = relationship("QFTransaction", back_populates="player", lazy="selectin")
    daily_bonuses = relationship("QFDailyBonus", back_populates="player", lazy="selectin")
    result_views = relationship("QFResultView", back_populates="player", lazy="selectin")
    abandoned_prompts = relationship(
        "PlayerAbandonedPrompt", back_populates="player", lazy="selectin"
    )
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    quests = relationship("QFQuest", back_populates="player", lazy="selectin")
    qf_player_data = relationship(
        "QFPlayerData",
        uselist=False,
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    mm_player_data = relationship(
        "MMPlayerData",
        uselist=False,
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    ir_player_data = relationship(
        "IRPlayerData",
        uselist=False,
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tl_player_data = relationship(
        "TLPlayerData",
        uselist=False,
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tl_rounds = relationship(
        "TLRound",
        back_populates="player",
        foreign_keys="TLRound.player_id",
        lazy="selectin",
    )
    tl_daily_bonuses = relationship("TLDailyBonus", back_populates="player", lazy="selectin")
    tl_daily_states = relationship("TLPlayerDailyState", back_populates="player", lazy="selectin")

    def get_game_data(self, game_type: GameType):
        """Return the per-game data object for the requested game.

        This helper avoids implicit creation of per-game data and requires
        callers to handle missing records explicitly.
        """

        if game_type == GameType.QF:
            return self.qf_player_data
        if game_type == GameType.TL:
            return self.tl_player_data
        if game_type == GameType.MM:
            return self.mm_player_data
        if game_type == GameType.IR:
            return self.ir_player_data
        raise ValueError(f"Unsupported game type: {game_type}")

    def __repr__(self):
        return (f"<Player(player_id={self.player_id}, username={self.username}, "
                f"email={self.email})>")
