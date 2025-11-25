"""Tests for flagged prompt flows."""
import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy import select

from backend.models.qf.player import QFPlayer
from backend.models.qf.prompt import Prompt
from backend.models.qf.round import Round
from backend.models.qf.flagged_prompt import FlaggedPrompt
from backend.services import RoundService
from backend.services import TransactionService
from backend.services import FlaggedPromptService
from backend.services import QueueService


def _create_player(email_prefix: str, balance: int = 1000) -> QFPlayer:
    unique = uuid.uuid4().hex[:8]
    return QFPlayer(
        player_id=uuid.uuid4(),
        username=f"{email_prefix}_{unique}",
        username_canonical=f"{email_prefix}_{unique}",
        email=f"{email_prefix}_{unique}@example.com",
        password_hash="test",
        wallet=balance,
    )


async def _start_prompt_and_copy_round(db_session, transaction_service, round_service, prompt_player, copy_player) -> tuple[Round, Round]:
    # Ensure queue is empty to avoid cross-test contamination
    while QueueService.get_next_prompt_round():
        pass

    prompt = Prompt(
        prompt_id=uuid.uuid4(),
        text=f"The best beach day {uuid.uuid4().hex[:6]}",
        category="general",
        enabled=True,
    )
    db_session.add(prompt)
    await db_session.commit()

    prompt_round = await round_service.start_prompt_round(prompt_player, transaction_service)
    await round_service.submit_prompt_phrase(prompt_round.round_id, "SUNSET SHORE", prompt_player, transaction_service)

    copy_round, _ = await round_service.start_copy_round(copy_player, transaction_service)
    await db_session.refresh(copy_player)

    return prompt_round, copy_round


@pytest.mark.asyncio
async def test_flag_copy_round_creates_flag(db_session):
    prompt_player = _create_player('prompt', wallet=2000)
    copy_player = _create_player('copy', wallet=2000)
    db_session.add_all([prompt_player, copy_player])
    await db_session.commit()

    transaction_service = TransactionService(db_session)
    round_service = RoundService(db_session)

    prompt_round, copy_round = await _start_prompt_and_copy_round(
        db_session, transaction_service, round_service, prompt_player, copy_player
    )

    balance_before_flag = copy_player.balance

    flag = await round_service.flag_copy_round(copy_round.round_id, copy_player, transaction_service)

    assert flag.status == 'pending'
    assert flag.prompt_round_id == prompt_round.round_id
    assert flag.copy_round_id == copy_round.round_id
    assert flag.partial_refund_amount == copy_round.cost - round_service.settings.abandoned_penalty
    assert flag.penalty_kept == round_service.settings.abandoned_penalty

    refreshed_copy_round = await db_session.get(Round, copy_round.round_id)
    assert refreshed_copy_round.status == 'abandoned'

    refreshed_prompt_round = await db_session.get(Round, prompt_round.round_id)
    assert refreshed_prompt_round.phraseset_status == 'flagged_pending'

    await db_session.refresh(copy_player)
    expected_balance = balance_before_flag + flag.partial_refund_amount
    assert copy_player.balance == expected_balance

    flags_in_db = await db_session.execute(select(FlaggedPrompt))
    assert len(flags_in_db.scalars().all()) == 1


@pytest.mark.asyncio
async def test_confirm_flag_refunds_and_locks_prompt_owner(db_session):
    prompt_player = _create_player('prompt', wallet=2000)
    copy_player = _create_player('copy', wallet=2000)
    admin_player = _create_player('admin', wallet=0)
    db_session.add_all([prompt_player, copy_player, admin_player])
    await db_session.commit()

    transaction_service = TransactionService(db_session)
    round_service = RoundService(db_session)
    flag_service = FlaggedPromptService(db_session)

    prompt_round, copy_round = await _start_prompt_and_copy_round(
        db_session, transaction_service, round_service, prompt_player, copy_player
    )

    flag = await round_service.flag_copy_round(copy_round.round_id, copy_player, transaction_service)
    await db_session.refresh(copy_player)
    balance_after_partial_refund = copy_player.balance

    result = await flag_service.resolve_flag(flag.flag_id, 'confirm', admin_player, transaction_service)
    assert result is not None
    assert result.flag.status == 'confirmed'

    await db_session.refresh(copy_player)
    assert copy_player.balance == balance_after_partial_refund + flag.penalty_kept

    await db_session.refresh(prompt_player)
    assert prompt_player.locked_until is not None
    locked_until = prompt_player.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    assert locked_until > datetime.now(UTC)

    refreshed_prompt_round = await db_session.get(Round, prompt_round.round_id)
    assert refreshed_prompt_round.phraseset_status == 'flagged_removed'


@pytest.mark.asyncio
async def test_dismiss_flag_increments_reporter_streak_and_requeues(db_session):
    prompt_player = _create_player('prompt', wallet=2000)
    copy_player = _create_player('copy', wallet=2000)
    admin_player = _create_player('admin', wallet=0)
    db_session.add_all([prompt_player, copy_player, admin_player])
    await db_session.commit()

    transaction_service = TransactionService(db_session)
    round_service = RoundService(db_session)
    flag_service = FlaggedPromptService(db_session)

    prompt_round, copy_round = await _start_prompt_and_copy_round(
        db_session, transaction_service, round_service, prompt_player, copy_player
    )

    copy_player.flag_dismissal_streak = 4
    await db_session.commit()

    flag = await round_service.flag_copy_round(copy_round.round_id, copy_player, transaction_service)

    result = await flag_service.resolve_flag(flag.flag_id, 'dismiss', admin_player, transaction_service)
    assert result is not None
    assert result.flag.status == 'dismissed'

    await db_session.refresh(copy_player)
    assert copy_player.flag_dismissal_streak == 0
    assert copy_player.locked_until is not None
    locked_until = copy_player.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=UTC)
    assert locked_until > datetime.now(UTC)

    refreshed_prompt_round = await db_session.get(Round, prompt_round.round_id)
    assert refreshed_prompt_round.phraseset_status in (None, 'waiting_copies')

    # Prompt should be back in queue for another copy player
    assert QueueService.get_prompt_rounds_waiting() > 0

