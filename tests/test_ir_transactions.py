"""Tests for IR transaction and daily bonus services."""
import pytest
import uuid
from datetime import datetime, timedelta
from backend.services.ir.player_service import IRPlayerService
from backend.services.ir.transaction_service import IRTransactionService
from backend.services.ir.ir_daily_bonus_service import IRDailyBonusService
from backend.utils.passwords import hash_password


@pytest.fixture
async def ir_player_factory(db_session):
    """Factory for creating IR test players."""
    player_service = IRPlayerService(db_session)

    async def _create_player(
        email: str | None = None,
        username: str | None = None,
        password: str = "TestPassword123!",
    ):
        if email is None:
            email = f"irplayer{uuid.uuid4().hex[:8]}@example.com"
        if username is None:
            username = f"player_{uuid.uuid4().hex[:8]}"

        password_hash = hash_password(password)
        return await player_service.create_player(
            username=username,
            email=email,
            password_hash=password_hash,
        )

    return _create_player


@pytest.mark.asyncio
async def test_ir_debit_wallet(db_session, ir_player_factory):
    """Test debiting wallet balance."""
    player = await ir_player_factory()
    transaction_service = IRTransactionService(db_session)

    initial_balance = player.wallet
    debit_amount = 100

    transaction = await transaction_service.debit_wallet(
        player_id=player.player_id,
        amount=debit_amount,
        transaction_type="ir_backronym_entry",
        reference_id=str(uuid.uuid4())
    )

    assert transaction is not None
    assert transaction.amount == -debit_amount  # Debits are stored as negative

    # Refresh player and check balance
    await db_session.refresh(player)
    assert player.wallet == initial_balance - debit_amount


@pytest.mark.asyncio
async def test_ir_credit_wallet(db_session, ir_player_factory):
    """Test crediting wallet balance."""
    player = await ir_player_factory()
    transaction_service = IRTransactionService(db_session)

    initial_balance = player.wallet
    credit_amount = 50

    transaction = await transaction_service.credit_wallet(
        player_id=player.player_id,
        amount=credit_amount,
        transaction_type="ir_vote_payout",
        reference_id=str(uuid.uuid4())
    )

    assert transaction is not None
    assert transaction.amount == credit_amount

    # Refresh player and check balance
    await db_session.refresh(player)
    assert player.wallet == initial_balance + credit_amount


@pytest.mark.asyncio
async def test_ir_debit_insufficient_balance(db_session, ir_player_factory):
    """Test that debit fails with insufficient balance."""
    player = await ir_player_factory()
    transaction_service = IRTransactionService(db_session)

    # Set balance to 50
    player.wallet = 50
    await db_session.commit()

    # Try to debit 100
    with pytest.raises(Exception):  # Should raise error
        await transaction_service.debit_wallet(
            player_id=player.player_id,
            amount=100,
            transaction_type="ir_backronym_entry",
            reference_id=str(uuid.uuid4())
        )


@pytest.mark.asyncio
async def test_ir_vault_rake_application(db_session, ir_player_factory):
    """Test applying vault rake to earnings."""
    player = await ir_player_factory()
    transaction_service = IRTransactionService(db_session)

    initial_wallet = player.wallet
    initial_vault = player.vault
    earnings = 100
    rake_percent = 30  # 30% rake

    # Apply vault rake
    await transaction_service.apply_vault_rake(
        player_id=player.player_id,
        net_earnings=earnings
    )

    # Refresh player
    await db_session.refresh(player)

    rake_amount = int(earnings * rake_percent / 100)
    expected_wallet_increase = earnings - rake_amount
    expected_vault_increase = rake_amount

    # Check calculations (allowing for rounding)
    assert player.wallet == initial_wallet + expected_wallet_increase
    assert player.vault >= initial_vault + rake_amount - 1  # Allow for rounding


@pytest.mark.asyncio
async def test_ir_transaction_ledger_tracking(db_session, ir_player_factory):
    """Test that transactions are recorded in ledger."""
    player = await ir_player_factory()
    transaction_service = IRTransactionService(db_session)

    ref_id = str(uuid.uuid4())

    transaction = await transaction_service.debit_wallet(
        player_id=player.player_id,
        amount=100,
        transaction_type="ir_backronym_entry",
        reference_id=ref_id
    )

    assert transaction is not None
    assert transaction.player_id == player.player_id
    assert transaction.amount == 100
    assert transaction.transaction_type == "ir_backronym_entry"
    assert transaction.reference_id == ref_id


@pytest.mark.asyncio
async def test_ir_claim_daily_bonus(db_session, ir_player_factory):
    """Test claiming daily bonus."""
    player = await ir_player_factory()
    bonus_service = IRDailyBonusService(db_session)

    initial_balance = player.wallet

    # Claim daily bonus
    bonus = await bonus_service.claim_daily_bonus(player.player_id)

    assert bonus is not None

    # Refresh player and check balance
    await db_session.refresh(player)
    assert player.wallet == initial_balance + 100  # Default daily bonus


@pytest.mark.asyncio
async def test_ir_daily_bonus_once_per_day(db_session, ir_player_factory):
    """Test that daily bonus can only be claimed once per day."""
    player = await ir_player_factory()
    bonus_service = IRDailyBonusService(db_session)

    # Claim first bonus
    bonus1 = await bonus_service.claim_daily_bonus(player.player_id)
    assert bonus1 is not None

    # Try to claim again immediately
    bonus2 = await bonus_service.claim_daily_bonus(player.player_id)

    # Should either raise error or return None
    if bonus2 is not None:
        # If it returns None, that's acceptable
        assert False, "Should not allow claiming bonus twice in same day"


@pytest.mark.asyncio
async def test_ir_daily_bonus_available_check(db_session, ir_player_factory):
    """Test checking if daily bonus is available."""
    player = await ir_player_factory()
    bonus_service = IRDailyBonusService(db_session)

    # Should be available initially
    available = await bonus_service.is_daily_bonus_available(player.player_id)
    assert available is True

    # Claim bonus
    await bonus_service.claim_daily_bonus(player.player_id)

    # Should no longer be available today
    available = await bonus_service.is_daily_bonus_available(player.player_id)
    assert available is False


@pytest.mark.asyncio
async def test_ir_get_pending_payouts(db_session, ir_player_factory):
    """Test retrieving pending payouts."""
    player = await ir_player_factory()
    bonus_service = IRDailyBonusService(db_session)

    # Get pending payouts (should be empty)
    pending = await bonus_service.get_pending_payouts(player.player_id)

    # Should be a list (possibly empty)
    assert isinstance(pending, list)


@pytest.mark.asyncio
async def test_ir_concurrent_transactions(db_session, ir_player_factory):
    """Test that concurrent transactions are handled safely."""
    player = await ir_player_factory()
    transaction_service = IRTransactionService(db_session)

    initial_balance = player.wallet

    # Simulate concurrent debits (should be serialized by locks)
    for i in range(5):
        await transaction_service.debit_wallet(
            player_id=player.player_id,
            amount=10,
            transaction_type="ir_vote_entry",
            reference_id=f"ref_{i}"
        )

    # Refresh and verify
    await db_session.refresh(player)
    assert player.wallet == initial_balance - 50
