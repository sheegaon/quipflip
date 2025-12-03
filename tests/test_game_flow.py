"""Tests for complete game flow."""
import pytest
import uuid
from sqlalchemy import select

from backend.config import get_settings
from backend.models.qf.prompt import Prompt
from backend.models.qf.player_data import QFPlayerData
from backend.services import QFRoundService
from backend.services import TransactionService
from backend.utils.model_registry import GameType


@pytest.mark.asyncio
async def test_prompt_round_lifecycle(db_session, player_factory):
    """Test prompt round from start to submission."""
    # Create player and services
    round_service = QFRoundService(db_session)
    transaction_service = TransactionService(db_session, GameType.QF)

    player = await player_factory()

    # Disable existing prompts and seed a test prompt
    from backend.models.qf.prompt import Prompt as PromptModel
    from sqlalchemy import update
    await db_session.execute(update(PromptModel).values(enabled=False))
    await db_session.commit()

    prompt = Prompt(
        text=f"big cats {uuid.uuid4().hex[:8]}",
        category="test",
        enabled=True
    )
    db_session.add(prompt)
    await db_session.commit()

    # Start prompt round
    round = await round_service.start_prompt_round(player, transaction_service)

    assert round.round_type == "prompt"
    assert round.status == "active"
    assert round.cost == 100

    # Verify the persisted wallet balance reflects the prompt cost deduction
    settings = get_settings()
    qf_player_data = (
        await db_session.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
    ).scalar_one()
    assert qf_player_data.wallet == settings.qf_starting_wallet - settings.prompt_cost

    # Submit word (minimum 4 characters)
    round = await round_service.submit_prompt_phrase(
        round.round_id, "big lion", player, transaction_service
    )

    assert round.status == "submitted"
    assert round.submitted_phrase == "BIG LION"


@pytest.mark.asyncio
async def test_one_round_at_a_time_enforcement(db_session, player_factory):
    """Test player can only have one active round."""
    from backend.services import QFPlayerService

    player_service = QFPlayerService(db_session)
    round_service = QFRoundService(db_session)
    transaction_service = TransactionService(db_session, GameType.QF)

    player = await player_factory()

    # Seed prompt
    prompt = Prompt(text="test", category="test", enabled=True)
    db_session.add(prompt)
    await db_session.commit()

    # Start first round
    prompt_round = await round_service.start_prompt_round(player, transaction_service)

    # Persist active round on the player's game data so subsequent checks respect it
    qf_player_data = (
        await db_session.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
    ).scalar_one()
    qf_player_data.active_round_id = prompt_round.round_id
    await db_session.commit()

    # Try to start second round
    can_start, reason = await player_service.can_start_prompt_round(player)
    assert can_start is False
    assert reason == "already_in_round"


@pytest.mark.asyncio
async def test_insufficient_balance_prevention(db_session, player_factory):
    """Test player cannot start round without sufficient balance."""
    from backend.services import QFPlayerService

    player_service = QFPlayerService(db_session)
    player = await player_factory()

    # Set wallet to $50 (insufficient for $100 prompt) on the persisted player data
    result = await db_session.execute(
        select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
    )
    player_data = result.scalar_one()
    player_data.wallet = 50
    player_data.vault = 0  # Ensure vault is also set to 0 for total balance of $50
    await db_session.commit()

    can_start, reason = await player_service.can_start_prompt_round(player)
    assert can_start is False
    assert reason == "insufficient_balance"


@pytest.mark.asyncio
async def test_transaction_ledger_tracking(db_session, player_factory):
    """Test all transactions are recorded with wallet_balance_after."""
    round_service = QFRoundService(db_session)
    transaction_service = TransactionService(db_session, GameType.QF)

    player = await player_factory()

    # Seed prompt with unique text
    prompt = Prompt(text=f"test ledger {uuid.uuid4()}", category="test", enabled=True)
    db_session.add(prompt)
    await db_session.commit()

    # Start round (should create transaction)
    await round_service.start_prompt_round(player, transaction_service)

    # Check transaction exists
    from sqlalchemy import select
    from backend.models.qf.transaction import QFTransaction
    result = await db_session.execute(
        select(QFTransaction).where(QFTransaction.player_id == player.player_id)
    )
    transactions = result.scalars().all()

    assert len(transactions) == 1
    assert transactions[0].amount == -100
    assert transactions[0].type == "prompt_entry"
    assert transactions[0].wallet_balance_after == 4900


@pytest.mark.asyncio
async def test_daily_bonus_logic(db_session, player_factory):
    """Test daily bonus availability and claiming."""
    from datetime import date, timedelta, datetime, UTC
    from backend.services import QFPlayerService

    player_service = QFPlayerService(db_session)
    transaction_service = TransactionService(db_session, GameType.QF)

    # Test 1: Bonus not available on creation day
    player1 = await player_factory()
    available = await player_service.is_daily_bonus_available(player1)
    assert available is False, "Bonus should not be available on creation day"

    # Test 2: Bonus available for player created yesterday with old last_login_date
    yesterday = date.today() - timedelta(days=1)
    yesterday_dt = datetime.combine(yesterday, datetime.min.time()).replace(tzinfo=UTC)

    player2 = await player_factory(username="test_daily_bonus", email="test_daily_bonus@example.com")

    # Update persisted fields to simulate an existing user created yesterday
    player2.created_at = yesterday_dt
    player2.last_login_date = yesterday_dt
    qf_player_data = (
        await db_session.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player2.player_id)
        )
    ).scalar_one()
    qf_player_data.wallet = 1000
    qf_player_data.vault = 0
    await db_session.commit()
    await db_session.refresh(player2)

    available = await player_service.is_daily_bonus_available(player2)
    assert available is True, "Bonus should be available for player created yesterday"

    # Test 3: Claim bonus
    amount = await player_service.claim_daily_bonus(player2, transaction_service)
    assert amount == 100
    qf_player_data = (
        await db_session.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player2.player_id)
        )
    ).scalar_one()
    assert qf_player_data.balance == 1100

    # Test 4: Bonus no longer available after claiming (last_login_date set to today)
    available = await player_service.is_daily_bonus_available(player2)
    assert available is False, "Bonus should not be available after claiming today"


@pytest.mark.asyncio
async def test_cannot_copy_own_prompt(db_session, player_factory):
    """Test that players cannot copy their own prompts."""
    from backend.services import QFQueueService

    round_service = QFRoundService(db_session)
    transaction_service = TransactionService(db_session, GameType.QF)

    player = await player_factory()

    # Disable existing prompts and seed a test prompt
    from backend.models.qf.prompt import Prompt as PromptModel
    from sqlalchemy import update
    await db_session.execute(update(PromptModel).values(enabled=False))
    await db_session.commit()

    prompt = Prompt(
        text=f"big cats {uuid.uuid4().hex[:8]}",
        category="test",
        enabled=True
    )
    db_session.add(prompt)
    await db_session.commit()

    # Start and submit prompt round (minimum 4 characters)
    prompt_round = await round_service.start_prompt_round(player, transaction_service)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id, "big lion", player, transaction_service
    )
    await db_session.refresh(player)

    # Prompt should now be in queue
    prompts_before = QFQueueService.get_prompt_rounds_waiting()
    assert prompts_before >= 1

    qf_player_data = (
        await db_session.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
    ).scalar_one()
    initial_balance = qf_player_data.balance

    # Try to start copy round with same player - should not give them their own prompt
    try:
        copy_round, _ = await round_service.start_copy_round(player, transaction_service)
    except ValueError:
        # Acceptable outcome: system refused to start a copy round with only own prompt available
        qf_player_data = (
            await db_session.execute(
                select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
            )
        ).scalar_one()
        assert qf_player_data.balance == initial_balance
        return

    assert copy_round.prompt_round_id != prompt_round.round_id

    qf_player_data = (
        await db_session.execute(
            select(QFPlayerData).where(QFPlayerData.player_id == player.player_id)
        )
    ).scalar_one()
    assert qf_player_data.balance == initial_balance - copy_round.cost
