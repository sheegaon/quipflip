"""Unified player model for cross-game authentication."""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
)
from sqlalchemy.orm import relationship
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

    # Relationships
    phraseset_activities = relationship(
        "PhrasesetActivity", back_populates="player", cascade="all, delete-orphan"
    )
    rounds = relationship("Round", back_populates="player", foreign_keys="Round.player_id")
    votes = relationship("Vote", back_populates="player")
    transactions = relationship("QFTransaction", back_populates="player")
    daily_bonuses = relationship("QFDailyBonus", back_populates="player")
    result_views = relationship("QFResultView", back_populates="player")
    abandoned_prompts = relationship("PlayerAbandonedPrompt", back_populates="player")
    refresh_tokens = relationship("RefreshToken", back_populates="player", cascade="all, delete-orphan")
    quests = relationship("QFQuest", back_populates="player")
    qf_player_data = relationship(
        "QFPlayerData",
        uselist=False,
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def _ensure_qf_data(self):
        """Ensure a QFPlayerData record exists for delegated properties."""

        if self.qf_player_data is None:
            from backend.models.qf.player_data import QFPlayerData

            self.qf_player_data = QFPlayerData(player_id=self.player_id)
        return self.qf_player_data

    @property
    def wallet(self) -> int:
        data = self.qf_player_data
        return data.wallet if data else 0

    @wallet.setter
    def wallet(self, value: int) -> None:
        self._ensure_qf_data().wallet = value

    @property
    def vault(self) -> int:
        data = self.qf_player_data
        return data.vault if data else 0

    @vault.setter
    def vault(self, value: int) -> None:
        self._ensure_qf_data().vault = value

    @property
    def active_round_id(self):
        data = self.qf_player_data
        return data.active_round_id if data else None

    @active_round_id.setter
    def active_round_id(self, value):
        self._ensure_qf_data().active_round_id = value

    @property
    def tutorial_completed(self):
        data = self.qf_player_data
        return data.tutorial_completed if data else False

    @tutorial_completed.setter
    def tutorial_completed(self, value):
        self._ensure_qf_data().tutorial_completed = value

    @property
    def tutorial_progress(self):
        data = self.qf_player_data
        return data.tutorial_progress if data else "not_started"

    @tutorial_progress.setter
    def tutorial_progress(self, value):
        self._ensure_qf_data().tutorial_progress = value

    @property
    def tutorial_started_at(self):
        data = self.qf_player_data
        return data.tutorial_started_at if data else None

    @tutorial_started_at.setter
    def tutorial_started_at(self, value):
        self._ensure_qf_data().tutorial_started_at = value

    @property
    def tutorial_completed_at(self):
        data = self.qf_player_data
        return data.tutorial_completed_at if data else None

    @tutorial_completed_at.setter
    def tutorial_completed_at(self, value):
        self._ensure_qf_data().tutorial_completed_at = value

    @property
    def consecutive_incorrect_votes(self) -> int:
        data = self.qf_player_data
        return data.consecutive_incorrect_votes if data else 0

    @consecutive_incorrect_votes.setter
    def consecutive_incorrect_votes(self, value: int):
        self._ensure_qf_data().consecutive_incorrect_votes = value

    @property
    def vote_lockout_until(self):
        data = self.qf_player_data
        return data.vote_lockout_until if data else None

    @vote_lockout_until.setter
    def vote_lockout_until(self, value):
        self._ensure_qf_data().vote_lockout_until = value

    @property
    def flag_dismissal_streak(self) -> int:
        data = self.qf_player_data
        return data.flag_dismissal_streak if data else 0

    @flag_dismissal_streak.setter
    def flag_dismissal_streak(self, value: int):
        self._ensure_qf_data().flag_dismissal_streak = value

    @property
    def balance(self) -> int:
        """Return the player's total Quipflip balance (wallet + vault).

        This mirrors the convenience property previously available on the
        game-specific QFPlayer model so existing code and tests can continue
        to read a player's combined spendable funds from the unified model.
        """

        data = self.qf_player_data
        if data is None:
            return 0
        return data.balance

    def __repr__(self):
        return (f"<Player(player_id={self.player_id}, username={self.username}, "
                f"email={self.email})>")
