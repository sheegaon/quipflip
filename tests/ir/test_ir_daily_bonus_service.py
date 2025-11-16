"""Tests covering the IR daily bonus service."""

import pytest
from sqlalchemy import select

from backend.config import get_settings
from backend.models.ir.ir_daily_bonus import IRDailyBonus
from backend.services.ir.ir_daily_bonus_service import (
    IRDailyBonusService,
    IRDailyBonusError,
)
from backend.services.ir.player_service import IRPlayerService
from backend.services.ir.transaction_service import IRTransactionError
from backend.utils.passwords import hash_password

settings = get_settings()


@pytest.mark.asyncio
async def test_claim_bonus_rolls_back_when_wallet_credit_fails(db_session, monkeypatch):
    """Bonus claims must be atomic so failures don't mark the bonus as claimed."""

    player_service = IRPlayerService(db_session)
    player = await player_service.create_player(
        username="ir_bonus_test",
        email="ir_bonus_test@example.com",
        password_hash=hash_password("Password123!"),
    )

    bonus_service = IRDailyBonusService(db_session)

    async def _raise_credit(*args, **kwargs):  # pragma: no cover - only used in this test
        raise IRTransactionError("boom")

    monkeypatch.setattr(
        bonus_service.transaction_service,
        "credit_wallet_in_transaction",
        _raise_credit,
    )

    with pytest.raises(IRDailyBonusError):
        await bonus_service.claim_bonus(str(player.player_id))

    stmt = select(IRDailyBonus).where(IRDailyBonus.player_id == str(player.player_id))
    result = await db_session.execute(stmt)
    assert result.scalars().first() is None

    fresh_player = await player_service.get_player_by_id(str(player.player_id))
    assert fresh_player.wallet == settings.ir_initial_balance

    # The player should still be allowed to retry once the wallet credit succeeds.
    retry_service = IRDailyBonusService(db_session)
    reward = await retry_service.claim_bonus(str(player.player_id))

    assert reward["amount"] == settings.ir_daily_bonus_amount

    result = await db_session.execute(stmt)
    bonus_row = result.scalars().first()
    assert bonus_row is not None

    fresh_player = await player_service.get_player_by_id(str(player.player_id))
    assert fresh_player.wallet == settings.ir_initial_balance + settings.ir_daily_bonus_amount
