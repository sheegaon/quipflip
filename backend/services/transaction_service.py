"""Transaction service for atomic balance updates."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import uuid
import logging

from backend.models.player_base import PlayerBase
from backend.models.transaction_base import TransactionBase
from backend.services.auth_service import GameType
from backend.utils import lock_client
from backend.utils.exceptions import InsufficientBalanceError
from backend.utils.model_registry import get_player_model, get_transaction_model

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for managing player transactions."""

    def __init__(self, db: AsyncSession, game_type: GameType = GameType.QF):
        self.db = db
        self.game_type = game_type
        self.player_model = get_player_model(game_type)
        self.transaction_model = get_transaction_model(game_type)

    async def create_transaction(
        self,
        player_id: UUID,
        amount: int,
        trans_type: str,
        reference_id: UUID | None = None,
        auto_commit: bool = True,
        skip_lock: bool = False,
        wallet_type: str = "wallet",
    ) -> TransactionBase:
        """
        Create transaction and update player balance atomically.

        Uses distributed lock to prevent race conditions (unless skip_lock=True).

        Args:
            player_id: PlayerBase UUID
            amount: Amount (negative for charges, positive for payouts)
            trans_type: TransactionBase type
            reference_id: Optional reference to round/phraseset/vote
            auto_commit: If True, commits immediately. If False, caller must commit.
            skip_lock: If True, assumes caller has already acquired the lock.
            wallet_type: "wallet" or "vault" - which balance to update

        Returns:
            Created transaction

        Raises:
            InsufficientBalanceError: If balance would go negative
        """
        async def _create_transaction_impl():
            # Get current player with row lock
            result = await self.db.execute(
                select(self.player_model).where(self.player_model.player_id == player_id).with_for_update()
            )
            player = result.scalar_one_or_none()

            if not player:
                raise ValueError(f"Player not found: {player_id}")

            # Calculate new balance based on wallet type
            if wallet_type == "vault":
                current_balance = player.vault
                new_balance = current_balance + amount

                # Check sufficient balance for negative transactions
                if new_balance < 0:
                    raise InsufficientBalanceError(
                        f"Insufficient vault balance: {current_balance} + {amount} = {new_balance} < 0"
                    )

                # Update vault
                player.vault = new_balance
            else:
                current_balance = player.wallet
                new_balance = current_balance + amount

                # Check sufficient balance for negative transactions
                if new_balance < 0:
                    raise InsufficientBalanceError(
                        f"Insufficient wallet balance: {current_balance} + {amount} = {new_balance} < 0"
                    )

                # Update wallet
                player.wallet = new_balance

            # Create transaction record
            transaction = self.transaction_model(
                transaction_id=uuid.uuid4(),
                player_id=player_id,
                amount=amount,
                type=trans_type,
                reference_id=reference_id,
                balance_after=player.wallet + player.vault,  # Legacy column: total balance
                wallet_type=wallet_type,
                wallet_balance_after=player.wallet,
                vault_balance_after=player.vault,
            )

            self.db.add(transaction)

            if auto_commit:
                await self.db.commit()
                await self.db.refresh(transaction)

            logger.info(
                f"TransactionBase created: player={player_id}, amount={amount}, "
                f"type={trans_type}, wallet_type={wallet_type}, "
                f"new_wallet={player.wallet}, new_vault={player.vault}, auto_commit={auto_commit}"
            )

            return transaction

        if skip_lock:
            return await _create_transaction_impl()
        else:
            lock_name = f"create_transaction:{player_id}"
            with lock_client.lock(lock_name, timeout=10):
                return await _create_transaction_impl()

    async def create_split_payout(
        self,
        player_id: UUID,
        gross_amount: int,
        cost: int,
        trans_type: str,
        reference_id: UUID | None = None,
        auto_commit: bool = True,
        skip_lock: bool = False,
    ) -> tuple[TransactionBase | None, TransactionBase | None]:
        """
        Create payout with 70/30 split between wallet and vault based on net earnings.

        Uses distributed lock to prevent race conditions (unless skip_lock=True).

        Rules:
        - If net earnings (gross - cost) > 0:
          - 70% of net goes to wallet
          - 30% of net goes to vault
          - Cost is returned to wallet
        - If net earnings <= 0:
          - All gross earnings go back to wallet

        Args:
            player_id: PlayerBase UUID
            gross_amount: Gross payout amount
            cost: Cost that was paid to enter the round
            trans_type: TransactionBase type (e.g., "vote_payout", "prize_payout")
            reference_id: Optional reference to round/phraseset/vote
            auto_commit: If True, commits immediately. If False, caller must commit.
            skip_lock: If True, assumes caller has already acquired the lock.

        Returns:
            Tuple of (wallet_transaction, vault_transaction)
        """
        async def _create_split_payout_impl():
            net_earnings = gross_amount - cost

            if net_earnings <= 0:
                # All gross earnings go back to wallet
                wallet_txn = await self.create_transaction(
                    player_id=player_id,
                    amount=gross_amount,
                    trans_type=trans_type,
                    reference_id=reference_id,
                    auto_commit=auto_commit,
                    skip_lock=True,  # Lock already acquired by outer function
                    wallet_type="wallet",
                )
                return wallet_txn, None
            else:
                # Split net earnings: 70% to wallet, 30% to vault
                # Also return the cost to wallet
                vault_amount = int(net_earnings * 0.3)
                wallet_amount = gross_amount - vault_amount

                # Create wallet transaction (cost + 70% of net)
                wallet_txn = await self.create_transaction(
                    player_id=player_id,
                    amount=wallet_amount,
                    trans_type=trans_type,
                    reference_id=reference_id,
                    auto_commit=False,
                    skip_lock=True,  # Lock already acquired by outer function
                    wallet_type="wallet",
                )

                # Create vault transaction (30% of net)
                vault_txn = await self.create_transaction(
                    player_id=player_id,
                    amount=vault_amount,
                    trans_type="vault_rake",
                    reference_id=reference_id,
                    auto_commit=False,
                    skip_lock=True,  # Lock already acquired by outer function
                    wallet_type="vault",
                )

                if auto_commit:
                    await self.db.commit()
                    await self.db.refresh(wallet_txn)
                    await self.db.refresh(vault_txn)

                logger.info(
                    f"Split payout created: player={player_id}, gross={gross_amount}, cost={cost}, "
                    f"net={net_earnings}, wallet={wallet_amount}, vault={vault_amount}"
                )

                return wallet_txn, vault_txn

        if skip_lock:
            return await _create_split_payout_impl()
        else:
            lock_name = f"create_transaction:{player_id}"
            with lock_client.lock(lock_name, timeout=10):
                return await _create_split_payout_impl()

    async def get_player_transactions(
        self,
        player_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TransactionBase]:
        """Get player transaction history."""
        result = await self.db.execute(
            select(self.transaction_model)
            .where(self.transaction_model.player_id == player_id)
            .order_by(self.transaction_model.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
