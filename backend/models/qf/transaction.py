"""Transaction ledger model."""
from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.models.transaction_base import TransactionBase
from backend.models.base import get_uuid_column


class QFTransaction(TransactionBase):
    """Transaction ledger model."""
    __tablename__ = "qf_transactions"

    # Override player_id to add QF-specific foreign key constraint
    player_id = get_uuid_column(ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationships
    player = relationship("Player", back_populates="transactions")

    # Indexes
    __table_args__ = (
        Index('ix_transactions_player_created', 'player_id', 'created_at'),
    )
