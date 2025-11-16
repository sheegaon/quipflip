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
    VOTE_ENTRY = "ir_vote_entry"
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

    async def _lock_player(self, player_id: str) -> IRPlayer:
        stmt = select(IRPlayer).where(IRPlayer.player_id == player_id).with_for_update()
        result = await self.db.execute(stmt)
        player = result.scalars().first()
        if not player:
            raise IRTransactionError("player_not_found")
        return player

    async def debit_wallet(
        self,
        player_id: str,
        amount: int,
        transaction_type: str,
        reference_id: str | None = None,
    ) -> IRTransaction:
        """Debit a player's wallet with locking and ledger entry."""

        if amount <= 0:
            raise IRTransactionError("amount_must_be_positive")

        async with self.db.begin():
            player = await self._lock_player(player_id)
            if player.wallet < amount:
                raise IRTransactionError("insufficient_wallet_balance")

            player.wallet -= amount
            transaction = IRTransaction(
                transaction_id=str(uuid.uuid4()),
                player_id=player_id,
                type=transaction_type,
                amount=-amount,
                wallet_type="wallet",
                reference_id=reference_id,
                wallet_balance_after=player.wallet,
                vault_balance_after=player.vault,
                created_at=datetime.now(UTC),
            )
            self.db.add(transaction)

        await self.db.refresh(transaction)
        return transaction

    async def credit_wallet(
        self,
        player_id: str,
        amount: int,
        transaction_type: str,
        reference_id: str | None = None,
        *,
        use_existing_transaction: bool = False,
    ) -> IRTransaction:
        """Credit a player's wallet with locking and ledger entry."""

        if amount <= 0:
            raise IRTransactionError("amount_must_be_positive")

        async def _create_credit_transaction() -> IRTransaction:
            player = await self._lock_player(player_id)
            player.wallet += amount
            transaction = IRTransaction(
                transaction_id=str(uuid.uuid4()),
                player_id=player_id,
                type=transaction_type,
                amount=amount,
                wallet_type="wallet",
                reference_id=reference_id,
                wallet_balance_after=player.wallet,
                vault_balance_after=player.vault,
                created_at=datetime.now(UTC),
            )
            self.db.add(transaction)
            return transaction

        if use_existing_transaction:
            transaction = await _create_credit_transaction()
            await self.db.flush()
        else:
            async with self.db.begin():
                transaction = await _create_credit_transaction()

        await self.db.refresh(transaction)
        return transaction

    async def credit_vault(
        self,
        player_id: str,
        amount: int,
        transaction_type: str,
        reference_id: str | None = None,
    ) -> IRTransaction:
        """Credit a player's vault balance with ledger entry."""

        if amount <= 0:
            raise IRTransactionError("amount_must_be_positive")

        async with self.db.begin():
            player = await self._lock_player(player_id)
            player.vault += amount
            transaction = IRTransaction(
                transaction_id=str(uuid.uuid4()),
                player_id=player_id,
                type=transaction_type,
                amount=amount,
                wallet_type="vault",
                reference_id=reference_id,
                wallet_balance_after=player.wallet,
                vault_balance_after=player.vault,
                created_at=datetime.now(UTC),
            )
            self.db.add(transaction)

        await self.db.refresh(transaction)
        return transaction

    async def record_transaction(
        self,
        player_id: str,
        transaction_type: str,
        amount: int,
        wallet_type: str = "wallet",
        reference_id: str | None = None,
        wallet_balance_after: int | None = None,
        vault_balance_after: int | None = None,
    ) -> IRTransaction:
        """Record a transaction in the ledger.

        Args:
            player_id: Player UUID
            transaction_type: Type of transaction
            amount: Amount (positive for income, negative for expenses)
            wallet_type: Either 'wallet' or 'vault'
            reference_id: Optional reference ID (set_id, entry_id, etc.)
            wallet_balance_after: Wallet balance after transaction
            vault_balance_after: Vault balance after transaction

        Returns:
            IRTransaction: Created transaction record

        Raises:
            IRTransactionError: If transaction fails
        """
        transaction_id = str(uuid.uuid4())
        transaction = IRTransaction(
            transaction_id=transaction_id,
            player_id=player_id,
            type=transaction_type,
            amount=amount,
            wallet_type=wallet_type,
            reference_id=reference_id,
            wallet_balance_after=wallet_balance_after,
            vault_balance_after=vault_balance_after,
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
            vault_rake = int(amount * (self.player_service.settings.ir_vault_rake_percent / 100))
            wallet_amount = amount - vault_rake

            # Update player wallet and vault
            wallet_txn = await self.credit_wallet(
                player_id=player_id,
                amount=wallet_amount,
                transaction_type=self.VOTE_PAYOUT,
                reference_id=set_id,
            )
            await self.credit_vault(
                player_id=player_id,
                amount=vault_rake,
                transaction_type=self.VAULT_CONTRIBUTION,
                reference_id=set_id,
            )

            logger.info(
                f"Vote payout {wallet_amount} IC (vault: {vault_rake}) to player {player_id}"
            )
            return wallet_txn

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
            transaction = await self.credit_wallet(
                player_id=player_id,
                amount=amount,
                transaction_type=self.CREATOR_PAYOUT,
                reference_id=set_id,
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
            transaction = await self.debit_wallet(
                player_id=player_id,
                amount=amount,
                transaction_type=self.VAULT_CONTRIBUTION,
            )
            await self.credit_vault(
                player_id=player_id,
                amount=amount,
                transaction_type=self.VAULT_CONTRIBUTION,
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
            player = await self.player_service.update_wallet(player_id, amount)

            transaction = await self.record_transaction(
                player_id=player_id,
                transaction_type=self.DAILY_BONUS,
                amount=amount,
                wallet_type="wallet",
                wallet_balance_after=player.wallet,
                vault_balance_after=player.vault,
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
