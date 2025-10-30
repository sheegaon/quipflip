"""Tests for quest progress persistence."""

import uuid

import pytest

from backend.models.player import Player
from backend.models.quest import Quest, QuestType, QuestStatus


@pytest.mark.asyncio
async def test_quest_progress_updates_are_persisted(db_session):
    """Quest progress mutations should be written to the database."""

    test_id = uuid.uuid4().hex[:8]

    canonical = f"player_{test_id}"

    player = Player(
        player_id=uuid.uuid4(),
        username=canonical,
        username_canonical=canonical,
        pseudonym=f"Player_{test_id}",
        pseudonym_canonical=canonical,
        email=f"player_{test_id}@example.com",
        password_hash="hash",
        balance=0,
    )
    db_session.add(player)
    await db_session.commit()

    quest = Quest(
        player_id=player.player_id,
        quest_type=QuestType.MILESTONE_VOTES_100.value,
        status=QuestStatus.ACTIVE.value,
        progress={"current": 0, "target": 100},
        reward_amount=10,
    )
    db_session.add(quest)
    await db_session.commit()

    quest.progress["current"] = 5
    await db_session.commit()
    await db_session.refresh(quest)

    assert quest.progress["current"] == 5
