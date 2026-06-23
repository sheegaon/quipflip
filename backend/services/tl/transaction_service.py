"""ThinkLink transaction service for balance updates."""
from __future__ import annotations

import logging
import uuid
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.tl.player_data import TLPlayerData
from backend.models.tl.transaction import TLTransaction
from backend.utils.idempotency import build_idempotency_key

logger = logging.getLogger(__name__)


class TLTransactionService:
    """Service for managing ThinkLink player transactions and balance updates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load_player_data(self, player_id: UUID):
        result = await self.db.execute(
            select(TLPlayerData)
            .where(TLPlayerData.player_id == player_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def create_transaction(
        self,
        player_id: UUID,
        amount: int,
        transaction_type: str,
        round_id: UUID | None = None,
        description: str | None = None,
        target_wallet: str = "wallet",
    ) -> TLTransaction:
        """Create transaction and update player balance atomically."""

        idempotency_key = build_idempotency_key(
            TLTransaction.__tablename__,
            {
                "player_id": player_id,
                "amount": amount,
                "transaction_type": transaction_type,
                "round_id": round_id,
                "target_wallet": target_wallet,
                "description": description,
            },
        )

        existing = await self.db.execute(
            select(TLTransaction).where(TLTransaction.idempotency_key == idempotency_key)
        )
        existing_transaction = existing.scalar_one_or_none()
        if existing_transaction:
            return existing_transaction

        try:
            async with self.db.begin_nested():
                player_data = await self._load_player_data(player_id)
                if not player_data:
                    from backend.config import get_settings

                    settings = get_settings()
                    player_data = TLPlayerData(
                        player_id=player_id,
                        wallet=settings.tl_starting_balance,
                        vault=0,
                    )
                    self.db.add(player_data)
                    await self.db.flush()

                balance_column = TLPlayerData.vault if target_wallet == "vault" else TLPlayerData.wallet
                values = {
                    "wallet": TLPlayerData.wallet if target_wallet == "vault" else TLPlayerData.wallet + amount,
                    "vault": TLPlayerData.vault if target_wallet != "vault" else TLPlayerData.vault + amount,
                }
                stmt = update(TLPlayerData).where(TLPlayerData.player_id == player_id)
                if amount < 0:
                    stmt = stmt.where(balance_column + amount >= 0)
                stmt = stmt.values(**values)

                result = await self.db.execute(stmt)
                if result.rowcount != 1:
                    current = await self._load_player_data(player_id)
                    if not current:
                        raise ValueError(f"Player not found: {player_id}")

                    current_balance = current.vault if target_wallet == "vault" else current.wallet
                    raise ValueError(
                        f"Insufficient {target_wallet} balance: {current_balance} + {amount} = "
                        f"{current_balance + amount} < 0"
                    )

                player_data = await self._load_player_data(player_id)
                if not player_data:
                    raise ValueError(f"Player not found after update: {player_id}")

                transaction = TLTransaction(
                    transaction_id=uuid.uuid4(),
                    player_id=player_id,
                    amount=amount,
                    transaction_type=transaction_type,
                    round_id=round_id,
                    description=description or f"{transaction_type}: {amount} coins",
                    idempotency_key=idempotency_key,
                )
                self.db.add(transaction)
                await self.db.flush()

                logger.info(
                    "TL Transaction created: player_id=%s amount=%s type=%s target=%s new_wallet=%s new_vault=%s",
                    player_id,
                    amount,
                    transaction_type,
                    target_wallet,
                    player_data.wallet,
                    player_data.vault,
                )

                return transaction
        except IntegrityError:
            existing = await self.db.execute(
                select(TLTransaction).where(TLTransaction.idempotency_key == idempotency_key)
            )
            existing_transaction = existing.scalar_one_or_none()
            if existing_transaction:
                return existing_transaction
            raise
        except Exception as exc:
            logger.error("❌ Failed to create TL transaction: %s", exc)
            raise

    async def get_player_transactions(
        self,
        player_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TLTransaction]:
        """Get player transaction history."""
        result = await self.db.execute(
            select(TLTransaction)
            .where(TLTransaction.player_id == player_id)
            .order_by(TLTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())