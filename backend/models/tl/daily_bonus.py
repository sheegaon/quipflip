"""Daily bonus tracking for ThinkLink players."""
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.models.daily_bonus_base import DailyBonusBase
from backend.models.base import get_uuid_column


class TLDailyBonus(DailyBonusBase):
    """Daily bonus tracking model for ThinkLink."""

    __tablename__ = "tl_daily_bonuses"

    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False
    )

    player = relationship("TLPlayer", back_populates="tl_daily_bonuses")

    __table_args__ = (
        UniqueConstraint("player_id", "date", name="uq_tl_player_daily_bonus"),
    )
