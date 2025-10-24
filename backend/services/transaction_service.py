"""Transaction service for atomic balance updates."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import uuid
import logging

from backend.models.player import Player
from backend.models.transaction import Transaction
from backend.utils import lock_client
from backend.utils.exceptions import InsufficientBalanceError

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for managing player transactions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transaction(
        self,
        player_id: UUID,
        amount: int,
        trans_type: str,
        reference_id: UUID | None = None,
        auto_commit: bool = True,
        skip_lock: bool = False,
    ) -> Transaction:
        """
        Create transaction and update player balance atomically.

        Uses distributed lock to prevent race conditions (unless skip_lock=True).

        Args:
            player_id: Player UUID
            amount: Amount (negative for charges, positive for payouts)
            trans_type: Transaction type
            reference_id: Optional reference to round/phraseset/vote
            auto_commit: If True, commits immediately. If False, caller must commit.
            skip_lock: If True, assumes caller has already acquired the lock.

        Returns:
            Created transaction

        Raises:
            InsufficientBalanceError: If balance would go negative
        """
        async def _create_transaction_impl():
            # Get current player with row lock
            result = await self.db.execute(
                select(Player).where(Player.player_id == player_id).with_for_update()
            )
            player = result.scalar_one_or_none()

            if not player:
                raise ValueError(f"Player not found: {player_id}")

            # Calculate new balance
            new_balance = player.balance + amount

            # Check sufficient balance for negative transactions
            if new_balance < 0:
                raise InsufficientBalanceError(
                    f"Insufficient balance: {player.balance} + {amount} = {new_balance} < 0"
                )

            # Update balance
            player.balance = new_balance

            # Create transaction record
            transaction = Transaction(
                transaction_id=uuid.uuid4(),
                player_id=player_id,
                amount=amount,
                type=trans_type,
                reference_id=reference_id,
                balance_after=new_balance,
            )

            self.db.add(transaction)

            if auto_commit:
                await self.db.commit()
                await self.db.refresh(transaction)

            logger.info(
                f"Transaction created: player={player_id}, amount={amount}, "
                f"type={trans_type}, new_balance={new_balance}, auto_commit={auto_commit}"
            )

            return transaction

        if skip_lock:
            return await _create_transaction_impl()
        else:
            lock_name = f"create_transaction:{player_id}"
            with lock_client.lock(lock_name, timeout=10):
                return await _create_transaction_impl()

    async def get_player_transactions(
        self,
        player_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """Get player transaction history."""
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.player_id == player_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
