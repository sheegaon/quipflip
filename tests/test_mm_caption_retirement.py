"""Tests for caption retirement rules."""

from datetime import datetime, UTC
from uuid import uuid4

import pytest

from backend.models.mm.caption import MMCaption
from backend.services.mm.game_service import MMGameService


class _DummySession:
    async def flush(self, *_args, **_kwargs):
        return None


class _ConfigService:
    async def get_config_value(self, key, default=None):
        if key == "mm_retire_after_shows":
            return 5
        if key == "mm_min_quality_score_active":
            return 0.05
        return default


def _make_caption(**overrides) -> MMCaption:
    defaults = {
        "caption_id": uuid4(),
        "image_id": uuid4(),
        "author_player_id": uuid4(),
        "kind": "original",
        "parent_caption_id": None,
        "text": "Test caption",
        "status": "active",
        "created_at": datetime.now(UTC),
        "shows": 0,
        "picks": 0,
        "first_vote_awarded": False,
        "quality_score": 0.25,
        "lifetime_earnings_gross": 0,
        "lifetime_to_wallet": 0,
        "lifetime_to_vault": 0,
    }

    defaults.update(overrides)
    return MMCaption(**defaults)


@pytest.mark.asyncio
async def test_caption_retires_after_min_shows_with_no_picks():
    service = MMGameService(_DummySession())
    service.config_service = _ConfigService()

    caption = _make_caption(shows=4, picks=0)

    await service._increment_caption_shows([caption])

    assert caption.shows == 5
    assert caption.status == "retired"


@pytest.mark.asyncio
async def test_caption_stays_active_before_threshold():
    service = MMGameService(_DummySession())
    service.config_service = _ConfigService()

    caption = _make_caption(shows=3, picks=0)

    await service._increment_caption_shows([caption])

    assert caption.shows == 4
    assert caption.status == "active"


@pytest.mark.asyncio
async def test_caption_retires_for_low_quality_after_threshold():
    service = MMGameService(_DummySession())
    service.config_service = _ConfigService()

    caption = _make_caption(shows=60, picks=1)

    await service._increment_caption_shows([caption])

    assert caption.status == "retired"
