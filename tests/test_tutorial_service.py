"""Tests for the tutorial service."""
import pytest
from datetime import datetime, UTC

from backend.services.tutorial_service import TutorialService


@pytest.mark.asyncio
async def test_get_tutorial_status_new_player(db_session, player_factory):
    """New players should have tutorial not started."""
    # Use unique username to avoid collision with other tests
    player = await player_factory()

    service = TutorialService(db_session)
    status = await service.get_tutorial_status(player.player_id)

    assert status.tutorial_completed is False
    assert status.tutorial_progress == "not_started"
    assert status.tutorial_started_at is None
    assert status.tutorial_completed_at is None


@pytest.mark.asyncio
async def test_update_tutorial_progress(db_session, player_factory):
    """Updating tutorial progress should set started_at timestamp."""
    # Use unique username to avoid collision with other tests
    player = await player_factory()

    service = TutorialService(db_session)
    status = await service.update_tutorial_progress(player.player_id, "welcome")

    assert status.tutorial_progress == "welcome"
    assert status.tutorial_started_at is not None
    assert status.tutorial_completed is False
    assert status.tutorial_completed_at is None


@pytest.mark.asyncio
async def test_complete_tutorial(db_session, player_factory):
    """Completing tutorial should set completed flag and timestamp."""
    # Use unique username to avoid collision with other tests
    player = await player_factory()

    service = TutorialService(db_session)

    # Start tutorial
    await service.update_tutorial_progress(player.player_id, "welcome")

    # Complete tutorial
    status = await service.update_tutorial_progress(player.player_id, "completed")

    assert status.tutorial_progress == "completed"
    assert status.tutorial_completed is True
    assert status.tutorial_started_at is not None
    assert status.tutorial_completed_at is not None


@pytest.mark.asyncio
async def test_reset_tutorial(db_session, player_factory):
    """Resetting tutorial should clear all tutorial fields."""
    # Use unique username to avoid collision with other tests
    player = await player_factory()

    service = TutorialService(db_session)

    # Complete tutorial
    await service.update_tutorial_progress(player.player_id, "welcome")
    await service.update_tutorial_progress(player.player_id, "completed")

    # Reset it
    status = await service.reset_tutorial(player.player_id)

    assert status.tutorial_completed is False
    assert status.tutorial_progress == "not_started"
    assert status.tutorial_started_at is None
    assert status.tutorial_completed_at is None


@pytest.mark.asyncio
async def test_tutorial_progress_steps(db_session, player_factory):
    """Test multiple progress steps through tutorial."""
    # Use unique username to avoid collision with other tests
    player = await player_factory()

    service = TutorialService(db_session)

    steps = ["welcome", "dashboard", "prompt_round", "copy_round", "vote_round", "completed"]

    for step in steps:
        status = await service.update_tutorial_progress(player.player_id, step)
        assert status.tutorial_progress == step

        # started_at should be set after first step
        if step != "not_started":
            assert status.tutorial_started_at is not None

        # completed should only be true at end
        if step == "completed":
            assert status.tutorial_completed is True
            assert status.tutorial_completed_at is not None
        else:
            assert status.tutorial_completed is False
            assert status.tutorial_completed_at is None
