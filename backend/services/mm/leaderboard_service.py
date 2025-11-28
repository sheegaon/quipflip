"""Leaderboard service for Meme Mint players."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, UTC
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mm.player import MMPlayer
from backend.models.mm.transaction import MMTransaction
from backend.models.mm.vote_round import MMVoteRound
from backend.services.ai.ai_service import AI_PLAYER_EMAIL_DOMAIN

logger = logging.getLogger(__name__)

LEADERBOARD_ROLES = ["prompt", "copy", "voter"]
WEEKLY_LEADERBOARD_LIMIT = 5
ALLTIME_LEADERBOARD_LIMIT = 10
GROSS_EARNINGS_LEADERBOARD_LIMIT_WEEKLY = 10
GROSS_EARNINGS_LEADERBOARD_LIMIT_ALLTIME = 20


class MMLeaderboardService:
    """Compute Meme Mint leaderboards for vault earnings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _add_current_player_to_leaderboard(
        entries: list[dict[str, Any]],
        top_limit: int,
        player_id: UUID,
        username: str | None,
        default_entry: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Add the current player to the leaderboard if missing."""

        lookup = {entry["player_id"]: entry for entry in entries}
        top_entries = entries[:top_limit]

        player_entry = lookup.get(player_id)
        if player_entry is None:
            player_entry = {
                **default_entry,
                "player_id": player_id,
                "username": username or "Unknown Player",
            }

        combined = [dict(entry) for entry in top_entries]
        if all(entry["player_id"] != player_entry["player_id"] for entry in combined):
            combined.append(dict(player_entry))

        for entry in combined:
            entry["is_current_player"] = entry["player_id"] == player_id

        return combined

    @staticmethod
    def _get_week_start() -> datetime:
        """Return the timestamp used as the start of the weekly window."""

        return datetime.now(UTC) - timedelta(days=7)

    def _build_total_rounds_subquery(self, start_date: datetime | None):
        """Build a subquery counting total rounds per player."""

        conditions = [MMVoteRound.abandoned.is_(False)]
        if start_date:
            conditions.append(MMVoteRound.created_at >= start_date)

        return (
            select(
                MMVoteRound.player_id.label("player_id"),
                func.count(MMVoteRound.round_id).label("total_rounds"),
            )
            .where(*conditions)
            .group_by(MMVoteRound.player_id)
            .subquery()
        )

    async def _build_gross_earnings_leaderboard(
        self,
        start_date: datetime | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Compute leaderboard entries ranked by vault balance or weekly vault change."""

        total_rounds_subquery = self._build_total_rounds_subquery(start_date)

        if start_date:
            vault_change_stmt = (
                select(
                    MMTransaction.player_id.label("player_id"),
                    func.sum(MMTransaction.amount).label("vault_change"),
                )
                .where(
                    MMTransaction.wallet_type == "vault",
                    MMTransaction.created_at >= start_date,
                )
                .group_by(MMTransaction.player_id)
                .subquery()
            )

            leaderboard_stmt = (
                select(
                    MMPlayer.player_id,
                    MMPlayer.username,
                    MMPlayer.email,
                    func.coalesce(vault_change_stmt.c.vault_change, 0).label("vault_balance"),
                    func.coalesce(total_rounds_subquery.c.total_rounds, 0).label("total_rounds"),
                )
                .join(vault_change_stmt, vault_change_stmt.c.player_id == MMPlayer.player_id)
                .join(
                    total_rounds_subquery,
                    total_rounds_subquery.c.player_id == MMPlayer.player_id,
                    isouter=True,
                )
                .where(
                    ~MMPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"),
                    vault_change_stmt.c.vault_change > 0,
                )
                .order_by(vault_change_stmt.c.vault_change.desc(), MMPlayer.username.asc())
                .limit(limit)
            )
        else:
            leaderboard_stmt = (
                select(
                    MMPlayer.player_id,
                    MMPlayer.username,
                    MMPlayer.email,
                    MMPlayer.vault.label("vault_balance"),
                    func.coalesce(total_rounds_subquery.c.total_rounds, 0).label("total_rounds"),
                )
                .join(
                    total_rounds_subquery,
                    total_rounds_subquery.c.player_id == MMPlayer.player_id,
                    isouter=True,
                )
                .where(
                    ~MMPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"),
                    MMPlayer.vault > 0,
                )
                .order_by(MMPlayer.vault.desc(), MMPlayer.username.asc())
                .limit(limit)
            )

        result = await self.db.execute(leaderboard_stmt)

        entries: list[dict[str, Any]] = []
        for rank, row in enumerate(result.all(), start=1):
            email = getattr(row, "email", "") or ""
            entries.append(
                {
                    "player_id": row.player_id,
                    "username": row.username,
                    "vault_balance": int(row.vault_balance or 0),
                    "total_rounds": int(row.total_rounds or 0),
                    "rank": rank,
                    "is_current_player": False,
                    "is_bot": False,
                    "is_ai": email.endswith(AI_PLAYER_EMAIL_DOMAIN),
                }
            )

        logger.debug(
            "Computed %s leaderboard with %d entries (start_date=%s)",
            "weekly" if start_date else "all-time",
            len(entries),
            start_date,
        )

        return entries

    async def get_weekly_leaderboard_for_player(
        self,
        player_id: UUID,
        username: str | None,
    ) -> tuple[dict[str, list[dict[str, Any]]], datetime]:
        """Return weekly leaderboard data including the current player."""

        start_date = self._get_week_start()
        gross_entries = await self._build_gross_earnings_leaderboard(
            start_date, GROSS_EARNINGS_LEADERBOARD_LIMIT_WEEKLY
        )

        result: dict[str, list[dict[str, Any]]] = {}
        for role in LEADERBOARD_ROLES:
            result[role] = self._add_current_player_to_leaderboard(
                [],
                WEEKLY_LEADERBOARD_LIMIT,
                player_id,
                username,
                {
                    "role": role,
                    "total_costs": 0,
                    "total_earnings": 0,
                    "net_earnings": 0,
                    "win_rate": 0.0,
                    "total_rounds": 0,
                    "rank": None,
                    "is_bot": False,
                    "is_ai": False,
                },
            )

        result["gross_earnings"] = self._add_current_player_to_leaderboard(
            gross_entries,
            GROSS_EARNINGS_LEADERBOARD_LIMIT_WEEKLY,
            player_id,
            username,
            {
                "vault_balance": 0,
                "total_rounds": 0,
                "rank": None,
                "is_bot": False,
                "is_ai": False,
            },
        )

        return result, datetime.now(UTC)

    async def get_alltime_leaderboard_for_player(
        self,
        player_id: UUID,
        username: str | None,
    ) -> tuple[dict[str, list[dict[str, Any]]], datetime]:
        """Return all-time leaderboard data including the current player."""

        gross_entries = await self._build_gross_earnings_leaderboard(
            start_date=None,
            limit=GROSS_EARNINGS_LEADERBOARD_LIMIT_ALLTIME,
        )

        result: dict[str, list[dict[str, Any]]] = {}
        for role in LEADERBOARD_ROLES:
            result[role] = self._add_current_player_to_leaderboard(
                [],
                ALLTIME_LEADERBOARD_LIMIT,
                player_id,
                username,
                {
                    "role": role,
                    "total_costs": 0,
                    "total_earnings": 0,
                    "net_earnings": 0,
                    "win_rate": 0.0,
                    "total_rounds": 0,
                    "rank": None,
                    "is_bot": False,
                    "is_ai": False,
                },
            )

        result["gross_earnings"] = self._add_current_player_to_leaderboard(
            gross_entries,
            GROSS_EARNINGS_LEADERBOARD_LIMIT_ALLTIME,
            player_id,
            username,
            {
                "vault_balance": 0,
                "total_rounds": 0,
                "rank": None,
                "is_bot": False,
                "is_ai": False,
            },
        )

        return result, datetime.now(UTC)
