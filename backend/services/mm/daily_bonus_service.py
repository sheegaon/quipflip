"""Daily bonus handling for Meme Mint."""

from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mm.daily_bonus import MMDailyBonus
from backend.models.mm.player import MMPlayer
from backend.services.mm.system_config_service import MMSystemConfigService
from backend.services.transaction_service import TransactionService
from backend.utils.exceptions import InsufficientBalanceError
from backend.utils.model_registry import GameType


class MMDailyBonusError(RuntimeError):
    """Raised when Meme Mint daily bonus operations fail."""


class MMDailyBonusService:
    """Service for checking and claiming Meme Mint daily bonuses."""

    def __init__(self, db: AsyncSession, config_service: MMSystemConfigService | None = None):
        self.db = db
        self.config_service = config_service or MMSystemConfigService(db)
        self.transaction_service = TransactionService(db, game_type=GameType.MM)

    async def is_bonus_available(self, player_id: str) -> bool:
        today = datetime.now(UTC).date()
        player_result = await self.db.execute(select(MMPlayer).where(MMPlayer.player_id == player_id))
        player = player_result.scalars().first()
        if not player or player.is_guest:
            return False
        if player.created_at.date() == today:
            return False
        result = await self.db.execute(
            select(MMDailyBonus).where(MMDailyBonus.player_id == player_id, MMDailyBonus.date == today)
        )
        return result.scalars().first() is None

    async def claim_bonus(self, player_id: str) -> dict:
        today = datetime.now(UTC)
        bonus_date = today.date()
        amount = await self.config_service.get_config_value("mm_daily_bonus_amount")
        try:
            player_result = await self.db.execute(select(MMPlayer).where(MMPlayer.player_id == player_id))
            player = player_result.scalars().first()
            if not player:
                raise MMDailyBonusError("not_available")
            if player.is_guest or player.created_at.date() == bonus_date:
                raise MMDailyBonusError("not_available")

            existing = await self.db.execute(
                select(MMDailyBonus)
                .where(MMDailyBonus.player_id == player_id, MMDailyBonus.date == bonus_date)
                .with_for_update()
            )
            if existing.scalars().first():
                raise MMDailyBonusError("already_claimed")

            bonus = MMDailyBonus(player_id=player_id, amount=amount, date=bonus_date)
            self.db.add(bonus)
            transaction = await self.transaction_service.create_transaction(
                player_id=player_id,
                amount=amount,
                trans_type="daily_bonus",
                reference_id=bonus.bonus_id,
                auto_commit=False,
                wallet_type="wallet",
            )
            await self.db.commit()
        except InsufficientBalanceError as exc:
            await self.db.rollback()
            raise MMDailyBonusError(str(exc)) from exc
        except Exception as exc:
            await self.db.rollback()
            raise MMDailyBonusError(str(exc)) from exc

        return {"amount": amount, "claimed_at": today, "transaction_id": transaction.transaction_id}
