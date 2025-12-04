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

        game_data_map = {
            GameType.QF: self.qf_player_data,
            GameType.TL: self.tl_player_data,
            GameType.MM: self.mm_player_data,
            GameType.IR: self.ir_player_data,
        }
        if game_type in game_data_map:
            return game_data_map[game_type]
        raise ValueError(f"Unsupported game type: {game_type}")

    @property
    def balance(self) -> int:
        """Return combined wallet + vault for Quipflip players.

        This mirrors the convenience property available on per-game data
        objects and keeps legacy balance lookups working.
        """

        source = self._wallet_source()
        if source:
            # All per-game player data objects expose wallet and vault
            return int(source.wallet or 0) + int(source.vault or 0)
        return 0

    def _wallet_source(self):
        """Return the first per-game data object that exposes wallet/vault fields."""

        for attr in ("qf_player_data", "ir_player_data", "mm_player_data", "tl_player_data"):
            data = self.__dict__.get(attr)
            if data is not None and hasattr(data, "wallet"):
                return data
        return None

    @property
    def wallet(self) -> int:
        source = self._wallet_source()
        return source.wallet if source else 0

    @wallet.setter
    def wallet(self, value: int):
        source = self._wallet_source()
        if not source:
            from backend.models.qf.player_data import QFPlayerData

            self.qf_player_data = QFPlayerData(player_id=self.player_id)
            source = self.qf_player_data
        source.wallet = value

    @property
    def vault(self) -> int:
        source = self._wallet_source()
        return source.vault if source else 0

    @vault.setter
    def vault(self, value: int):
        source = self._wallet_source()
        if not source:
            from backend.models.qf.player_data import QFPlayerData

            self.qf_player_data = QFPlayerData(player_id=self.player_id)
            source = self.qf_player_data
        source.vault = value

    @property
    def active_round_id(self):
        """Proxy active_round_id to the Quipflip-specific player data."""

        if self.qf_player_data:
            return self.qf_player_data.active_round_id
        return None

    @active_round_id.setter
    def active_round_id(self, value):
        if not self.qf_player_data:
            raise AttributeError("QF player data is not loaded; cannot set active_round_id")
        self.qf_player_data.active_round_id = value

    def __repr__(self):
        return (f"<Player(player_id={self.player_id}, username={self.username}, "
                f"email={self.email})>")
