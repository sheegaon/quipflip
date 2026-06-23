"""Tests for the activity service."""
import pytest
from datetime import datetime, UTC, timedelta
from uuid import uuid4

from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.services import ActivityService


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

    copy_one = QFPlayer(
        player_id=uuid4(),
        username="copy_one",
        username_canonical="copy_one",
        email="copy_one@example.com",
        password_hash="hash",
        wallet=1000,
        vault=0,
    )
    copy_two = QFPlayer(
        player_id=uuid4(),
        username="copy_two",
        username_canonical="copy_two",
        email="copy_two@example.com",
        password_hash="hash",
        wallet=1000,
        vault=0,
    )
    copy_round_1 = Round(
        round_id=uuid4(),
        player_id=copy_one.player_id,
        round_type="copy",
        status="submitted",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        cost=100,
        prompt_round_id=prompt_round.round_id,
        original_phrase="ICE CREAM",
        copy_phrase="GELATO",
    )
    copy_round_2 = Round(
        round_id=uuid4(),
        player_id=copy_two.player_id,
        round_type="copy",
        status="submitted",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        cost=100,
        prompt_round_id=prompt_round.round_id,
        original_phrase="ICE CREAM",
        copy_phrase="SORBET",
    )
    phraseset_id = uuid4()
    phraseset = Phraseset(
        phraseset_id=phraseset_id,
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy_round_1.round_id,
        copy_round_2_id=copy_round_2.round_id,
        prompt_text=prompt_round.prompt_text,
        original_phrase=prompt_round.submitted_phrase,
        copy_phrase_1=copy_round_1.copy_phrase,
        copy_phrase_2=copy_round_2.copy_phrase,
        status="open",
        vote_count=0,
        created_at=datetime.now(UTC),
        total_pool=200,
    )
    db_session.add_all([copy_one, copy_two, copy_round_1, copy_round_2])
    await db_session.flush()
    db_session.add(phraseset)
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

    await service.attach_phraseset_id(prompt_round.round_id, phraseset_id)
    await db_session.commit()

    timeline = await service.get_phraseset_activity(phraseset_id)
    assert len(timeline) == 1
    assert timeline[0]["phraseset_id"] == str(phraseset_id)
    assert timeline[0]["prompt_round_id"] == str(prompt_round.round_id)
