"""Transaction service for atomic balance updates."""
from __future__ import annotations

import logging
import uuid
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.transaction_base import TransactionBase
from backend.utils.exceptions import InsufficientBalanceError
from backend.utils.idempotency import build_idempotency_key
from backend.utils.model_registry import GameType, get_transaction_model

logger = logging.getLogger(__name__)


class TransactionService:
    """Service for managing player transactions."""

    ENTRY_CREATION = "ir_backronym_entry"
    VOTE_ENTRY = "ir_vote_entry"
    VOTE_PAYOUT = "ir_vote_payout"
    CREATOR_PAYOUT = "ir_creator_payout"
    VAULT_CONTRIBUTION = "ir_vault_contribution"

    def __init__(self, db: AsyncSession, game_type: GameType):
        self.db = db
        if game_type is None:
            raise ValueError("game_type must be provided for TransactionService")
        self.game_type = game_type
        if game_type == GameType.QF:
            from backend.models.qf.player_data import QFPlayerData

            self.player_data_model = QFPlayerData
        elif game_type == GameType.MM:
            from backend.models.mm.player_data import MMPlayerData

            self.player_data_model = MMPlayerData
        elif game_type == GameType.IR:
            from backend.models.ir.player_data import IRPlayerData

            self.player_data_model = IRPlayerData
        else:
            raise ValueError(f"Unsupported game type: {game_type}")
        self.transaction_model = get_transaction_model(game_type)

    def _build_idempotency_key(
        self,
        player_id: UUID,
        amount: int,
        trans_type: str,
        reference_id: UUID | None,
        wallet_type: str,
    ) -> str:
        return build_idempotency_key(
            self.transaction_model.__tablename__,
            {
                "game_type": self.game_type.value,
                "player_id": player_id,
                "amount": amount,
                "type": trans_type,
                "reference_id": reference_id,
                "wallet_type": wallet_type,
            },
        )

    def _is_ir_ledger(self) -> bool:
        return self.game_type == GameType.IR

    @staticmethod
    def _same_reference(left: UUID | str | None, right: UUID | str | None) -> bool:
        if left is None or right is None:
            return left is right
        return str(left).replace("-", "").lower() == str(right).replace("-", "").lower()

    def _validate_replay(
        self,
        transaction: TransactionBase,
        *,
        player_id: UUID,
        amount: int,
        trans_type: str,
        reference_id: UUID | None,
        wallet_type: str,
    ) -> None:
        """Reject reuse of an idempotency key for a different movement."""

        matches = (
            str(transaction.player_id).replace("-", "").lower()
            == str(player_id).replace("-", "").lower()
            and transaction.amount == amount
            and transaction.type == trans_type
            and self._same_reference(transaction.reference_id, reference_id)
            and transaction.wallet_type == wallet_type
        )
        if not matches:
            raise RuntimeError(
                "Transaction idempotency key conflicts with an existing movement"
            )

    async def _load_player_data(self, player_id: UUID):
        result = await self.db.execute(
            select(self.player_data_model)
            .where(self.player_data_model.player_id == player_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def _resolve_ir_set_id(self, reference_id: UUID | str | None) -> UUID | None:
        """Resolve an IR reference to a real backronym set when possible."""

        if reference_id is None:
            return None

        if isinstance(reference_id, str):
            try:
                reference_id = UUID(reference_id)
            except ValueError:
                return None

        from backend.models.ir.backronym_set import BackronymSet

        result = await self.db.execute(
            select(BackronymSet.set_id).where(BackronymSet.set_id == reference_id)
        )
        return result.scalar_one_or_none()

    async def create_transaction(
        self,
        player_id: UUID,
        amount: int,
        trans_type: str,
        reference_id: UUID | None = None,
        auto_commit: bool = True,
        skip_lock: bool = False,  # Kept for compatibility; database constraints are authoritative.
        wallet_type: str = "wallet",
        idempotency_key: str | None = None,
    ) -> TransactionBase:
        """Create a transaction and update player balance atomically."""

        movement_key = idempotency_key or self._build_idempotency_key(
            player_id=player_id,
            amount=amount,
            trans_type=trans_type,
            reference_id=reference_id,
            wallet_type=wallet_type,
        )

        existing = await self.db.execute(
            select(self.transaction_model).where(
                self.transaction_model.idempotency_key == movement_key
            )
        )
        existing_transaction = existing.scalar_one_or_none()
        if existing_transaction:
            self._validate_replay(
                existing_transaction,
                player_id=player_id,
                amount=amount,
                trans_type=trans_type,
                reference_id=reference_id,
                wallet_type=wallet_type,
            )
            return existing_transaction

        async def _create_transaction_impl() -> TransactionBase:
            balance_column = (
                self.player_data_model.vault
                if wallet_type == "vault"
                else self.player_data_model.wallet
            )
            values = {
                "wallet": self.player_data_model.wallet if wallet_type == "vault" else self.player_data_model.wallet + amount,
                "vault": self.player_data_model.vault if wallet_type != "vault" else self.player_data_model.vault + amount,
            }
            stmt = update(self.player_data_model).where(self.player_data_model.player_id == player_id)
            if amount < 0:
                stmt = stmt.where(balance_column + amount >= 0)
            stmt = stmt.values(**values)

            result = await self.db.execute(stmt)
            if result.rowcount != 1:
                player = await self._load_player_data(player_id)
                if not player:
                    raise ValueError(f"Player not found: {player_id}")

                current_balance = player.vault if wallet_type == "vault" else player.wallet
                raise InsufficientBalanceError(
                    f"Insufficient {wallet_type} balance: {current_balance} + {amount} would be negative"
                )

            player = await self._load_player_data(player_id)
            if not player:
                raise ValueError(f"Player not found after update: {player_id}")

            if self._is_ir_ledger():
                set_id = await self._resolve_ir_set_id(reference_id)
                transaction = self.transaction_model(
                    transaction_id=uuid.uuid4(),
                    player_id=player_id,
                    amount=amount,
                    type=trans_type,
                    transaction_type=trans_type,
                    reference_id=reference_id,
                    wallet_type=wallet_type,
                    wallet_balance_after=player.wallet,
                    vault_balance_after=player.vault,
                    vault_contribution=amount if wallet_type == "vault" else 0,
                    entry_id=None,
                    set_id=set_id,
                    idempotency_key=movement_key,
                )
            else:
                transaction = self.transaction_model(
                    transaction_id=uuid.uuid4(),
                    player_id=player_id,
                    amount=amount,
                    type=trans_type,
                    reference_id=reference_id,
                    wallet_type=wallet_type,
                    wallet_balance_after=player.wallet,
                    vault_balance_after=player.vault,
                    idempotency_key=movement_key,
                )

            self.db.add(transaction)
            await self.db.flush()

            logger.info(
                "Transaction created: %s amount=%s type=%s wallet_type=%s new_wallet=%s new_vault=%s",
                player_id,
                amount,
                trans_type,
                wallet_type,
                player.wallet,
                player.vault,
            )
            return transaction

        try:
            async with self.db.begin_nested():
                transaction = await _create_transaction_impl()
        except IntegrityError:
            existing = await self.db.execute(
                select(self.transaction_model).where(
                    self.transaction_model.idempotency_key == movement_key
                )
            )
            existing_transaction = existing.scalar_one_or_none()
            if existing_transaction:
                self._validate_replay(
                    existing_transaction,
                    player_id=player_id,
                    amount=amount,
                    trans_type=trans_type,
                    reference_id=reference_id,
                    wallet_type=wallet_type,
                )
                return existing_transaction
            raise

        if auto_commit:
            await self.db.commit()
            await self.db.refresh(transaction)

        return transaction

    async def debit_wallet(
        self,
        player_id: UUID,
        amount: int,
        transaction_type: str,
        reference_id: UUID | None = None,
        auto_commit: bool = True,
        skip_lock: bool = False,
        wallet_type: str = "wallet",
    ) -> TransactionBase:
        """Debit coins from a wallet or vault."""

        return await self.create_transaction(
            player_id=player_id,
            amount=-abs(amount),
            trans_type=transaction_type,
            reference_id=reference_id,
            auto_commit=auto_commit,
            skip_lock=skip_lock,
            wallet_type=wallet_type,
        )

    async def credit_wallet(
        self,
        player_id: UUID,
        amount: int,
        transaction_type: str,
        reference_id: UUID | None = None,
        auto_commit: bool = True,
        skip_lock: bool = False,
    ) -> TransactionBase:
        """Credit coins to a wallet."""

        return await self.create_transaction(
            player_id=player_id,
            amount=abs(amount),
            trans_type=transaction_type,
            reference_id=reference_id,
            auto_commit=auto_commit,
            skip_lock=skip_lock,
            wallet_type="wallet",
        )

    async def credit_vault(
        self,
        player_id: UUID,
        amount: int,
        transaction_type: str | None = None,
        reference_id: UUID | None = None,
        auto_commit: bool = True,
        skip_lock: bool = False,
    ) -> TransactionBase:
        """Credit coins to a vault."""

        return await self.create_transaction(
            player_id=player_id,
            amount=abs(amount),
            trans_type=transaction_type or self.VAULT_CONTRIBUTION,
            reference_id=reference_id,
            auto_commit=auto_commit,
            skip_lock=skip_lock,
            wallet_type="vault",
        )

    async def process_vote_payout(
        self,
        player_id: UUID,
        amount: int,
        set_id: UUID | None = None,
        auto_commit: bool = True,
    ) -> TransactionBase:
        """Credit an IR vote payout to the player's wallet."""

        return await self.credit_wallet(
            player_id=player_id,
            amount=amount,
            transaction_type=self.VOTE_PAYOUT,
            reference_id=set_id,
            auto_commit=auto_commit,
        )

    async def process_creator_payout(
        self,
        player_id: UUID,
        amount: int,
        set_id: UUID | None = None,
        auto_commit: bool = True,
    ) -> TransactionBase:
        """Credit an IR creator payout to the player's wallet."""

        return await self.credit_wallet(
            player_id=player_id,
            amount=amount,
            transaction_type=self.CREATOR_PAYOUT,
            reference_id=set_id,
            auto_commit=auto_commit,
        )

    async def create_split_payout(
        self,
        player_id: UUID,
        gross_amount: int,
        cost: int,
        trans_type: str,
        reference_id: UUID | None = None,
        auto_commit: bool = True,
        skip_lock: bool = False,  # Compatibility only.
        idempotency_prefix: str | None = None,
    ) -> tuple[TransactionBase | None, TransactionBase | None]:
        """Create payout with a 70/30 wallet/vault split."""

        net_earnings = gross_amount - cost
        if net_earnings <= 0:
            wallet_txn = await self.create_transaction(
                player_id=player_id,
                amount=gross_amount,
                trans_type=trans_type,
                reference_id=reference_id,
                auto_commit=auto_commit,
                skip_lock=True,
                wallet_type="wallet",
                idempotency_key=(
                    f"{idempotency_prefix}:wallet" if idempotency_prefix else None
                ),
            )
            return wallet_txn, None

        vault_amount = int(net_earnings * 0.3)
        wallet_amount = gross_amount - vault_amount

        wallet_txn = await self.create_transaction(
            player_id=player_id,
            amount=wallet_amount,
            trans_type=trans_type,
            reference_id=reference_id,
            auto_commit=False,
            skip_lock=True,
            wallet_type="wallet",
            idempotency_key=(
                f"{idempotency_prefix}:wallet" if idempotency_prefix else None
            ),
        )
        vault_txn = await self.create_transaction(
            player_id=player_id,
            amount=vault_amount,
            trans_type="vault_rake",
            reference_id=reference_id,
            auto_commit=False,
            skip_lock=True,
            wallet_type="vault",
            idempotency_key=(
                f"{idempotency_prefix}:vault" if idempotency_prefix else None
            ),
        )

        if auto_commit:
            await self.db.commit()
            await self.db.refresh(wallet_txn)
            await self.db.refresh(vault_txn)

        logger.info(
            "Split payout created: %s gross=%s cost=%s net=%s wallet=%s vault=%s",
            player_id,
            gross_amount,
            cost,
            net_earnings,
            wallet_amount,
            vault_amount,
        )

        return wallet_txn, vault_txn

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
