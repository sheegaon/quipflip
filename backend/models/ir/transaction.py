"""Transaction ledger model."""
from sqlalchemy import Column, Integer, String, ForeignKey, Index, DateTime
from sqlalchemy.orm import relationship

from backend.models.transaction_base import TransactionBase
from backend.models.base import get_uuid_column


class IRTransaction(TransactionBase):
    """Transaction ledger model."""
    __tablename__ = "ir_transactions"

    # Override player_id to add IR-specific foreign key constraint
    player_id = get_uuid_column(ForeignKey("ir_players.player_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # IR-specific fields for backwards compatibility
    transaction_type = Column(String(50), nullable=False, index=True)  # ir_backronym_entry, ir_vote_entry, etc.
    vault_contribution = Column(Integer, nullable=False, server_default='0')
    entry_id = get_uuid_column(nullable=True)
    set_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    player = relationship("IRPlayer", back_populates="transactions")

    # Indexes - use string references for inherited columns
    __table_args__ = (
        Index("ix_transaction_player", "player_id"),
        Index("ix_transaction_type", "transaction_type"),
        Index("ix_transaction_created", "created_at"),
    )
