"""Durable assignment regressions for Initial Reaction."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from backend.models.ir.assignment import IRAssignment
from backend.models.ir.backronym_entry import BackronymEntry
from backend.models.ir.player_data import IRPlayerData
from backend.models.ir.transaction import IRTransaction
from backend.services.ir.assignment_service import IRAssignmentError, IRAssignmentService
from backend.services.ir.player_service import IRPlayerService
from backend.services.phrase_validator import PhraseValidator
from backend.utils.passwords import hash_password


async def _create_player(db_session):
    suffix = uuid.uuid4().hex[:8]
    return await IRPlayerService(db_session).create_player(
        username=f"ir_assignment_{suffix}",
        email=f"ir_assignment_{suffix}@example.com",
        password_hash=hash_password("TestPassword123!"),
    )


def _valid_words(set_obj):
    dictionary = PhraseValidator().dictionary
    return [
        next(word for word in dictionary if word.startswith(letter) and len(word) >= 2)
        for letter in set_obj.word
    ]


@pytest.mark.asyncio
async def test_start_reuses_durable_assignment(db_session):
    player = await _create_player(db_session)
    service = IRAssignmentService(db_session)

    first, first_set = await service.assign(player.player_id)
    second, second_set = await service.assign(player.player_id)

    assert second.assignment_id == first.assignment_id
    assert second.assignment_token == first.assignment_token
    assert second_set.set_id == first_set.set_id
    assert await db_session.scalar(select(func.count(IRAssignment.assignment_id))) == 1


@pytest.mark.asyncio
async def test_submit_requires_assignment_token_and_moves_money_once(db_session):
    player = await _create_player(db_session)
    service = IRAssignmentService(db_session)
    assignment, set_obj = await service.assign(player.player_id)
    starting_wallet = await db_session.scalar(
        select(IRPlayerData.wallet).where(IRPlayerData.player_id == player.player_id)
    )
    words = _valid_words(set_obj)

    with pytest.raises(IRAssignmentError, match="assignment_not_found"):
        await service.submit(
            player.player_id,
            set_obj.set_id,
            uuid.uuid4(),
            words,
        )

    entry, submitted_set = await service.submit(
        str(player.player_id),
        str(set_obj.set_id),
        str(assignment.assignment_token),
        words,
    )
    assert submitted_set.set_id == set_obj.set_id

    with pytest.raises(IRAssignmentError, match="assignment_already_submitted"):
        await service.submit(
            player.player_id,
            set_obj.set_id,
            assignment.assignment_token,
            words,
        )

    refreshed_assignment = await db_session.get(IRAssignment, assignment.assignment_id)
    ending_wallet = await db_session.scalar(
        select(IRPlayerData.wallet).where(IRPlayerData.player_id == player.player_id)
    )
    assert refreshed_assignment.status == "submitted"
    assert refreshed_assignment.entry_id == entry.entry_id
    assert ending_wallet == starting_wallet - service.settings.ir_backronym_entry_cost
    assert await db_session.scalar(select(func.count(BackronymEntry.entry_id))) == 1
    assert await db_session.scalar(select(func.count(IRTransaction.transaction_id))) == 1


@pytest.mark.asyncio
async def test_assignment_rejects_invalid_uuid_parameters(db_session):
    player = await _create_player(db_session)
    service = IRAssignmentService(db_session)
    assignment, set_obj = await service.assign(player.player_id)

    assert await service.get_active_assignment("not-a-uuid") is None
    with pytest.raises(IRAssignmentError, match="invalid_uuid_parameter"):
        await service.submit(
            player.player_id,
            "not-a-uuid",
            assignment.assignment_token,
            _valid_words(set_obj),
        )


@pytest.mark.asyncio
async def test_assign_reserves_at_most_five_players_per_open_set(db_session):
    players = [await _create_player(db_session) for _ in range(6)]
    service = IRAssignmentService(db_session)

    assignments = [await service.assign(player.player_id) for player in players]
    first_set_id = assignments[0][1].set_id

    assert all(set_obj.set_id == first_set_id for _, set_obj in assignments[:5])
    assert assignments[5][1].set_id != first_set_id
    assert await db_session.scalar(
        select(func.count(IRAssignment.assignment_id)).where(
            IRAssignment.set_id == first_set_id,
            IRAssignment.status == "assigned",
        )
    ) == 5


@pytest.mark.asyncio
async def test_transition_expires_unsubmitted_assignments(db_session):
    players = [await _create_player(db_session) for _ in range(2)]
    service = IRAssignmentService(db_session)
    first, set_obj = await service.assign(players[0].player_id)
    second, _ = await service.assign(players[1].player_id)
    set_obj.entry_count = 5
    await db_session.commit()

    await service.set_service.transition_to_voting(set_obj.set_id)
    await db_session.refresh(first)
    await db_session.refresh(second)

    assert first.status == "expired"
    assert second.status == "expired"
    assert first.expired_at is not None
    assert await service.get_active_assignment(players[0].player_id) is None
