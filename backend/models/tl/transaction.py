"""ThinkLink transaction model."""
import uuid
from sqlalchemy import Column, ForeignKey, String, Integer, DateTime, Text, Index
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class TLTransaction(Base):
    """ThinkLink transaction ledger.

    Tracks all balance changes for a player (entries, payouts, refunds, bonuses).
    """

    __tablename__ = "tl_transaction"

    transaction_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False
    )
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # round_entry, round_payout, daily_bonus, refund, etc.
    round_id = get_uuid_column(
        ForeignKey("tl_round.round_id", ondelete="SET NULL"),
        nullable=True
    )
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        Index('idx_tl_transaction_player', 'player_id'),
    )

    def __repr__(self):
        return (f"<TLTransaction(transaction_id={self.transaction_id}, player_id={self.player_id}, "
        f"amount={self.amount})>")
