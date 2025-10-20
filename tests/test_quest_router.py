"""Tests for quest router endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4

from backend.main import app
from backend.models.quest import Quest, QuestType, QuestStatus
from backend.services.quest_service import QuestService


@pytest.mark.asyncio
async def test_get_player_quests_with_existing_quests(test_app, db_session, player_factory):
    """Test GET /quests returns properly formatted quest responses."""
    # Create a player
    player = await player_factory()

    # Create a quest directly in database
    quest_service = QuestService(db_session)
    await quest_service._create_quest(player.player_id, QuestType.HOT_STREAK_5)
    await db_session.commit()

    # Call the API endpoint
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(
            "/quests",
            headers={"Authorization": f"Bearer {player.api_key}"}
        )

    # Should succeed without 500 error
    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "quests" in data
    assert "total_count" in data
    assert data["total_count"] >= 1

    # Verify quest data is properly formatted
    quests = data["quests"]
    hot_streak_quest = next((q for q in quests if q["quest_type"] == "hot_streak_5"), None)
    assert hot_streak_quest is not None

    # Verify config was properly loaded (not the fallback)
    assert hot_streak_quest["name"] == "Hot Streak"
    assert hot_streak_quest["category"] == "streak"
    assert hot_streak_quest["reward_amount"] == 10
    assert "progress_percentage" in hot_streak_quest
    assert "progress_current" in hot_streak_quest
    assert "progress_target" in hot_streak_quest


@pytest.mark.asyncio
async def test_get_active_quests(test_app, db_session, player_factory):
    """Test GET /quests/active returns only active quests."""
    player = await player_factory()

    # Create both active and completed quests
    quest_service = QuestService(db_session)
    active_quest = await quest_service._create_quest(player.player_id, QuestType.HOT_STREAK_5)
    completed_quest = await quest_service._create_quest(player.player_id, QuestType.MILESTONE_VOTES_100)
    completed_quest.status = QuestStatus.COMPLETED.value
    await db_session.commit()

    # Call the API
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(
            "/quests/active",
            headers={"Authorization": f"Bearer {player.api_key}"}
        )

    assert response.status_code == 200
    quests = response.json()

    # Should only return active quests
    assert len([q for q in quests if q["status"] == "active"]) == len(quests)
    assert any(q["quest_type"] == "hot_streak_5" for q in quests)
    assert not any(q["quest_type"] == "milestone_votes_100" for q in quests)


@pytest.mark.asyncio
async def test_get_claimable_quests(test_app, db_session, player_factory):
    """Test GET /quests/claimable returns only completed quests."""
    player = await player_factory()

    # Create both active and completed quests
    quest_service = QuestService(db_session)
    active_quest = await quest_service._create_quest(player.player_id, QuestType.HOT_STREAK_5)
    completed_quest = await quest_service._create_quest(player.player_id, QuestType.MILESTONE_VOTES_100)
    completed_quest.status = QuestStatus.COMPLETED.value
    await db_session.commit()

    # Call the API
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(
            "/quests/claimable",
            headers={"Authorization": f"Bearer {player.api_key}"}
        )

    assert response.status_code == 200
    quests = response.json()

    # Should only return completed quests
    assert len([q for q in quests if q["status"] == "completed"]) == len(quests)
    assert not any(q["quest_type"] == "hot_streak_5" for q in quests)
    assert any(q["quest_type"] == "milestone_votes_100" for q in quests)


@pytest.mark.asyncio
async def test_quest_duplicate_prevention(test_app, db_session, player_factory):
    """Test that _create_quest doesn't crash when creating duplicate quests."""
    player = await player_factory()

    quest_service = QuestService(db_session)

    # Create the same quest twice
    quest1 = await quest_service._create_quest(player.player_id, QuestType.HOT_STREAK_5)
    await db_session.commit()

    # This should not crash with InvalidRequestError
    quest2 = await quest_service._create_quest(player.player_id, QuestType.HOT_STREAK_5)

    # Should return the same quest
    assert quest1.quest_id == quest2.quest_id
