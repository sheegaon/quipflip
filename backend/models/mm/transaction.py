"""Transaction ledger entries for Meme Mint."""
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import relationship

from backend.models.transaction_base import TransactionBase
from backend.models.base import get_uuid_column


class MMTransaction(TransactionBase):
    """Transaction ledger scoped to Meme Mint."""

    __tablename__ = "mm_transactions"

    player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"), nullable=False
    )

    player = relationship("MMPlayer", back_populates="transactions")

    __table_args__ = (
        Index("ix_mm_transactions_player_created", "player_id", "created_at"),
    )
