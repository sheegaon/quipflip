"""Service layer for managing flagged prompt phrases."""
from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from backend.models.qf.flagged_prompt import FlaggedPrompt
from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.services.qf.queue_service import QFQueueService
from backend.services.transaction_service import TransactionService
from backend.config import get_settings


class FlaggedPromptRecord:
    """Structured data returned from list/resolve operations."""

    def __init__(
        self,
        flag: FlaggedPrompt,
        reporter_username: str,
        prompt_username: str,
        reviewer_username: Optional[str],
    ) -> None:
        self.flag = flag
        self.reporter_username = reporter_username
        self.prompt_username = prompt_username
        self.reviewer_username = reviewer_username


class FlaggedPromptService:
    """Business logic for viewing and resolving flagged prompt phrases."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def list_flags(self, status: Optional[str] = None) -> list[FlaggedPromptRecord]:
        reporter_alias = aliased(QFPlayer)
        prompt_alias = aliased(QFPlayer)
        reviewer_alias = aliased(QFPlayer)

        query = (
            select(
                FlaggedPrompt,
                reporter_alias.username,
                prompt_alias.username,
                reviewer_alias.username,
            )
            .join(reporter_alias, FlaggedPrompt.reporter_player_id == reporter_alias.player_id)
            .join(prompt_alias, FlaggedPrompt.prompt_player_id == prompt_alias.player_id)
            .join(
                reviewer_alias,
                FlaggedPrompt.reviewer_player_id == reviewer_alias.player_id,
                isouter=True,
            )
            .order_by(FlaggedPrompt.created_at.desc())
        )

        if status:
            query = query.where(FlaggedPrompt.status == status)

        result = await self.db.execute(query)
        records: list[FlaggedPromptRecord] = []
        for flag, reporter_username, prompt_username, reviewer_username in result.all():
            records.append(
                FlaggedPromptRecord(
                    flag=flag,
                    reporter_username=reporter_username,
                    prompt_username=prompt_username,
                    reviewer_username=reviewer_username,
                )
            )
        return records

    async def resolve_flag(
        self,
        flag_id: UUID,
        action: str,
        admin: QFPlayer,
        transaction_service: TransactionService,
    ) -> Optional[FlaggedPromptRecord]:
        flag = await self.db.get(FlaggedPrompt, flag_id)
        if not flag:
            return None

        if flag.status != "pending":
            raise ValueError("flag_already_resolved")

        reporter = await self.db.get(QFPlayer, flag.reporter_player_id)
        prompt_owner = await self.db.get(QFPlayer, flag.prompt_player_id)
        prompt_round = await self.db.get(Round, flag.prompt_round_id)

        now = datetime.now(UTC)
        flag.reviewed_at = now
        flag.reviewer_player_id = admin.player_id

        if action == "confirm":
            flag.status = "confirmed"
            # Ensure prompt never returns to queue
            if prompt_round:
                prompt_round.phraseset_status = "flagged_removed"
                QFQueueService.remove_prompt_round_from_queue(prompt_round.round_id)

            if reporter and flag.penalty_kept > 0:
                await transaction_service.create_transaction(
                    reporter.player_id,
                    flag.penalty_kept,
                    "flag_refund",
                    flag.flag_id,
                    auto_commit=False,
                )

            if reporter:
                reporter.flag_dismissal_streak = 0

            if prompt_owner:
                lock_until = now + timedelta(hours=24)
                if not prompt_owner.locked_until or prompt_owner.locked_until < lock_until:
                    prompt_owner.locked_until = lock_until

        elif action == "dismiss":
            flag.status = "dismissed"

            if reporter:
                reporter.flag_dismissal_streak = reporter.flag_dismissal_streak + 1
                if reporter.flag_dismissal_streak >= 5:
                    lock_until = now + timedelta(hours=24)
                    if reporter.locked_until and reporter.locked_until > now:
                        lock_until = max(reporter.locked_until, lock_until)
                    reporter.locked_until = lock_until
                    reporter.flag_dismissal_streak = 0

            if prompt_round:
                restored_status = flag.previous_phraseset_status
                prompt_round.phraseset_status = restored_status

                needs_queue = False
                if prompt_round.status == "submitted" and prompt_round.copy2_player_id is None:
                    if restored_status in (None, "waiting_copies", "waiting_copy1"):
                        needs_queue = True

                if needs_queue:
                    QFQueueService.add_prompt_round_to_queue(prompt_round.round_id)

        else:
            raise ValueError("invalid_action")

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(flag)

        from backend.utils.cache import dashboard_cache

        if reporter:
            dashboard_cache.invalidate_player_data(reporter.player_id)
        if prompt_owner:
            dashboard_cache.invalidate_player_data(prompt_owner.player_id)

        reporter_username = reporter.username if reporter else "Unknown Reporter"
        prompt_username = prompt_owner.username if prompt_owner else "Unknown Player"
        reviewer_username = admin.username

        return FlaggedPromptRecord(
            flag=flag,
            reporter_username=reporter_username,
            prompt_username=prompt_username,
            reviewer_username=reviewer_username,
        )
