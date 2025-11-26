"""Manage per-player daily state for Meme Mint."""

from datetime import UTC, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mm.player_daily_state import MMPlayerDailyState
from backend.services.mm.system_config_service import MMSystemConfigService


class MMPlayerDailyStateService:
    """Track free caption quota usage for Meme Mint players."""

    def __init__(self, db: AsyncSession, config_service: MMSystemConfigService | None = None):
        self.db = db
        self.config_service = config_service or MMSystemConfigService(db)

    async def _get_or_create_state(self, player_id: str) -> MMPlayerDailyState:
        today = datetime.now(UTC).date()
        result = await self.db.execute(
            select(MMPlayerDailyState)
            .where(MMPlayerDailyState.player_id == player_id)
            .where(MMPlayerDailyState.date == today)
            .with_for_update()
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = MMPlayerDailyState(player_id=player_id, date=today, free_captions_used=0)
            self.db.add(state)
            await self.db.flush()
        return state

    async def get_remaining_free_captions(self, player_id: str) -> int:
        state = await self._get_or_create_state(player_id)
        allowance = await self.config_service.get_config_value("mm_free_captions_per_day", default=0)
        return max(allowance - state.free_captions_used, 0)

    async def consume_free_caption(self, player_id: str) -> MMPlayerDailyState:
        state = await self._get_or_create_state(player_id)
        allowance = await self.config_service.get_config_value("mm_free_captions_per_day", default=0)
        if state.free_captions_used < allowance:
            state.free_captions_used += 1
        await self.db.commit()
        await self.db.refresh(state)
        return state
