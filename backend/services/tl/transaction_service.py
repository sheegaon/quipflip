"""ThinkLink transaction service for balance updates."""
import logging
import uuid
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.tl.transaction import TLTransaction
from backend.models.tl.player_data import TLPlayerData

logger = logging.getLogger(__name__)


class TLTransactionService:
    """Service for managing ThinkLink player transactions and balance updates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transaction(
        self,
        player_id: UUID,
        amount: int,
        transaction_type: str,
        round_id: UUID | None = None,
        description: str | None = None,
        target_wallet: str = "wallet",
    ) -> TLTransaction:
        """
        Create transaction and update player balance atomically.

        Args:
            player_id: Player UUID
            amount: Amount (positive for payouts, negative for charges)
            transaction_type: Transaction type (round_entry, round_payout_wallet, etc.)
            round_id: Optional reference to TLRound
            description: Optional transaction description
            target_wallet: "wallet" or "vault" - which balance to update

        Returns:
            Created TLTransaction

        Raises:
            ValueError: If player not found or insufficient balance
        """
        try:
            # Get or create player data with row lock for atomic updates
            result = await self.db.execute(
                select(TLPlayerData)
                .where(TLPlayerData.player_id == player_id)
                .with_for_update()
            )
            player_data = result.scalar_one_or_none()

            if not player_data:
                # Create new player data with default balances
                from backend.config import get_settings
                settings = get_settings()
                player_data = TLPlayerData(
                    player_id=player_id,
                    wallet=settings.tl_starting_balance,
                    vault=0
                )
                self.db.add(player_data)
                await self.db.flush()  # Get the row in DB for locking

            # Update the appropriate balance
            if target_wallet == "vault":
                current_balance = player_data.vault
                new_balance = current_balance + amount
                if new_balance < 0:
                    raise ValueError(f"Insufficient vault balance: {current_balance} + {amount} = {new_balance} < 0")
                player_data.vault = new_balance
            else:  # wallet
                current_balance = player_data.wallet
                new_balance = current_balance + amount
                if new_balance < 0:
                    raise ValueError(f"Insufficient wallet balance: {current_balance} + {amount} = {new_balance} < 0")
                player_data.wallet = new_balance

            # Create transaction record
            transaction = TLTransaction(
                transaction_id=uuid.uuid4(),
                player_id=player_id,
                amount=amount,
                transaction_type=transaction_type,
                round_id=round_id,
                description=description or f"{transaction_type}: {amount} coins"
            )
            self.db.add(transaction)

            # Flush to ensure consistency
            await self.db.flush()

            logger.info(
                f"TL Transaction created: player_id={player_id}, amount={amount}, "
                f"type={transaction_type}, target={target_wallet}, "
                f"new_wallet={player_data.wallet}, new_vault={player_data.vault}"
            )

            return transaction

        except Exception as e:
            logger.error(f"❌ Failed to create TL transaction: {e}")
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
