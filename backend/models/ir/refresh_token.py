"""Refresh token persistence model."""
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from backend.models.refresh_token_base import RefreshTokenBase
from backend.models.base import get_uuid_column


class IRRefreshToken(RefreshTokenBase):
    """Stored refresh tokens for JWT authentication."""

    __tablename__ = "ir_refresh_tokens"

    # Override player_id to add IR-specific foreign key constraint
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    player = relationship("Player", back_populates="refresh_tokens")
