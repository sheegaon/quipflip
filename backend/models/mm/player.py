"""Meme Mint player model leveraging the unified players table."""
from sqlalchemy.orm import relationship

from backend.models.player import Player


class MMPlayer(Player):
    """Unified player representation for Meme Mint flows.

    This subclass shares the ``players`` table with :class:`~backend.models.player.Player`
    but exposes Meme Mint–specific relationships and convenience properties that work
    with the ``mm_player_data`` table.
    """

    __tablename__ = None  # Inherit the unified "players" table

    # Relationships
    mm_player_data = relationship(
        "MMPlayerData",
        uselist=False,
        back_populates="player",
        cascade="all, delete-orphan",
        lazy="joined",
    )
    transactions = relationship("MMTransaction", back_populates="player", cascade="all, delete-orphan")
    daily_bonuses = relationship("MMDailyBonus", back_populates="player", cascade="all, delete-orphan")
    vote_rounds = relationship("MMVoteRound", back_populates="player", cascade="all, delete-orphan")
    captions = relationship("MMCaption", back_populates="author", cascade="all, delete-orphan")
    caption_submissions = relationship(
        "MMCaptionSubmission", back_populates="player", cascade="all, delete-orphan"
    )
    caption_seen_records = relationship(
        "MMCaptionSeen", back_populates="player", cascade="all, delete-orphan"
    )
    daily_states = relationship(
        "MMPlayerDailyState", back_populates="player", cascade="all, delete-orphan"
    )
    created_circles = relationship(
        "MMCircle",
        foreign_keys="MMCircle.created_by_player_id",
        back_populates="created_by"
    )
    circle_memberships = relationship(
        "MMCircleMember",
        back_populates="player"
    )
    circle_join_requests = relationship(
        "MMCircleJoinRequest",
        foreign_keys="MMCircleJoinRequest.player_id",
        back_populates="player"
    )

    def _ensure_mm_data(self):
        """Ensure an MMPlayerData record exists for delegated properties."""

        if self.mm_player_data is None:
            from backend.models.mm.player_data import MMPlayerData

            self.mm_player_data = MMPlayerData(player_id=self.player_id)
        return self.mm_player_data

    # Meme Mint balance helpers
    @property
    def wallet(self) -> int:
        data = self.mm_player_data
        return data.wallet if data else 0

    @wallet.setter
    def wallet(self, value: int) -> None:
        self._ensure_mm_data().wallet = value

    @property
    def vault(self) -> int:
        data = self.mm_player_data
        return data.vault if data else 0

    @vault.setter
    def vault(self, value: int) -> None:
        self._ensure_mm_data().vault = value

    # Tutorial helpers
    @property
    def tutorial_completed(self) -> bool:
        data = self.mm_player_data
        return data.tutorial_completed if data else False

    @tutorial_completed.setter
    def tutorial_completed(self, value: bool) -> None:
        self._ensure_mm_data().tutorial_completed = value

    @property
    def tutorial_progress(self) -> str:
        data = self.mm_player_data
        return data.tutorial_progress if data else "not_started"

    @tutorial_progress.setter
    def tutorial_progress(self, value: str) -> None:
        self._ensure_mm_data().tutorial_progress = value

    @property
    def tutorial_started_at(self):
        data = self.mm_player_data
        return data.tutorial_started_at if data else None

    @tutorial_started_at.setter
    def tutorial_started_at(self, value) -> None:
        self._ensure_mm_data().tutorial_started_at = value

    @property
    def tutorial_completed_at(self):
        data = self.mm_player_data
        return data.tutorial_completed_at if data else None

    @tutorial_completed_at.setter
    def tutorial_completed_at(self, value) -> None:
        self._ensure_mm_data().tutorial_completed_at = value

    # Guest vote lockout helpers
    @property
    def consecutive_incorrect_votes(self) -> int:
        data = self.mm_player_data
        return data.consecutive_incorrect_votes if data else 0

    @consecutive_incorrect_votes.setter
    def consecutive_incorrect_votes(self, value: int) -> None:
        self._ensure_mm_data().consecutive_incorrect_votes = value

    @property
    def vote_lockout_until(self):
        data = self.mm_player_data
        return data.vote_lockout_until if data else None

    @vote_lockout_until.setter
    def vote_lockout_until(self, value) -> None:
        self._ensure_mm_data().vote_lockout_until = value
