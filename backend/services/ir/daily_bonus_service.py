"""Daily bonus handling for Initial Reaction players."""
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.ir.daily_bonus import IRDailyBonus
from backend.models.ir.player import IRPlayer
from backend.services.transaction_service import TransactionService
from backend.services.auth_service import GameType
from backend.utils.exceptions import InsufficientBalanceError


class IRDailyBonusError(RuntimeError):
    """Raised when daily bonus operations fail."""


class IRDailyBonusService:
    """Service responsible for checking and claiming daily bonuses."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.transaction_service = TransactionService(db, game_type=GameType.IR)

    async def is_bonus_available(self, player_id: str) -> bool:
        """Return True if the player can still claim today's bonus."""

        today = datetime.now(UTC).date()

        player_result = await self.db.execute(
            select(IRPlayer).where(IRPlayer.player_id == player_id)
        )
        player = player_result.scalars().first()
        if not player:
            return False

        if player.is_guest:
            return False

        if player.created_at.date() == today:
            return False

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
            player_result = await self.db.execute(
                select(IRPlayer).where(IRPlayer.player_id == player_id)
            )
            player = player_result.scalars().first()
            if not player:
                raise IRDailyBonusError("not_available")

            if player.is_guest or player.created_at.date() == bonus_date:
                raise IRDailyBonusError("not_available")

            # Check if bonus was already claimed today (do this before general availability check)
            stmt = select(IRDailyBonus).where(
                (IRDailyBonus.player_id == player_id)
                & (IRDailyBonus.date == bonus_date)
            ).with_for_update()
            result = await self.db.execute(stmt)
            if result.scalars().first():
                raise IRDailyBonusError("already_claimed")

            bonus = IRDailyBonus(
                player_id=player_id,
                bonus_amount=self.settings.ir_daily_bonus_amount,
                claimed_at=today,
                date=bonus_date,
            )
            self.db.add(bonus)

            transaction = await self.transaction_service.create_transaction(
                player_id=player_id,
                amount=self.settings.ir_daily_bonus_amount,
                trans_type="daily_bonus",
                auto_commit=False,
                wallet_type="wallet",
            )

            await self.db.commit()
        except InsufficientBalanceError as exc:
            await self.db.rollback()
            raise IRDailyBonusError(str(exc)) from exc
        except Exception as exc:
            await self.db.rollback()
            raise IRDailyBonusError(str(exc)) from exc

        return {
            "amount": self.settings.ir_daily_bonus_amount,
            "claimed_at": today,
            "transaction_id": transaction.transaction_id,
        }
