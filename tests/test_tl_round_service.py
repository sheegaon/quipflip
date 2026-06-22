"""Integration tests for ThinkLink round lifecycle behavior."""

import uuid
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from backend.models.tl.answer import TLAnswer
from backend.models.tl.cluster import TLCluster
from backend.models.tl.guess import TLGuess
from backend.models.tl.prompt import TLPrompt
from backend.models.tl.round import TLRound
from backend.models.tl.player_data import TLPlayerData
from backend.services.tl.round_service import TLRoundService
from backend.services.tl.scoring_service import TLScoringService
from backend.services.tl.transaction_service import TLTransactionService


def _vector(seed: float = 0.0) -> list[float]:
    return [seed] * 1536


@pytest.mark.asyncio
async def test_tl_abandon_round_completes_current_score_without_refund(db_session, player_factory):
    """Manual quit should close the round at the current score without the old 95-coin refund."""

    player = await player_factory()
    prompt = TLPrompt(
        prompt_id=uuid.uuid4(),
        text="Name something you lose in the couch",
        embedding=_vector(0.1),
        is_active=True,
        ai_seeded=False,
    )
    db_session.add(prompt)
    await db_session.flush()

    round_obj = TLRound(
        round_id=uuid.uuid4(),
        player_id=player.player_id,
        prompt_id=prompt.prompt_id,
        snapshot_answer_ids=[str(uuid.uuid4())],
        snapshot_cluster_ids=[str(uuid.uuid4())],
        snapshot_total_weight=1.0,
        matched_clusters=[],
        strikes=1,
        status="active",
    )
    db_session.add(round_obj)
    await db_session.flush()

    transaction_service = TLTransactionService(db_session)
    await transaction_service.create_transaction(
        player_id=player.player_id,
        amount=-100,
        transaction_type="round_entry",
        round_id=round_obj.round_id,
        description="Round entry",
    )

    guess = TLGuess(
        round_id=round_obj.round_id,
        text="wallet",
        embedding=_vector(0.2),
        was_match=False,
        matched_answer_ids=[],
        matched_cluster_ids=[],
        caused_strike=True,
    )
    db_session.add(guess)
    await db_session.flush()

    round_service = TLRoundService(Mock(), Mock(), TLScoringService(), Mock())
    result, error = await round_service.abandon_round(
        db_session,
        str(round_obj.round_id),
        str(player.player_id),
    )

    assert error is None
    assert result["status"] == "completed"
    assert result["refund_amount"] == 0

    await db_session.refresh(round_obj)
    assert round_obj.status == "completed"
    assert round_obj.final_coverage == pytest.approx(0.0)

    player_data = (
        await db_session.execute(
            select(TLPlayerData).where(TLPlayerData.player_id == player.player_id)
        )
    ).scalar_one()
    assert player_data.wallet == 900


@pytest.mark.asyncio
async def test_tl_finalize_round_is_stale_safe(db_session, player_factory):
    """A second finalizer run should no-op instead of double-updating stats or balances."""

    player = await player_factory()
    prompt = TLPrompt(
        prompt_id=uuid.uuid4(),
        text="Name a thing that is always in your pocket",
        embedding=_vector(0.1),
        is_active=True,
        ai_seeded=False,
    )
    cluster = TLCluster(
        cluster_id=uuid.uuid4(),
        prompt_id=prompt.prompt_id,
        centroid_embedding=_vector(0.3),
        size=1,
    )
    answer = TLAnswer(
        answer_id=uuid.uuid4(),
        prompt_id=prompt.prompt_id,
        text="Keys",
        embedding=_vector(0.4),
        cluster_id=cluster.cluster_id,
        answer_players_count=1,
        shows=0,
        contributed_matches=0,
        is_active=True,
    )
    db_session.add(prompt)
    await db_session.flush()
    db_session.add(cluster)
    await db_session.flush()
    db_session.add(answer)
    await db_session.flush()

    round_obj = TLRound(
        round_id=uuid.uuid4(),
        player_id=player.player_id,
        prompt_id=prompt.prompt_id,
        snapshot_answer_ids=[str(answer.answer_id)],
        snapshot_cluster_ids=[str(cluster.cluster_id)],
        snapshot_total_weight=1.0,
        matched_clusters=[],
        strikes=0,
        status="active",
    )
    db_session.add(round_obj)
    await db_session.flush()

    scoring_service = TLScoringService()

    first = await scoring_service.finalize_round(
        db_session,
        round_obj,
        wallet_award=0,
        vault_award=0,
        gross_payout=0,
        coverage=0.0,
    )
    assert first is True

    await db_session.refresh(answer)
    assert answer.shows == 1

    second = await scoring_service.finalize_round(
        db_session,
        round_obj,
        wallet_award=0,
        vault_award=0,
        gross_payout=0,
        coverage=0.0,
    )
    assert second is False

    await db_session.refresh(answer)
    assert answer.shows == 1
