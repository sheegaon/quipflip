"""Meme Mint player model leveraging shared player base."""
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import relationship

from backend.models.player_base import PlayerBase


class MMPlayer(PlayerBase):
    """Player account for Meme Mint."""

    __tablename__ = "mm_players"

    __table_args__ = (
        UniqueConstraint("username_canonical", name="uq_mm_players_username_canonical"),
    )

    # Relationships
    transactions = relationship("MMTransaction", back_populates="player", cascade="all, delete-orphan")
    refresh_tokens = relationship("MMRefreshToken", back_populates="player", cascade="all, delete-orphan")
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
