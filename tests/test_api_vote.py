"""Tests for vote API endpoints.

This test suite specifically validates that vote submission through the API
works correctly, catching regressions like missing dependency parameters that
cause 422 validation errors.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta, UTC

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.models.player import Player
from backend.models.qf.player_data import QFPlayerData
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.config import get_settings

API_BASE_URL = "http://test/qf"


async def create_authenticated_player(test_app, username_suffix=""):
    """Helper to create a player and return auth token."""
    suffix = username_suffix or uuid4().hex[:6]
    payload = {
        "username": f"voter_{suffix}",
        "email": f"voter_{suffix}@example.com",
        "password": "VoterPass123!",
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        response = await client.post("/player", json=payload)
        assert response.status_code == 201
        data = response.json()
        return data["access_token"], data["player_id"]


async def create_complete_phraseset(db_session):
    """Create a complete phraseset ready for voting."""
    from backend.models.qf.prompt import Prompt

    settings = get_settings()
    test_id = uuid4().hex[:8]

    # Create a prompt first
    prompt = Prompt(
        prompt_id=uuid4(),
        text=f"Test prompt {test_id}",
        category="simple",
        enabled=True,
    )
    db_session.add(prompt)
    await db_session.flush()

    # Create three players
    prompter = Player(
        player_id=uuid4(),
        username=f"prompter_{test_id}",
        username_canonical=f"prompter_{test_id}",
        email=f"prompter_{test_id}@test.com",
        password_hash="hash",
    )
    copier1 = Player(
        player_id=uuid4(),
        username=f"copier1_{test_id}",
        username_canonical=f"copier1_{test_id}",
        email=f"copier1_{test_id}@test.com",
        password_hash="hash",
    )
    copier2 = Player(
        player_id=uuid4(),
        username=f"copier2_{test_id}",
        username_canonical=f"copier2_{test_id}",
        email=f"copier2_{test_id}@test.com",
        password_hash="hash",
    )
    db_session.add_all([prompter, copier1, copier2])
    await db_session.flush()

    db_session.add_all(
        [
            QFPlayerData(player_id=prompter.player_id, wallet=settings.qf_starting_wallet),
            QFPlayerData(player_id=copier1.player_id, wallet=settings.qf_starting_wallet),
            QFPlayerData(player_id=copier2.player_id, wallet=settings.qf_starting_wallet),
        ]
    )
    await db_session.flush()

    # Create rounds
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    prompt_round = Round(
        round_id=uuid4(),
        player_id=prompter.player_id,
        round_type="prompt",
        status="completed",
        created_at=datetime.now(UTC),
        expires_at=expires_at,
        cost=settings.prompt_cost,
        prompt_id=prompt.prompt_id,
        prompt_text=prompt.text,
        submitted_phrase="ORIGINAL PHRASE",
    )
    copy_round1 = Round(
        round_id=uuid4(),
        player_id=copier1.player_id,
        round_type="copy",
        status="completed",
        created_at=datetime.now(UTC),
        expires_at=expires_at,
        cost=settings.copy_cost_normal,
        prompt_round_id=prompt_round.round_id,
        original_phrase="ORIGINAL PHRASE",
        copy_phrase="COPY PHRASE ONE",
    )
    copy_round2 = Round(
        round_id=uuid4(),
        player_id=copier2.player_id,
        round_type="copy",
        status="completed",
        created_at=datetime.now(UTC),
        expires_at=expires_at,
        cost=settings.copy_cost_normal,
        prompt_round_id=prompt_round.round_id,
        original_phrase="ORIGINAL PHRASE",
        copy_phrase="COPY PHRASE TWO",
    )

    db_session.add_all([prompt_round, copy_round1, copy_round2])
    await db_session.flush()

    # Create phraseset
    phraseset = Phraseset(
        phraseset_id=uuid4(),
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy_round1.round_id,
        copy_round_2_id=copy_round2.round_id,
        prompt_text=prompt.text,
        original_phrase="ORIGINAL PHRASE",
        copy_phrase_1="COPY PHRASE ONE",
        copy_phrase_2="COPY PHRASE TWO",
        status="active",
        created_at=datetime.now(UTC),
    )

    db_session.add(phraseset)
    await db_session.commit()

    return phraseset.phraseset_id, [prompter.player_id, copier1.player_id, copier2.player_id]


@pytest.mark.asyncio
async def test_vote_submission_no_validation_error(test_app, db_session):
    """Test that vote submission doesn't return 422 validation error.

    This test specifically catches the regression where enforce_vote_rate_limit
    was missing the game_type parameter, causing FastAPI to try to extract it
    from the request body and failing with a 422 error.

    Regression: https://github.com/anthropics/quipflip/issues/XXX
    """
    # Create authenticated voter (not a contributor)
    token, voter_id = await create_authenticated_player(test_app)

    # Create complete phraseset
    phraseset_id, contributor_ids = await create_complete_phraseset(db_session)

    # Verify voter is not a contributor
    assert voter_id not in contributor_ids

    # Get voter from database
    result = await db_session.execute(
        select(Player).where(Player.player_id == voter_id)
    )
    voter = result.scalar_one()

    # Create a vote round for the voter
    settings = get_settings()
    vote_round = Round(
        round_id=uuid4(),
        player_id=voter.player_id,
        round_type="vote",
        status="active",
        phraseset_id=phraseset_id,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        cost=settings.vote_cost,
    )
    db_session.add(vote_round)

    # Update voter's active round
    voter.active_round_id = vote_round.round_id
    await db_session.commit()

    # Submit vote via API
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        response = await client.post(
            f"/phrasesets/{phraseset_id}/vote",
            json={"phrase": "ORIGINAL PHRASE"},
            headers={"Authorization": f"Bearer {token}"}
        )

    # The critical assertion: should NOT return 422 (validation error)
    assert response.status_code != 422, (
        f"Vote submission returned 422 validation error. "
        f"This likely means enforce_vote_rate_limit is missing the game_type parameter. "
        f"Response: {response.json()}"
    )

    # Should return 200 (success)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify response structure
    data = response.json()
    assert "correct" in data
    assert "payout" in data
    assert "original_phrase" in data
    assert "your_choice" in data
    assert data["your_choice"] == "ORIGINAL PHRASE"


@pytest.mark.asyncio
async def test_vote_submission_validates_phrase(test_app, db_session):
    """Test that vote submission validates the phrase is one of the three choices."""
    # Create authenticated voter
    token, voter_id = await create_authenticated_player(test_app)

    # Create complete phraseset
    phraseset_id, contributor_ids = await create_complete_phraseset(db_session)

    # Get voter from database
    result = await db_session.execute(
        select(Player).where(Player.player_id == voter_id)
    )
    voter = result.scalar_one()

    # Create a vote round for the voter
    settings = get_settings()
    vote_round = Round(
        round_id=uuid4(),
        player_id=voter.player_id,
        round_type="vote",
        status="active",
        phraseset_id=phraseset_id,
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        cost=settings.vote_cost,
    )
    db_session.add(vote_round)

    # Update voter's active round
    voter.active_round_id = vote_round.round_id
    await db_session.commit()

    # Submit vote with invalid phrase
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        response = await client.post(
            f"/phrasesets/{phraseset_id}/vote",
            json={"phrase": "INVALID PHRASE"},
            headers={"Authorization": f"Bearer {token}"}
        )

    # Should return 400 (bad request) for invalid phrase, not 422 (validation error)
    assert response.status_code == 400
    assert "must be one of" in response.json()["detail"].lower()
