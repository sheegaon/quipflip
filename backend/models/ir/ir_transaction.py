"""IR Transaction model (ledger)."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class IRTransaction(Base):
    """Initial Reaction transaction ledger."""

    __tablename__ = "ir_transactions"

    transaction_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount = Column(Integer, nullable=False)  # Negative for charges, positive for payouts
    type = Column(String(50), nullable=False, index=True)  # ir_backronym_entry, ir_vote_entry, etc.
    wallet_type = Column(String(20), default="wallet", nullable=False)  # wallet or vault
    reference_id = get_uuid_column(nullable=True, index=True)  # set_id, vote_id, etc.
    wallet_balance_after = Column(Integer, nullable=True)
    vault_balance_after = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_ir_transaction_player_id", player_id),
        Index("ix_ir_transaction_type", type),
        Index("ix_ir_transaction_reference_id", reference_id),
        Index("ix_ir_transaction_created_at", created_at),
        Index("ix_ir_transaction_player_created", player_id, created_at),
    )

    # Relationships
    player = relationship("IRPlayer", back_populates="transactions")
