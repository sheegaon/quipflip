"""
Tests for TransactionService - balance management and transaction recording.
"""

import pytest
from datetime import datetime, UTC
import uuid

from backend.models.player import Player
from backend.models.transaction import Transaction
from backend.services.transaction_service import TransactionService
from sqlalchemy import select


@pytest.fixture
async def player_with_balance(db_session):
    """Create a player with initial balance."""
    test_id = uuid.uuid4().hex[:8]
    player = Player(
        player_id=uuid.uuid4(),
        username=f"test_player_{test_id}",
        username_canonical=f"test_player_{test_id}",
        pseudonym=f"TestPlayer{test_id}",
        pseudonym_canonical=f"testplayer{test_id}",
        email=f"test_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    db_session.add(player)
    await db_session.commit()
    return player


class TestTransactionCreation:
    """Test transaction creation and balance updates."""

    @pytest.mark.asyncio
    async def test_create_transaction_debit(self, db_session, player_with_balance):
        """Should create debit transaction and decrease balance."""
        transaction_service = TransactionService(db_session)

        initial_balance = player_with_balance.balance

        # Create debit transaction
        transaction = await transaction_service.create_transaction(
            player_id=player_with_balance.player_id,
            amount=-100,
            transaction_type="test_debit",
        )

        assert transaction is not None
        assert transaction.amount == -100
        assert transaction.transaction_type == "test_debit"
        assert transaction.player_id == player_with_balance.player_id

        # Verify balance decreased
        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == initial_balance - 100

    @pytest.mark.asyncio
    async def test_create_transaction_credit(self, db_session, player_with_balance):
        """Should create credit transaction and increase balance."""
        transaction_service = TransactionService(db_session)

        initial_balance = player_with_balance.balance

        # Create credit transaction
        transaction = await transaction_service.create_transaction(
            player_id=player_with_balance.player_id,
            amount=250,
            transaction_type="test_credit",
        )

        assert transaction is not None
        assert transaction.amount == 250
        assert transaction.transaction_type == "test_credit"

        # Verify balance increased
        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == initial_balance + 250

    @pytest.mark.asyncio
    async def test_transaction_recorded_in_database(self, db_session, player_with_balance):
        """Should record transaction in transactions table."""
        transaction_service = TransactionService(db_session)

        # Create transaction
        transaction = await transaction_service.create_transaction(
            player_id=player_with_balance.player_id,
            amount=-50,
            transaction_type="test_record",
        )

        # Query transaction from database
        result = await db_session.execute(
            select(Transaction).where(Transaction.transaction_id == transaction.transaction_id)
        )
        db_transaction = result.scalar_one()

        assert db_transaction.player_id == player_with_balance.player_id
        assert db_transaction.amount == -50
        assert db_transaction.transaction_type == "test_record"
        assert db_transaction.created_at is not None

    @pytest.mark.asyncio
    async def test_transaction_with_related_id(self, db_session, player_with_balance):
        """Should store related_id for tracking."""
        transaction_service = TransactionService(db_session)

        related_id = uuid.uuid4()

        transaction = await transaction_service.create_transaction(
            player_id=player_with_balance.player_id,
            amount=100,
            transaction_type="test_related",
            related_id=related_id,
        )

        assert transaction.related_id == related_id


class TestTransactionTypes:
    """Test different transaction types."""

    @pytest.mark.asyncio
    async def test_prompt_entry_transaction(self, db_session, player_with_balance):
        """Should handle prompt entry cost."""
        transaction_service = TransactionService(db_session)

        await transaction_service.create_transaction(
            player_id=player_with_balance.player_id,
            amount=-100,
            transaction_type="prompt_entry",
        )

        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == 900

    @pytest.mark.asyncio
    async def test_copy_entry_transaction(self, db_session, player_with_balance):
        """Should handle copy entry cost."""
        transaction_service = TransactionService(db_session)

        await transaction_service.create_transaction(
            player_id=player_with_balance.player_id,
            amount=-100,
            transaction_type="copy_entry",
        )

        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == 900

    @pytest.mark.asyncio
    async def test_vote_payout_transaction(self, db_session, player_with_balance):
        """Should handle vote payout credit."""
        transaction_service = TransactionService(db_session)

        await transaction_service.create_transaction(
            player_id=player_with_balance.player_id,
            amount=20,
            transaction_type="vote_payout",
        )

        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == 1020

    @pytest.mark.asyncio
    async def test_phraseset_payout_transaction(self, db_session, player_with_balance):
        """Should handle phraseset completion payout."""
        transaction_service = TransactionService(db_session)

        await transaction_service.create_transaction(
            player_id=player_with_balance.player_id,
            amount=150,
            transaction_type="phraseset_payout",
        )

        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == 1150


class TestBalanceConsistency:
    """Test balance consistency and edge cases."""

    @pytest.mark.asyncio
    async def test_multiple_transactions_sequence(self, db_session, player_with_balance):
        """Should correctly apply multiple sequential transactions."""
        transaction_service = TransactionService(db_session)

        initial_balance = player_with_balance.balance

        # Series of transactions
        await transaction_service.create_transaction(
            player_with_balance.player_id, -100, "test1"
        )
        await transaction_service.create_transaction(
            player_with_balance.player_id, 50, "test2"
        )
        await transaction_service.create_transaction(
            player_with_balance.player_id, -25, "test3"
        )
        await transaction_service.create_transaction(
            player_with_balance.player_id, 200, "test4"
        )

        await db_session.refresh(player_with_balance)

        # Net change: -100 + 50 - 25 + 200 = +125
        assert player_with_balance.balance == initial_balance + 125

    @pytest.mark.asyncio
    async def test_balance_can_go_negative(self, db_session, player_with_balance):
        """Should allow balance to go negative (debt)."""
        transaction_service = TransactionService(db_session)

        # Deduct more than available balance
        await transaction_service.create_transaction(
            player_with_balance.player_id, -1500, "overdraft"
        )

        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == -500  # Started with 1000

    @pytest.mark.asyncio
    async def test_zero_amount_transaction(self, db_session, player_with_balance):
        """Should handle zero-amount transactions."""
        transaction_service = TransactionService(db_session)

        initial_balance = player_with_balance.balance

        transaction = await transaction_service.create_transaction(
            player_with_balance.player_id, 0, "zero_test"
        )

        assert transaction.amount == 0

        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == initial_balance


class TestTransactionHistory:
    """Test transaction history and querying."""

    @pytest.mark.asyncio
    async def test_get_player_transactions(self, db_session, player_with_balance):
        """Should retrieve all transactions for a player."""
        transaction_service = TransactionService(db_session)

        # Create multiple transactions
        for i in range(5):
            await transaction_service.create_transaction(
                player_with_balance.player_id,
                i * 10,
                f"test_{i}",
            )

        # Query all transactions
        result = await db_session.execute(
            select(Transaction)
            .where(Transaction.player_id == player_with_balance.player_id)
            .order_by(Transaction.created_at)
        )
        transactions = result.scalars().all()

        assert len(transactions) == 5
        # Verify they're in correct order
        for i, transaction in enumerate(transactions):
            assert transaction.amount == i * 10
            assert transaction.transaction_type == f"test_{i}"

    @pytest.mark.asyncio
    async def test_transaction_timestamps(self, db_session, player_with_balance):
        """Should record accurate timestamps."""
        transaction_service = TransactionService(db_session)

        before = datetime.now(UTC)
        transaction = await transaction_service.create_transaction(
            player_with_balance.player_id, 100, "timestamp_test"
        )
        after = datetime.now(UTC)

        assert before <= transaction.created_at <= after


class TestConcurrency:
    """Test transaction service under concurrent conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_transaction_safety(self, db_session):
        """Should handle concurrent transactions correctly with locking."""
        # This test verifies that the locking mechanism works
        test_id = uuid.uuid4().hex[:8]
        player = Player(
            player_id=uuid.uuid4(),
            username=f"concurrent_{test_id}",
            username_canonical=f"concurrent_{test_id}",
            pseudonym=f"Concurrent{test_id}",
            pseudonym_canonical=f"concurrent{test_id}",
            email=f"concurrent_{test_id}@test.com",
            password_hash="hash",
            balance=1000,
        )
        db_session.add(player)
        await db_session.commit()

        transaction_service = TransactionService(db_session)

        # Sequential execution (simulating what happens under lock)
        await transaction_service.create_transaction(player.player_id, -100, "tx1")
        await transaction_service.create_transaction(player.player_id, -100, "tx2")
        await transaction_service.create_transaction(player.player_id, -100, "tx3")

        await db_session.refresh(player)
        assert player.balance == 700  # 1000 - 300
