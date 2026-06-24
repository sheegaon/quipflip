"""Magic-link model used for guest save and email sign-in flows."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MagicLink(Base):
    """Single-use token used to verify an email and finalize account saving."""

    __tablename__ = "magic_links"

    magic_link_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    guest_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = get_uuid_column(
        ForeignKey("accounts.account_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    redirect_path = Column(String(255), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    guest_player = relationship(
        "Player",
        foreign_keys=[guest_player_id],
        lazy="selectin",
    )
    account = relationship(
        "Account",
        foreign_keys=[account_id],
        lazy="selectin",
    )

    def is_active(self, now: datetime | None = None) -> bool:
        """Return True when the link has not expired or been consumed."""
        current_time = now or datetime.now(UTC)
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return self.consumed_at is None and expires_at > current_time

    def __repr__(self) -> str:
        return (
            f"<MagicLink(magic_link_id={self.magic_link_id}, email={self.email}, "
            f"expires_at={self.expires_at})>"
        )
