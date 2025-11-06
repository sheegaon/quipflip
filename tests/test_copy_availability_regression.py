"""
Regression tests for copy round availability.

These tests ensure that copy rounds are available when there are prompts
waiting in the database, even if the in-memory queue is empty (e.g., after
a server restart).
"""
import pytest
import uuid
from backend.models.prompt import Prompt
from backend.services.round_service import RoundService
from backend.services.transaction_service import TransactionService
from backend.services.player_service import PlayerService


@pytest.mark.asyncio
async def test_copy_available_when_prompts_in_database(db_session, player_factory):
    """
    Test that copy rounds are available when prompts exist in database.

    This is a regression test for the bug where copy rounds showed as unavailable
    even when there were prompts waiting, because the queue was empty after restart.
    """
    # Create two players
    player1 = await player_factory()
    player2 = await player_factory()

    # Services
    round_service = RoundService(db_session)
    transaction_service = TransactionService(db_session)
    player_service = PlayerService(db_session)

    # Disable all existing prompts to ensure we only use our test prompt
    from backend.models.prompt import Prompt as PromptModel
    from sqlalchemy import update
    await db_session.execute(update(PromptModel).values(enabled=False))
    await db_session.commit()

    # Seed a test prompt
    prompt = Prompt(
        text=f"dog food {uuid.uuid4().hex[:8]}",
        category="test",
        enabled=True
    )
    db_session.add(prompt)
    await db_session.commit()

    # Player 1 submits a prompt (must be 2+ words)
    prompt_round = await round_service.start_prompt_round(player1, transaction_service)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id, "big dogs", player1, transaction_service
    )
    await db_session.refresh(player1)

    # Now check if player2 can see copy rounds as available
    # This queries the database directly, not the queue
    available_count = await round_service.get_available_prompts_count(player2.player_id)

    assert available_count >= 1, (
        "Copy rounds should be available when there are prompts in database, "
        "even if the queue is empty"
    )

    # Verify player2 can actually start a copy round
    can_copy, error = await player_service.can_start_copy_round(player2)
    assert can_copy, f"Player should be able to start copy round, error: {error}"

    # Actually start the copy round to verify end-to-end
    copy_round, _ = await round_service.start_copy_round(player2, transaction_service)
    assert copy_round is not None
    assert copy_round.round_type == "copy"
    assert copy_round.original_phrase == "BIG DOGS"


@pytest.mark.asyncio
async def test_copy_not_available_for_own_prompts(db_session, player_factory):
    """
    Test that players cannot copy their own prompts.

    The available count should exclude the player's own prompts.
    """
    player = await player_factory()

    round_service = RoundService(db_session)
    transaction_service = TransactionService(db_session)

    # Disable all existing prompts to ensure we only use our test prompt
    from backend.models.prompt import Prompt as PromptModel
    from sqlalchemy import update
    await db_session.execute(update(PromptModel).values(enabled=False))
    await db_session.commit()

    # Seed a test prompt
    prompt = Prompt(
        text=f"big cats {uuid.uuid4().hex[:8]}",
        category="test",
        enabled=True
    )
    db_session.add(prompt)
    await db_session.commit()

    # Check available count BEFORE submitting own prompt
    available_before_self_submit = await round_service.get_available_prompts_count(player.player_id)

    # Player submits a prompt
    prompt_round = await round_service.start_prompt_round(player, transaction_service)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id, "big lion", player, transaction_service
    )
    await db_session.refresh(player)

    # Check available count AFTER submitting own prompt
    available_after_self_submit = await round_service.get_available_prompts_count(player.player_id)

    # The count should be the same (not increased)
    # because the player's own prompt shouldn't be in their available count
    assert available_after_self_submit == available_before_self_submit, (
        f"Player should not see their own prompts as available for copying. "
        f"Before: {available_before_self_submit}, After: {available_after_self_submit}"
    )


@pytest.mark.asyncio
async def test_copy_not_available_after_already_copied(db_session, player_factory):
    """
    Test that players cannot copy the same prompt twice.

    After a player copies a prompt, it should not appear in their available count.
    """
    player1 = await player_factory()
    player2 = await player_factory()

    round_service = RoundService(db_session)
    transaction_service = TransactionService(db_session)

    # Disable all existing prompts to ensure we only use our test prompt
    from backend.models.prompt import Prompt as PromptModel
    from sqlalchemy import update
    await db_session.execute(update(PromptModel).values(enabled=False))
    await db_session.commit()

    # Seed a test prompt
    prompt = Prompt(
        text=f"big birds {uuid.uuid4().hex[:8]}",
        category="test",
        enabled=True
    )
    db_session.add(prompt)
    await db_session.commit()

    # Player 1 submits a prompt
    prompt_round = await round_service.start_prompt_round(player1, transaction_service)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id, "big crow", player1, transaction_service
    )
    await db_session.refresh(player1)

    # Player 2 copies it
    available_before = await round_service.get_available_prompts_count(player2.player_id)
    assert available_before >= 1

    copy_round, _ = await round_service.start_copy_round(player2, transaction_service)
    await round_service.submit_copy_phrase(
        copy_round.round_id, "big hawk", player2, transaction_service
    )
    await db_session.refresh(player2)

    # Check available count again for player2
    available_after = await round_service.get_available_prompts_count(player2.player_id)

    # If this was the only prompt, count should be 0
    # If there were other prompts, count should be less than before
    assert available_after < available_before or available_after == 0, (
        "Player should not see prompts they've already copied as available"
    )


@pytest.mark.asyncio
async def test_multiple_prompts_available_count(db_session, player_factory):
    """
    Test that the available count correctly reflects multiple prompts from different players.
    """
    player1 = await player_factory()
    player2 = await player_factory()
    player3 = await player_factory()

    round_service = RoundService(db_session)
    transaction_service = TransactionService(db_session)

    # Disable all existing prompts to ensure we only use our test prompts
    from backend.models.prompt import Prompt as PromptModel
    from sqlalchemy import update
    await db_session.execute(update(PromptModel).values(enabled=False))
    await db_session.commit()

    # Seed TWO test prompts (so player1 can submit 2 prompts without seeing same prompt twice)
    # Use prompts with short words (< 4 chars) that can be shared
    prompt1 = Prompt(
        text=f"wet animals {uuid.uuid4().hex[:8]}",
        category="test",
        enabled=True
    )
    prompt2 = Prompt(
        text=f"dry animals {uuid.uuid4().hex[:8]}",
        category="test",
        enabled=True
    )
    db_session.add_all([prompt1, prompt2])
    await db_session.commit()

    # Player 1 submits 2 prompts - use two-word phrases that share "wet" (3 chars, not significant)
    for phrase in ["wet fish", "dry frog"]:
        prompt_round = await round_service.start_prompt_round(player1, transaction_service)
        await round_service.submit_prompt_phrase(
            prompt_round.round_id, phrase, player1, transaction_service
        )
        await db_session.refresh(player1)

    # Player 2 submits 1 prompt
    prompt_round = await round_service.start_prompt_round(player2, transaction_service)
    await round_service.submit_prompt_phrase(
        prompt_round.round_id, "wet toad", player2, transaction_service
    )
    await db_session.refresh(player2)

    # Player 3 should see AT LEAST 3 prompts available (2 from player1, 1 from player2)
    # There might be more from other tests, but we check the minimum
    available_for_player3 = await round_service.get_available_prompts_count(player3.player_id)
    assert available_for_player3 >= 3, f"Expected at least 3 prompts available, got {available_for_player3}"

    # Player 1 should see AT LEAST 1 prompt available (player2's)
    # Their own 2 prompts should not be counted
    available_for_player1 = await round_service.get_available_prompts_count(player1.player_id)
    assert available_for_player1 >= 1, f"Expected at least 1 prompt available, got {available_for_player1}"
    # Verify it's less than player3's count (since player1 can't see their own 2 prompts)
    assert available_for_player1 < available_for_player3, (
        "Player1 should see fewer prompts than Player3 (excluding own prompts)"
    )

    # Player 2 should see AT LEAST 2 prompts available (player1's 2)
    # Their own 1 prompt should not be counted
    available_for_player2 = await round_service.get_available_prompts_count(player2.player_id)
    assert available_for_player2 >= 2, f"Expected at least 2 prompts available, got {available_for_player2}"
    # Verify it's less than player3's count (since player2 can't see their own prompt)
    assert available_for_player2 < available_for_player3, (
        "Player2 should see fewer prompts than Player3 (excluding own prompt)"
    )
