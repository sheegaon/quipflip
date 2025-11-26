"""Refresh token storage for Meme Mint authentication."""
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from backend.models.refresh_token_base import RefreshTokenBase
from backend.models.base import get_uuid_column


class MMRefreshToken(RefreshTokenBase):
    """Stored refresh tokens tied to Meme Mint players."""

    __tablename__ = "mm_refresh_tokens"

    player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"), nullable=False, index=True
    )

    player = relationship("MMPlayer", back_populates="refresh_tokens")
