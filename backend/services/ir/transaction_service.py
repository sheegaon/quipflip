"""IR Transaction Service - Ledger and wallet/vault management for Initial Reaction."""

import logging
import uuid
from datetime import datetime, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.ir.ir_transaction import IRTransaction
from backend.models.ir.ir_player import IRPlayer
from backend.services.ir.player_service import IRPlayerService, IRPlayerError

logger = logging.getLogger(__name__)


class IRTransactionError(RuntimeError):
    """Raised when transaction service fails."""


class IRTransactionService:
    """Service for managing IR wallet/vault transactions and ledger."""

    # Transaction type constants
    ENTRY_CREATION = "ir_backronym_entry"
    VOTE_PAYOUT = "ir_vote_payout"
    CREATOR_PAYOUT = "ir_creator_payout"
    VAULT_CONTRIBUTION = "vault_contribution"
    DAILY_BONUS = "daily_bonus"
    ADMIN_ADJUSTMENT = "admin_adjustment"

    def __init__(self, db: AsyncSession):
        """Initialize IR transaction service.

        Args:
            db: Database session
        """
        self.db = db
        self.player_service = IRPlayerService(db)

    async def record_transaction(
        self,
        player_id: str,
        transaction_type: str,
        amount: int,
        vault_contribution: int = 0,
        entry_id: str | None = None,
        set_id: str | None = None,
    ) -> IRTransaction:
        """Record a transaction in the ledger.

        Args:
            player_id: Player UUID
            transaction_type: Type of transaction
            amount: Amount (positive for income, negative for expenses)
            vault_contribution: Amount contributed to vault (rake)
            entry_id: Optional backronym entry ID
            set_id: Optional backronym set ID

        Returns:
            IRTransaction: Created transaction record

        Raises:
            IRTransactionError: If transaction fails
        """
        transaction_id = str(uuid.uuid4())
        transaction = IRTransaction(
            transaction_id=transaction_id,
            player_id=player_id,
            transaction_type=transaction_type,
            amount=amount,
            vault_contribution=vault_contribution,
            entry_id=entry_id,
            set_id=set_id,
            created_at=datetime.now(UTC),
        )
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)

        logger.debug(f"Recorded IR transaction {transaction_id} for player {player_id}")
        return transaction

    async def process_vote_payout(
        self,
        player_id: str,
        amount: int,
        set_id: str,
    ) -> IRTransaction:
        """Process vote payout for player.

        Args:
            player_id: Player UUID
            amount: Payout amount
            set_id: Backronym set ID

        Returns:
            IRTransaction: Created transaction

        Raises:
            IRTransactionError: If payout fails
        """
        try:
            # Calculate vault rake (30%)
            vault_contribution = int(amount * 0.3)
            wallet_amount = amount - vault_contribution

            # Update player wallet
            player = await self.player_service.update_wallet(player_id, wallet_amount)

            # Record transaction
            transaction = await self.record_transaction(
                player_id=player_id,
                transaction_type=self.VOTE_PAYOUT,
                amount=wallet_amount,
                vault_contribution=vault_contribution,
                set_id=set_id,
            )

            logger.info(f"Vote payout {wallet_amount} IC (vault: {vault_contribution}) to player {player_id}")
            return transaction

        except IRPlayerError as e:
            raise IRTransactionError(f"vote_payout_failed: {str(e)}") from e

    async def process_creator_payout(
        self,
        player_id: str,
        amount: int,
        set_id: str,
    ) -> IRTransaction:
        """Process creator payout for player.

        Args:
            player_id: Player UUID
            amount: Payout amount
            set_id: Backronym set ID

        Returns:
            IRTransaction: Created transaction

        Raises:
            IRTransactionError: If payout fails
        """
        try:
            # Creator gets full amount (no rake for creator payouts)
            await self.player_service.update_wallet(player_id, amount)

            # Record transaction
            transaction = await self.record_transaction(
                player_id=player_id,
                transaction_type=self.CREATOR_PAYOUT,
                amount=amount,
                vault_contribution=0,
                set_id=set_id,
            )

            logger.info(f"Creator payout {amount} IC to player {player_id}")
            return transaction

        except IRPlayerError as e:
            raise IRTransactionError(f"creator_payout_failed: {str(e)}") from e

    async def process_vault_contribution(
        self,
        player_id: str,
        amount: int,
    ) -> IRTransaction:
        """Process vault contribution (rake).

        Args:
            player_id: Player UUID
            amount: Contribution amount

        Returns:
            IRTransaction: Created transaction

        Raises:
            IRTransactionError: If contribution fails
        """
        try:
            # Transfer from wallet to vault
            await self.player_service.transfer_wallet_to_vault(player_id, amount)

            # Record transaction
            transaction = await self.record_transaction(
                player_id=player_id,
                transaction_type=self.VAULT_CONTRIBUTION,
                amount=0,
                vault_contribution=amount,
            )

            logger.info(f"Vault contribution {amount} IC from player {player_id}")
            return transaction

        except IRPlayerError as e:
            raise IRTransactionError(f"vault_contribution_failed: {str(e)}") from e

    async def process_daily_bonus(
        self,
        player_id: str,
        amount: int,
    ) -> IRTransaction:
        """Process daily login bonus.

        Args:
            player_id: Player UUID
            amount: Bonus amount (default: 100 IC)

        Returns:
            IRTransaction: Created transaction

        Raises:
            IRTransactionError: If bonus fails
        """
        try:
            await self.player_service.update_wallet(player_id, amount)

            transaction = await self.record_transaction(
                player_id=player_id,
                transaction_type=self.DAILY_BONUS,
                amount=amount,
                vault_contribution=0,
            )

            logger.info(f"Daily bonus {amount} IC awarded to player {player_id}")
            return transaction

        except IRPlayerError as e:
            raise IRTransactionError(f"daily_bonus_failed: {str(e)}") from e

    async def get_player_transactions(
        self,
        player_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[IRTransaction]:
        """Get transaction history for player.

        Args:
            player_id: Player UUID
            limit: Max results
            offset: Results offset

        Returns:
            list[IRTransaction]: Transactions ordered by created_at DESC
        """
        stmt = (
            select(IRTransaction)
            .where(IRTransaction.player_id == player_id)
            .order_by(IRTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_ledger_summary(self, player_id: str) -> dict:
        """Get wallet/vault summary for player.

        Args:
            player_id: Player UUID

        Returns:
            dict: Summary with wallet, vault, total balance

        Raises:
            IRTransactionError: If player not found
        """
        player = await self.player_service.get_player_by_id(player_id)
        if not player:
            raise IRTransactionError("player_not_found")

        return {
            "player_id": player_id,
            "wallet": player.wallet,
            "vault": player.vault,
            "total_balance": player.wallet + player.vault,
        }
