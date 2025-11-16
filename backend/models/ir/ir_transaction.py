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
    transaction_type = Column(String(50), nullable=False, index=True)  # ir_backronym_entry, ir_vote_entry, etc.
    amount = Column(Integer, nullable=False)  # Negative for charges, positive for payouts
    vault_contribution = Column(Integer, nullable=False, server_default='0')
    entry_id = get_uuid_column(nullable=True)
    set_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_ir_transaction_player", player_id),
        Index("ix_ir_transaction_type", transaction_type),
        Index("ix_ir_transaction_created", created_at),
    )

    # Relationships
    player = relationship("IRPlayer", back_populates="transactions")
