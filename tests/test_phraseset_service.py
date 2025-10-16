"""Tests for phraseset service functionality."""
import pytest
from datetime import datetime, UTC, timedelta
from uuid import uuid4

from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import PhraseSet
from backend.models.vote import Vote
from backend.services.phraseset_service import PhrasesetService


def _base_player(username: str) -> Player:
    now = datetime.now(UTC)
    return Player(
        player_id=uuid4(),
        api_key=str(uuid4()),
        username=username,
        username_canonical=username,
        balance=1000,
        created_at=now,
    )


def _copy_round(player_id, prompt_round_id, phrase):
    now = datetime.now(UTC)
    return Round(
        round_id=uuid4(),
        player_id=player_id,
        round_type="copy",
        status="submitted",
        created_at=now,
        expires_at=now + timedelta(minutes=5),
        cost=100,
        prompt_round_id=prompt_round_id,
        copy_phrase=phrase,
        original_phrase="ORIGINAL",
    )


@pytest.mark.asyncio
async def test_get_phrasesets_and_claim(db_session):
    prompt_player = _base_player("prompt_master")
    copy_one = _base_player("copy_cat_one")
    copy_two = _base_player("copy_cat_two")

    now = datetime.now(UTC)
    prompt_round = Round(
        round_id=uuid4(),
        player_id=prompt_player.player_id,
        round_type="prompt",
        status="submitted",
        created_at=now,
        expires_at=now + timedelta(minutes=5),
        cost=100,
        prompt_text="the secret to joy is",
        submitted_phrase="KINDNESS",
        phraseset_status="finalized",
        copy1_player_id=copy_one.player_id,
        copy2_player_id=copy_two.player_id,
    )

    copy_round_1 = _copy_round(copy_one.player_id, prompt_round.round_id, "COMPASSION")
    copy_round_2 = _copy_round(copy_two.player_id, prompt_round.round_id, "GENEROSITY")

    phraseset_id = uuid4()
    phraseset = PhraseSet(
        phraseset_id=phraseset_id,
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy_round_1.round_id,
        copy_round_2_id=copy_round_2.round_id,
        prompt_text=prompt_round.prompt_text,
        original_phrase=prompt_round.submitted_phrase,
        copy_phrase_1=copy_round_1.copy_phrase,
        copy_phrase_2=copy_round_2.copy_phrase,
        status="finalized",
        vote_count=4,
        third_vote_at=now + timedelta(minutes=1),
        fifth_vote_at=now + timedelta(minutes=2),
        closes_at=now + timedelta(minutes=3),
        created_at=now,
        finalized_at=now + timedelta(minutes=4),
        total_pool=300,
    )

    voters = [
        _base_player(f"voter_{index}") for index in range(4)
    ]

    votes = [
        Vote(
            vote_id=uuid4(),
            phraseset_id=phraseset_id,
            player_id=voters[0].player_id,
            voted_phrase="KINDNESS",
            correct=True,
            payout=5,
            created_at=now + timedelta(minutes=1),
        ),
        Vote(
            vote_id=uuid4(),
            phraseset_id=phraseset_id,
            player_id=voters[1].player_id,
            voted_phrase="COMPASSION",
            correct=False,
            payout=0,
            created_at=now + timedelta(minutes=1, seconds=30),
        ),
        Vote(
            vote_id=uuid4(),
            phraseset_id=phraseset_id,
            player_id=voters[2].player_id,
            voted_phrase="GENEROSITY",
            correct=False,
            payout=0,
            created_at=now + timedelta(minutes=2),
        ),
        Vote(
            vote_id=uuid4(),
            phraseset_id=phraseset_id,
            player_id=voters[3].player_id,
            voted_phrase="COMPASSION",
            correct=False,
            payout=0,
            created_at=now + timedelta(minutes=2, seconds=15),
        ),
    ]

    db_session.add_all([
        prompt_player,
        copy_one,
        copy_two,
        *voters,
        prompt_round,
        copy_round_1,
        copy_round_2,
        phraseset,
        *votes,
    ])
    await db_session.commit()

    service = PhrasesetService(db_session)

    summaries, total = await service.get_player_phrasesets(prompt_player.player_id)
    assert total == 1
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["status"] == "finalized"
    assert summary["your_role"] == "prompt"
    assert summary["payout_claimed"] is False or summary["payout_claimed"] is None

    details = await service.get_phraseset_details(phraseset_id, prompt_player.player_id)
    assert details["payout_claimed"] is False
    assert details["your_role"] == "prompt"
    assert details["your_phrase"] == "KINDNESS"

    claim = await service.claim_prize(phraseset_id, prompt_player.player_id)
    assert claim["success"] is True
    assert claim["already_claimed"] is False

    # Second claim should be idempotent
    claim_again = await service.claim_prize(phraseset_id, prompt_player.player_id)
    assert claim_again["already_claimed"] is True

    unclaimed = await service.get_unclaimed_results(prompt_player.player_id)
    assert all(item["phraseset_id"] != phraseset_id for item in unclaimed["unclaimed"])
