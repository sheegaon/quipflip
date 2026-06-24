"""Account model for recoverable cross-device identity."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class Account(Base):
    """Recoverable account that can own one or more player identities."""

    __tablename__ = "accounts"

    account_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    primary_email = Column(String(255), unique=True, nullable=False, index=True)
    primary_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    primary_player = relationship(
        "Player",
        foreign_keys=[primary_player_id],
        lazy="selectin",
    )
    players = relationship(
        "Player",
        back_populates="account",
        foreign_keys="Player.account_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Account(account_id={self.account_id}, primary_email={self.primary_email}, "
            f"primary_player_id={self.primary_player_id})>"
        )
