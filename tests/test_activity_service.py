"""Tests for the activity service."""
import pytest
from datetime import datetime, UTC, timedelta
from uuid import uuid4

from backend.models.player import Player
from backend.models.round import Round
from backend.services.phraseset_activity_service import ActivityService


@pytest.mark.asyncio
async def test_record_and_attach_activity(db_session, player_factory):
    """Activities recorded against prompt rounds should attach to phrasesets."""
    player = await player_factory(username="player_one")
    prompt_round = Round(
        round_id=uuid4(),
        player_id=player.player_id,
        round_type="prompt",
        status="submitted",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        cost=100,
        prompt_text="the best dessert is",
        submitted_phrase="ICE CREAM",
        phraseset_status="waiting_copies",
    )

    db_session.add_all([player, prompt_round])
    await db_session.commit()

    service = ActivityService(db_session)
    activity = await service.record_activity(
        activity_type="prompt_submitted",
        prompt_round_id=prompt_round.round_id,
        player_id=player.player_id,
        metadata={"prompt_text": prompt_round.prompt_text},
    )
    await db_session.commit()

    assert activity.activity_id is not None
    assert activity.phraseset_id is None

    phraseset_id = uuid4()
    await service.attach_phraseset_id(prompt_round.round_id, phraseset_id)
    await db_session.commit()

    timeline = await service.get_phraseset_activity(phraseset_id)
    assert len(timeline) == 1
    assert timeline[0].phraseset_id == phraseset_id
    assert timeline[0].prompt_round_id == prompt_round.round_id
