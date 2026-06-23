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
    dictionary = PhraseValidator().dictionary
    words = [
        next(word for word in dictionary if word.startswith(letter) and len(word) >= 2)
        for letter in set_obj.word
    ]

    with pytest.raises(IRAssignmentError, match="assignment_not_found"):
        await service.submit(
            player.player_id,
            set_obj.set_id,
            uuid.uuid4(),
            words,
        )

    entry, submitted_set = await service.submit(
        player.player_id,
        set_obj.set_id,
        assignment.assignment_token,
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
