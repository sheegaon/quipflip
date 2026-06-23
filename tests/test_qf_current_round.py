"""Tests for QuipFlip current-round projection behavior."""

import uuid
from datetime import datetime, UTC, timedelta

import pytest
from sqlalchemy import select

from backend.models.qf.player_data import QFPlayerData
from backend.models.qf.prompt import Prompt
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.vote_choice import QFVoteChoice
from backend.routers.qf.player import _get_current_round
from backend.services import QFPlayerService
from backend.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
async def test_vote_round_choice_order_is_stable(db_session):
    """Vote choices should be persisted and reused across reconnects."""

    player_service = QFPlayerService(db_session)
    prompter = await player_service.create_player(
        username=f"prompt_user_{uuid.uuid4().hex[:8]}",
        email=f"prompt_user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    copier_one = await player_service.create_player(
        username=f"copy_user1_{uuid.uuid4().hex[:8]}",
        email=f"copy_user1_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    copier_two = await player_service.create_player(
        username=f"copy_user2_{uuid.uuid4().hex[:8]}",
        email=f"copy_user2_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    player = await player_service.create_player(
        username=f"vote_user_{uuid.uuid4().hex[:8]}",
        email=f"vote_user_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    prompt = Prompt(
        prompt_id=uuid.uuid4(),
        text=f"Vote prompt {uuid.uuid4().hex[:6]}",
        category="fun",
        enabled=True,
    )
    db_session.add(prompt)
    await db_session.flush()

    prompt_round = Round(
        round_id=uuid.uuid4(),
        player_id=prompter.player_id,
        round_type="prompt",
        status="submitted",
        prompt_id=prompt.prompt_id,
        prompt_text=prompt.text,
        submitted_phrase="ORIGINAL",
        cost=settings.prompt_cost,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    copy_round_1 = Round(
        round_id=uuid.uuid4(),
        player_id=copier_one.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        original_phrase="ORIGINAL",
        copy_phrase="COPY ONE",
        cost=settings.copy_cost_normal,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    copy_round_2 = Round(
        round_id=uuid.uuid4(),
        player_id=copier_two.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        original_phrase="ORIGINAL",
        copy_phrase="COPY TWO",
        cost=settings.copy_cost_normal,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add_all([prompt_round, copy_round_1, copy_round_2])
    await db_session.flush()

    phraseset = Phraseset(
        phraseset_id=uuid.uuid4(),
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy_round_1.round_id,
        copy_round_2_id=copy_round_2.round_id,
        prompt_text=prompt.text,
        original_phrase="ORIGINAL",
        copy_phrase_1="COPY ONE",
        copy_phrase_2="COPY TWO",
        status="open",
        vote_count=0,
        total_pool=settings.prize_pool_base,
        vote_contributions=0,
        vote_payouts_paid=0,
        system_contribution=0,
    )
    db_session.add(phraseset)
    await db_session.flush()

    vote_round = Round(
        round_id=uuid.uuid4(),
        player_id=player.player_id,
        round_type="vote",
        status="active",
        cost=settings.vote_cost,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.vote_round_seconds),
        phraseset_id=phraseset.phraseset_id,
    )
    db_session.add(vote_round)
    await db_session.flush()

    player_data = await db_session.get(QFPlayerData, player.player_id)
    assert player_data is not None
    player_data.active_round_id = vote_round.round_id
    await db_session.commit()

    first = await _get_current_round(player, db_session)
    second = await _get_current_round(player, db_session)

    assert first.state is not None
    assert second.state is not None
    assert first.state["phrases"] == second.state["phrases"]

    choices = await db_session.execute(
        select(QFVoteChoice)
        .where(QFVoteChoice.round_id == vote_round.round_id)
        .order_by(QFVoteChoice.position.asc())
    )
    persisted_choices = list(choices.scalars().all())
    assert len(persisted_choices) == 3
    assert [choice.displayed_phrase for choice in persisted_choices] == first.state["phrases"]
