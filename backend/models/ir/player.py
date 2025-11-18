"""Player model."""
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship
from backend.models.player_base import PlayerBase


class IRPlayer(PlayerBase):
    """Player account model."""
    __tablename__ = "ir_players"

    __table_args__ = (
        UniqueConstraint("username_canonical", name="uq_players_username_canonical"),
    )

    # Relationships
    backronym_entries = relationship("BackronymEntry", back_populates="player", cascade="all, delete-orphan")
    backronym_votes = relationship("BackronymVote", back_populates="player", cascade="all, delete-orphan")
    transactions = relationship("IRTransaction", back_populates="player", cascade="all, delete-orphan")
    result_views = relationship("IRResultView", back_populates="player", cascade="all, delete-orphan")
    refresh_tokens = relationship("IRRefreshToken", back_populates="player", cascade="all, delete-orphan")
    daily_bonuses = relationship("IRDailyBonus", back_populates="player", cascade="all, delete-orphan")
