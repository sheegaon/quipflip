"""Tests for guest-specific gameplay restrictions."""

from datetime import datetime, timedelta, UTC

import pytest

from backend.config import get_settings
from backend.services.player_service import PlayerService
from backend.services.vote_service import VoteService

settings = get_settings()


@pytest.mark.asyncio
async def test_guest_prompt_limit_enforced(player_factory, db_session, monkeypatch):
    """Guests should be limited to the configured outstanding prompt count."""

    player = await player_factory()
    player.is_guest = True
    await db_session.commit()

    service = PlayerService(db_session)

    async def fake_count(_: object) -> int:
        return settings.guest_max_outstanding_quips

    monkeypatch.setattr(service, "get_outstanding_prompts_count", fake_count)

    can_start, error = await service.can_start_prompt_round(player)
    assert can_start is False
    assert error == "max_outstanding_quips"

    async def below_limit(_: object) -> int:
        return settings.guest_max_outstanding_quips - 1

    monkeypatch.setattr(service, "get_outstanding_prompts_count", below_limit)

    can_start, error = await service.can_start_prompt_round(player)
    assert can_start is True
    assert error == ""


@pytest.mark.asyncio
async def test_guest_vote_lockout_after_incorrect_streak(player_factory, db_session):
    """Guests should be locked out after the configured number of incorrect votes."""

    player = await player_factory()
    player.is_guest = True
    await db_session.commit()

    vote_service = VoteService(db_session)

    for _ in range(settings.guest_vote_incorrect_streak_limit):
        vote_service._update_guest_vote_state(player, correct=False)

    await db_session.flush()

    assert player.guest_vote_locked_until is not None
    assert player.guest_vote_locked_until > datetime.now(UTC)
    assert player.guest_incorrect_vote_streak == 0

    player_service = PlayerService(db_session)
    can_vote, error = await player_service.can_start_vote_round(player)
    assert can_vote is False
    assert error == "guest_vote_locked"


@pytest.mark.asyncio
async def test_guest_vote_streak_resets_on_correct_vote(player_factory, db_session):
    """A correct vote should reset guest streaks and clear any lock."""

    player = await player_factory()
    player.is_guest = True
    player.guest_incorrect_vote_streak = settings.guest_vote_incorrect_streak_limit - 1
    player.guest_vote_locked_until = datetime.now(UTC) + timedelta(hours=1)
    await db_session.commit()

    vote_service = VoteService(db_session)
    vote_service._update_guest_vote_state(player, correct=True)

    await db_session.flush()

    assert player.guest_incorrect_vote_streak == 0
    assert player.guest_vote_locked_until is None
