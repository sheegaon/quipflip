"""Base Transaction model with common fields and functionality."""
from __future__ import annotations

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
from backend.utils.idempotency import build_idempotency_key


class TransactionBase(Base):
    """Base transaction ledger model."""
    
    __abstract__ = True

    transaction_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    player_id = get_uuid_column(nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # Negative for charges, positive for payouts
    type = Column(String(50), nullable=False, index=True)
    reference_id = get_uuid_column(nullable=True, index=True)  # References round_id, phraseset_id, vote_id, or quest_id
    idempotency_key = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)
    wallet_type = Column(String(20), default="wallet", nullable=False)  # "wallet" or "vault"
    wallet_balance_after = Column(Integer, nullable=True)  # For audit trail
    vault_balance_after = Column(Integer, nullable=True)  # For audit trail

    def __init__(self, **kwargs):
        if not kwargs.get("idempotency_key"):
            kwargs["idempotency_key"] = build_idempotency_key(self.__tablename__, kwargs)
        super().__init__(**kwargs)

    def __repr__(self):
        return (f"<{self.__class__.__name__}(transaction_id={self.transaction_id}, amount={self.amount}, "
                f"type={self.type})>")
