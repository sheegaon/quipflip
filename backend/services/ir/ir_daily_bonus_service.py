"""Daily bonus handling for Initial Reaction players."""
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.ir.ir_daily_bonus import IRDailyBonus
from backend.services.ir.transaction_service import IRTransactionService, IRTransactionError


class IRDailyBonusError(RuntimeError):
    """Raised when daily bonus operations fail."""


class IRDailyBonusService:
    """Service responsible for checking and claiming daily bonuses."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.transaction_service = IRTransactionService(db)

    async def is_bonus_available(self, player_id: str) -> bool:
        """Return True if the player can still claim today's bonus."""

        today = datetime.now(UTC).date()
        stmt = select(IRDailyBonus).where(
            (IRDailyBonus.player_id == player_id) & (IRDailyBonus.date == today)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first() is None

    async def claim_bonus(self, player_id: str) -> dict:
        """Claim the configured InitCoin bonus for today."""

        today = datetime.now(UTC)
        bonus_date = today.date()

        try:
            async with self.db.begin():
                stmt = select(IRDailyBonus).where(
                    (IRDailyBonus.player_id == player_id)
                    & (IRDailyBonus.date == bonus_date)
                ).with_for_update()
                result = await self.db.execute(stmt)
                if result.scalars().first():
                    raise IRDailyBonusError("already_claimed")

                bonus = IRDailyBonus(
                    player_id=player_id,
                    amount=self.settings.ir_daily_bonus_amount,
                    claimed_at=today,
                    date=bonus_date,
                )
                self.db.add(bonus)

                transaction = await self.transaction_service.credit_wallet(
                    player_id=player_id,
                    amount=self.settings.ir_daily_bonus_amount,
                    transaction_type=self.transaction_service.DAILY_BONUS,
                    use_existing_transaction=True,
                )
        except IRTransactionError as exc:
            raise IRDailyBonusError(str(exc)) from exc

        return {
            "amount": self.settings.ir_daily_bonus_amount,
            "claimed_at": today,
            "transaction_id": transaction.transaction_id,
        }
