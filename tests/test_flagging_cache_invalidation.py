"""Test cache invalidation when flagging prompts to ensure dashboard shows accurate counts."""
import pytest
from uuid import UUID
from backend.services.round_service import RoundService
from backend.services.transaction_service import TransactionService
from backend.services.player_service import PlayerService
from backend.services.vote_service import VoteService
from backend.services.queue_service import QueueService
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
    from backend.models.prompt import Prompt
    import uuid
    prompts = [
        Prompt(prompt_id=uuid.uuid4(), text="A FEELING GOOD", category="test", enabled=True),
        Prompt(prompt_id=uuid.uuid4(), text="SOMETHING WILD", category="test", enabled=True),
    ]
    for p in prompts:
        db_session.add(p)
    await db_session.commit()

    # Services
    round_service = RoundService(db_session)
    transaction_service_a = TransactionService(db_session)
    transaction_service_b = TransactionService(db_session)
    player_service = PlayerService(db_session)
    vote_service = VoteService(db_session)

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
    copy_round = await round_service.start_copy_round(player_b, transaction_service_b)
    await db_session.refresh(player_b)

    # Verify it's the prompt we expect
    assert copy_round.prompt_round_id == prompt_round.round_id

    # Player B flags the prompt
    flag = await round_service.flag_copy_round(
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
    from backend.models.prompt import Prompt
    import uuid
    prompts = [
        Prompt(prompt_id=uuid.uuid4(), text="TEST PROMPT ONE", category="test", enabled=True),
        Prompt(prompt_id=uuid.uuid4(), text="TEST PROMPT TWO", category="test", enabled=True),
    ]
    for p in prompts:
        db_session.add(p)
    await db_session.commit()

    # Services
    round_service = RoundService(db_session)
    transaction_service_a = TransactionService(db_session)
    transaction_service_b = TransactionService(db_session)
    player_service = PlayerService(db_session)
    vote_service = VoteService(db_session)

    # Clear cache
    dashboard_cache.clear()

    # Player A creates a prompt
    prompt_round = await round_service.start_prompt_round(player_a, transaction_service_a)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id,
        "ANOTHER TEST",
        player_a,
        transaction_service_a,
    )
    await db_session.refresh(player_a)

    # Player B gets dashboard data (simulating the GET /player/dashboard call)
    await round_service.ensure_prompt_queue_populated()
    prompts_waiting_before = await round_service.get_available_prompts_count(player_b.player_id)
    phrasesets_waiting_before = await vote_service.count_available_phrasesets_for_player(player_b.player_id)

    can_copy_before, _ = await player_service.can_start_copy_round(player_b)

    assert prompts_waiting_before >= 1, "Should have at least 1 prompt waiting"
    assert can_copy_before is True, "Player B should be able to start a copy round"

    # Player B starts and flags the copy round
    copy_round = await round_service.start_copy_round(player_b, transaction_service_b)
    await db_session.refresh(player_b)

    flag = await round_service.flag_copy_round(
        copy_round.round_id,
        player_b,
        transaction_service_b,
    )
    await db_session.refresh(player_b)

    # IMPORTANT: Clear the cache (simulating what should happen automatically)
    # In production, flag_copy_round should invalidate the cache
    # If this test fails without this line, it means cache invalidation isn't working

    # Now Player B gets fresh dashboard data
    await round_service.ensure_prompt_queue_populated()
    prompts_waiting_after = await round_service.get_available_prompts_count(player_b.player_id)

    # The flagged prompt should be excluded from the count
    assert prompts_waiting_after < prompts_waiting_before, (
        f"Expected prompts_waiting to decrease after flagging. "
        f"Before: {prompts_waiting_before}, After: {prompts_waiting_after}"
    )

    # If there was only 1 prompt and we flagged it, count should be 0
    # (or less by 1 if there were multiple prompts)
