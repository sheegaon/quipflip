"""Base Transaction model with common fields and functionality."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
)
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class TransactionBase(Base):
    """Base transaction ledger model."""
    
    __abstract__ = True

    transaction_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Negative for charges, positive for payouts
    type = Column(String(50), nullable=False, index=True)
    reference_id = get_uuid_column(nullable=True, index=True)  # References round_id, phraseset_id, vote_id, or quest_id
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)
    wallet_type = Column(String(20), default="wallet", nullable=False)  # "wallet" or "vault"
    wallet_balance_after = Column(Integer, nullable=True)  # For audit trail
    vault_balance_after = Column(Integer, nullable=True)  # For audit trail

    def __repr__(self):
        return (f"<{self.__class__.__name__}(transaction_id={self.transaction_id}, amount={self.amount}, "
                f"type={self.type})>")
