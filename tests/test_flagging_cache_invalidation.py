"""Test cache invalidation when flagging prompts to ensure dashboard shows accurate counts."""
import pytest
from backend.services import GameType, QFRoundService
from backend.services import TransactionService
from backend.services import QFPlayerService
from backend.utils.cache import dashboard_cache
from backend.config import get_settings


@pytest.mark.asyncio
async def test_prompts_waiting_count_after_flagging(db_session, player_factory):
    """
    Test that prompts_waiting count is accurate after flagging a prompt.

    Scenario:
    1. Player A creates a prompt
    2. Player B checks dashboard - sees 1 prompt waiting
    3. Player B starts copy round with that prompt
    4. Player B flags the prompt
    5. Player B checks dashboard again - should see 0 prompts waiting (not stale cached value)
    """
    settings = get_settings()

    # Create two players
    player_a = await player_factory()
    player_a.balance = 1000
    player_b = await player_factory()
    player_b.balance = 1000
    await db_session.commit()

    # Seed test prompts
    from backend.models.qf.prompt import Prompt
    import uuid
    prompts = [
        Prompt(prompt_id=uuid.uuid4(), text="A FEELING GOOD", category="test", enabled=True),
        Prompt(prompt_id=uuid.uuid4(), text="SOMETHING WILD", category="test", enabled=True),
    ]
    for p in prompts:
        db_session.add(p)
    await db_session.commit()

    # Services
    round_service = QFRoundService(db_session)
    transaction_service_a = TransactionService(db_session, GameType.QF)
    transaction_service_b = TransactionService(db_session, GameType.QF)

    # Clear cache to start fresh
    dashboard_cache.clear()

    # Player A creates a prompt
    prompt_round = await round_service.start_prompt_round(player_a, transaction_service_a)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id,
        "TEST PHRASE",
        player_a,
        transaction_service_a,
    )
    await db_session.refresh(player_a)

    # Player B checks available prompts - should see 1
    prompts_waiting_before = await round_service.get_available_prompts_count(player_b.player_id)
    assert prompts_waiting_before == 1, f"Expected 1 prompt waiting, got {prompts_waiting_before}"

    # Player B starts a copy round with this prompt
    copy_round, _ = await round_service.start_copy_round(player_b, transaction_service_b)
    await db_session.refresh(player_b)

    # Verify it's the prompt we expect
    assert copy_round.prompt_round_id == prompt_round.round_id

    # Player B flags the prompt
    await round_service.flag_copy_round(
        copy_round.round_id,
        player_b,
        transaction_service_b,
    )
    await db_session.refresh(player_b)
    await db_session.refresh(prompt_round)

    # Verify the prompt is flagged
    assert prompt_round.phraseset_status == "flagged_pending"

    # CRITICAL: Now check if Player B sees the correct count
    # The prompt should NOT be available anymore
    prompts_waiting_after = await round_service.get_available_prompts_count(player_b.player_id)
    assert prompts_waiting_after == 0, (
        f"Expected 0 prompts waiting after flagging, got {prompts_waiting_after}. "
        "This indicates stale cache or incorrect count logic."
    )

    # Also verify that the dashboard cache was invalidated for both players
    # (This is done by trying to get cached dashboard data - should be None)
    cache_key_a = f"dashboard:{player_a.player_id}"
    cache_key_b = f"dashboard:{player_b.player_id}"

    cached_a = dashboard_cache.get(cache_key_a)
    cached_b = dashboard_cache.get(cache_key_b)

    assert cached_a is None, "Player A's dashboard cache should be invalidated after their prompt was flagged"
    assert cached_b is None, "Player B's dashboard cache should be invalidated after flagging"


@pytest.mark.asyncio
async def test_dashboard_endpoint_shows_correct_count_after_flagging(
    db_session, player_factory
):
    """
    Test that the /player/dashboard endpoint returns correct prompts_waiting count after flagging.

    This simulates the exact flow the frontend uses.
    """
    settings = get_settings()

    # Create two players
    player_a = await player_factory()
    player_a.balance = 1000
    player_b = await player_factory()
    player_b.balance = 1000
    await db_session.commit()

    # Seed test prompts
    from backend.models.qf.prompt import Prompt
    import uuid
    prompts = [
        Prompt(prompt_id=uuid.uuid4(), text="TEST PROMPT ONE", category="test", enabled=True),
        Prompt(prompt_id=uuid.uuid4(), text="TEST PROMPT TWO", category="test", enabled=True),
    ]
    for p in prompts:
        db_session.add(p)
    await db_session.commit()

    # Services
    round_service = QFRoundService(db_session)
    transaction_service_a = TransactionService(db_session, GameType.QF)
    transaction_service_b = TransactionService(db_session, GameType.QF)
    player_service = QFPlayerService(db_session)

    # Clear cache
    dashboard_cache.clear()

    # Player A creates a prompt
    prompt_round = await round_service.start_prompt_round(player_a, transaction_service_a)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id,
        "VALID PHRASE",
        player_a,
        transaction_service_a,
    )
    await db_session.refresh(player_a)

    # Player B gets dashboard data (simulating the GET /player/dashboard call)
    await round_service.ensure_prompt_queue_populated()
    prompts_waiting_before = await round_service.get_available_prompts_count(player_b.player_id)

    can_copy_before, _ = await player_service.can_start_copy_round(player_b)

    assert prompts_waiting_before >= 1, "Should have at least 1 prompt waiting"
    assert can_copy_before is True, "Player B should be able to start a copy round"

    # Player B starts and flags the copy round
    copy_round, _ = await round_service.start_copy_round(player_b, transaction_service_b)
    await db_session.refresh(player_b)

    await round_service.flag_copy_round(
        copy_round.round_id,
        player_b,
        transaction_service_b,
    )
    await db_session.refresh(player_b)

    # Now Player B gets fresh dashboard data
    # Note: flag_copy_round should automatically invalidate the cache
    await round_service.ensure_prompt_queue_populated()
    prompts_waiting_after = await round_service.get_available_prompts_count(player_b.player_id)

    # The flagged prompt should be excluded from the count
    assert prompts_waiting_after < prompts_waiting_before, (
        f"Expected prompts_waiting to decrease after flagging. "
        f"Before: {prompts_waiting_before}, After: {prompts_waiting_after}"
    )


@pytest.mark.asyncio
async def test_abandoned_prompt_not_counted_in_available(db_session, player_factory):
    """
    Test that abandoned prompts within 24h cooldown are excluded from available count.

    This is the root cause of the bug where dashboard shows prompts_waiting > 0
    but starting a copy round fails with no_prompts_available.
    """
    from backend.models.qf.prompt import Prompt
    from backend.models.qf.player_abandoned_prompt import PlayerAbandonedPrompt
    from datetime import datetime, UTC
    import uuid

    settings = get_settings()

    # Create two players
    player_a = await player_factory()
    player_a.balance = 1000
    player_b = await player_factory()
    player_b.balance = 1000
    await db_session.commit()

    # Seed test prompt
    prompt = Prompt(prompt_id=uuid.uuid4(), text="ABANDONABLE", category="test", enabled=True)
    db_session.add(prompt)
    await db_session.commit()

    # Services
    round_service = QFRoundService(db_session)
    transaction_service_a = TransactionService(db_session, GameType.QF)
    transaction_service_b = TransactionService(db_session, GameType.QF)

    # Player A creates a prompt
    prompt_round = await round_service.start_prompt_round(player_a, transaction_service_a)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id,
        "TOTALLY DIFFERENT",
        player_a,
        transaction_service_a,
    )
    await db_session.refresh(player_a)

    # Player B checks available - should see 1
    count_before = await round_service.get_available_prompts_count(player_b.player_id)
    assert count_before == 1, f"Expected 1 available prompt, got {count_before}"

    # Player B starts and immediately abandons the copy round
    copy_round, _ = await round_service.start_copy_round(player_b, transaction_service_b)
    await db_session.refresh(player_b)

    # Abandon the round (this creates a 24h cooldown)
    abandoned_round, refund, penalty = await round_service.abandon_round(
        copy_round.round_id,
        player_b,
        transaction_service_b,
    )
    await db_session.refresh(player_b)

    # CRITICAL: Now check if Player B sees the correct count
    # The abandoned prompt should NOT be available for 24 hours
    count_after = await round_service.get_available_prompts_count(player_b.player_id)
    assert count_after == 0, (
        f"Expected 0 prompts available after abandoning (24h cooldown), got {count_after}. "
        "This is the exact bug - dashboard shows prompts_waiting but can't start copy round!"
    )

    # Verify the cooldown entry was created
    from sqlalchemy import select

    result = await db_session.execute(
        select(PlayerAbandonedPrompt).where(
            PlayerAbandonedPrompt.player_id == player_b.player_id
        )
    )
    cooldown_entry = result.scalar_one_or_none()
    assert cooldown_entry is not None, "Cooldown entry should exist in player_abandoned_prompts"
    assert cooldown_entry.prompt_round_id == prompt_round.round_id

    # Verify that trying to start another copy round will fail
    from backend.utils.exceptions import NoPromptsAvailableError

    with pytest.raises(NoPromptsAvailableError):
        await round_service.start_copy_round(player_b, transaction_service_b)
