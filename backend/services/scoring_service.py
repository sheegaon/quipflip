"""Scoring and payout calculation service."""

from collections import defaultdict
import json
from datetime import UTC, datetime, timedelta
import logging
from typing import Any, Iterable
from uuid import UUID, uuid5

from sqlalchemy import and_, func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

try:  # pragma: no cover - optional dependency during import
    from redis.asyncio import Redis
except Exception:  # pragma: no cover - handled at runtime when Redis unavailable
    Redis = None  # type: ignore

from backend.models.phraseset import Phraseset
from backend.models.phraseset_activity import PhrasesetActivity
from backend.models.player import Player
from backend.models.transaction import Transaction
from backend.models.vote import Vote
from backend.models.round import Round
from backend.config import get_settings

logger = logging.getLogger(__name__)


settings = get_settings()


PLACEHOLDER_PLAYER_NAMESPACE = UUID("6c057f58-7199-43ff-b4fc-17b77df5e6a2")
WEEKLY_LEADERBOARD_LIMIT = 5
WEEKLY_LEADERBOARD_CACHE_KEY = "leaderboard:weekly:v3"  # v3: align payouts with round completion window, excludes AI players
AI_PLAYER_EMAIL_DOMAIN = "@quipflip.internal"


_redis_client: "Redis | None" = None


def _get_redis_client() -> "Redis | None":
    """Return a Redis client if configured."""

    global _redis_client

    if not settings.redis_url or Redis is None:
        return None

    if _redis_client is None:
        try:
            _redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(f"Unable to initialize Redis client for leaderboard cache: {exc}")
            _redis_client = None
            return None

    return _redis_client


async def _load_cached_weekly_leaderboard() -> tuple[list[dict[str, Any]], datetime] | None:
    """Fetch cached weekly leaderboard data from Redis, if available."""

    client = _get_redis_client()
    if client is None:
        return None

    try:
        raw_value = await client.get(WEEKLY_LEADERBOARD_CACHE_KEY)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Failed to read weekly leaderboard cache: {exc}")
        return None

    if not raw_value:
        return None

    try:
        payload = json.loads(raw_value)
        generated_at_raw = payload.get("generated_at")
        generated_at = datetime.fromisoformat(generated_at_raw) if generated_at_raw else None

        entries: list[dict[str, Any]] = []
        for entry in payload.get("entries", []):
            normalized = dict(entry)
            if "player_id" in normalized:
                try:
                    normalized["player_id"] = UUID(str(normalized["player_id"]))
                except Exception:
                    logger.error(
                        f"Skipping cached leaderboard entry with invalid player_id: {normalized.get('player_id')}"
                    )
                    continue
            entries.append(normalized)

        if generated_at is None:
            return None

        return entries, generated_at
    except Exception as exc:  # pragma: no cover - cache corruption fallback
        logger.error(f"Invalid data in weekly leaderboard cache: {exc}")
        return None


async def _store_weekly_leaderboard_cache(entries: list[dict[str, Any]], generated_at: datetime) -> None:
    """Persist leaderboard results to Redis for reuse across workers."""

    client = _get_redis_client()
    if client is None:
        return

    cache_entries: list[dict[str, Any]] = []
    for entry in entries:
        cache_entries.append(
            {
                **entry,
                "player_id": str(entry["player_id"]),
            }
        )

    payload = {
        "entries": cache_entries,
        "generated_at": generated_at.isoformat(),
    }

    try:
        await client.set(WEEKLY_LEADERBOARD_CACHE_KEY, json.dumps(payload), ex=3600)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Failed to write weekly leaderboard cache: {exc}")


def _placeholder_player_id(phraseset_id: UUID, role: str) -> UUID:
    """Return a deterministic placeholder ID for missing contributors."""

    return uuid5(PLACEHOLDER_PLAYER_NAMESPACE, f"{phraseset_id}:{role}")


class ScoringService:
    """Service for calculating scores and payouts."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_payouts(self, phraseset: Phraseset) -> dict:
        """Calculate points and payouts for a single phraseset."""
        payouts = await self.calculate_payouts_bulk([phraseset])
        return payouts.get(phraseset.phraseset_id, self._empty_payout(phraseset))

    async def calculate_payouts_bulk(
        self, phrasesets: Iterable[Phraseset]
    ) -> dict[UUID, dict]:
        """Calculate payouts for multiple phrasesets using batched queries."""
        phrasesets = list(phrasesets)
        if not phrasesets:
            return {}

        phraseset_ids = [phraseset.phraseset_id for phraseset in phrasesets]

        vote_rows = await self.db.execute(
            select(Vote).where(Vote.phraseset_id.in_(phraseset_ids))
        )
        votes_by_phraseset: dict[UUID, list[Vote]] = defaultdict(list)
        for vote in vote_rows.scalars().all():
            votes_by_phraseset[vote.phraseset_id].append(vote)

        round_ids: set[UUID] = set()
        for phraseset in phrasesets:
            round_ids.update(
                rid
                for rid in (
                    phraseset.prompt_round_id,
                    phraseset.copy_round_1_id,
                    phraseset.copy_round_2_id,
                )
                if rid
            )

        round_rows = await self.db.execute(
            select(Round.round_id, Round.player_id).where(Round.round_id.in_(round_ids))
        )
        round_players = {round_id: player_id for round_id, player_id in round_rows.all()}

        payouts_by_phraseset: dict[UUID, dict] = {}
        for phraseset in phrasesets:
            votes = votes_by_phraseset.get(phraseset.phraseset_id, [])
            payouts_by_phraseset[phraseset.phraseset_id] = self._calculate_single_payout(
                phraseset,
                votes,
                round_players,
            )

        return payouts_by_phraseset

    def _calculate_single_payout(
        self,
        phraseset: Phraseset,
        votes: list[Vote],
        round_players: dict[UUID, UUID],
    ) -> dict:
        """Compute payout data for a phraseset using pre-fetched dependencies."""
        original_votes = sum(1 for v in votes if v.voted_phrase == phraseset.original_phrase)
        copy1_votes = sum(1 for v in votes if v.voted_phrase == phraseset.copy_phrase_1)
        copy2_votes = sum(1 for v in votes if v.voted_phrase == phraseset.copy_phrase_2)

        original_points = original_votes * settings.correct_vote_points
        copy1_points = copy1_votes * settings.incorrect_vote_points
        copy2_points = copy2_votes * settings.incorrect_vote_points
        total_points = original_points + copy1_points + copy2_points

        prize_pool = phraseset.total_pool

        if total_points == 0:
            original_payout = prize_pool // 3
            copy1_payout = prize_pool // 3
            copy2_payout = prize_pool // 3
        else:
            original_payout = (original_points * prize_pool) // total_points
            copy1_payout = (copy1_points * prize_pool) // total_points
            copy2_payout = (copy2_points * prize_pool) // total_points

        prompt_player = round_players.get(
            phraseset.prompt_round_id,
            _placeholder_player_id(phraseset.phraseset_id, "prompt"),
        )
        copy1_player = round_players.get(
            phraseset.copy_round_1_id,
            _placeholder_player_id(phraseset.phraseset_id, "copy1"),
        )
        copy2_player = round_players.get(
            phraseset.copy_round_2_id,
            _placeholder_player_id(phraseset.phraseset_id, "copy2"),
        )

        logger.info(
            f"Calculated payouts for phraseset {phraseset.phraseset_id}: original={original_payout}, copy1={copy1_payout}, copy2={copy2_payout}"
        )

        return {
            "original": {
                "points": original_points,
                "payout": original_payout,
                "player_id": prompt_player,
                "phrase": phraseset.original_phrase,
            },
            "copy1": {
                "points": copy1_points,
                "payout": copy1_payout,
                "player_id": copy1_player,
                "phrase": phraseset.copy_phrase_1,
            },
            "copy2": {
                "points": copy2_points,
                "payout": copy2_payout,
                "player_id": copy2_player,
                "phrase": phraseset.copy_phrase_2,
            },
        }

    async def get_weekly_leaderboard_snapshot(self) -> tuple[list[dict[str, Any]], datetime | None]:
        """Return cached weekly leaderboard, computing it when missing."""

        cached = await _load_cached_weekly_leaderboard()
        if cached:
            return cached

        entries = await self._compute_weekly_leaderboard()
        generated_at = datetime.now(UTC)
        await _store_weekly_leaderboard_cache(entries, generated_at)
        return entries, generated_at

    async def refresh_weekly_leaderboard(self) -> None:
        """Recalculate weekly leaderboard and persist the shared cache."""

        entries = await self._compute_weekly_leaderboard()
        generated_at = datetime.now(UTC)
        await _store_weekly_leaderboard_cache(entries, generated_at)

    async def get_weekly_leaderboard_for_player(
        self,
        player_id: UUID,
        username: str | None,
    ) -> tuple[list[dict[str, Any]], datetime | None]:
        """Return top leaderboard entries plus the current player."""

        entries, generated_at = await self.get_weekly_leaderboard_snapshot()

        lookup = {entry["player_id"]: entry for entry in entries}
        top_entries = entries[:WEEKLY_LEADERBOARD_LIMIT]

        player_entry = lookup.get(player_id)
        if player_entry is None:
            player_entry = {
                "player_id": player_id,
                "username": username or "Unknown Player",
                "total_costs": 0,
                "total_earnings": 0,
                "net_earnings": 0,
                "rank": None,
            }

        combined = [dict(entry) for entry in top_entries]
        if all(entry["player_id"] != player_entry["player_id"] for entry in combined):
            combined.append(dict(player_entry))

        for entry in combined:
            entry["is_current_player"] = entry["player_id"] == player_id

        return combined, generated_at

    async def _compute_weekly_leaderboard(self) -> list[dict]:
        """Calculate weekly net earnings for all active players."""

        window_start = datetime.now(UTC) - timedelta(days=7)

        prompt_completion = (
            select(
                Round.round_id.label("round_id"),
                func.max(PhrasesetActivity.created_at).label("completed_at"),
            )
            .join(PhrasesetActivity, PhrasesetActivity.prompt_round_id == Round.round_id)
            .where(
                Round.round_type == "prompt",
                PhrasesetActivity.activity_type == "prompt_submitted",
            )
            .group_by(Round.round_id)
        )

        copy_completion = (
            select(
                Round.round_id.label("round_id"),
                func.max(PhrasesetActivity.created_at).label("completed_at"),
            )
            .join(
                PhrasesetActivity,
                and_(
                    PhrasesetActivity.prompt_round_id == Round.prompt_round_id,
                    PhrasesetActivity.player_id == Round.player_id,
                    PhrasesetActivity.activity_type.in_(["copy1_submitted", "copy2_submitted"]),
                ),
            )
            .where(Round.round_type == "copy")
            .group_by(Round.round_id)
        )

        vote_completion = (
            select(
                Round.round_id.label("round_id"),
                func.max(PhrasesetActivity.created_at).label("completed_at"),
            )
            .join(
                PhrasesetActivity,
                and_(
                    PhrasesetActivity.phraseset_id == Round.phraseset_id,
                    PhrasesetActivity.player_id == Round.player_id,
                    PhrasesetActivity.activity_type == "vote_submitted",
                ),
            )
            .where(Round.round_type == "vote")
            .group_by(Round.round_id)
        )

        completion_union = union_all(prompt_completion, copy_completion, vote_completion).subquery()

        cost_subquery = (
            select(
                Round.player_id.label("player_id"),
                func.sum(Round.cost).label("total_costs"),
            )
            .join(completion_union, completion_union.c.round_id == Round.round_id)
            .where(
                Round.status == "submitted",
                completion_union.c.completed_at >= window_start,
            )
            .group_by(Round.player_id)
            .subquery()
        )

        phraseset_contributors = union_all(
            select(
                Phraseset.phraseset_id.label("phraseset_id"),
                Phraseset.prompt_round_id.label("round_id"),
            ),
            select(
                Phraseset.phraseset_id.label("phraseset_id"),
                Phraseset.copy_round_1_id.label("round_id"),
            ),
            select(
                Phraseset.phraseset_id.label("phraseset_id"),
                Phraseset.copy_round_2_id.label("round_id"),
            ),
        ).subquery()

        prize_earnings_entries = (
            select(
                Transaction.player_id.label("player_id"),
                Transaction.amount.label("amount"),
            )
            .join(Phraseset, Phraseset.phraseset_id == Transaction.reference_id)
            .join(
                phraseset_contributors,
                phraseset_contributors.c.phraseset_id == Phraseset.phraseset_id,
            )
            .join(Round, Round.round_id == phraseset_contributors.c.round_id)
            .join(completion_union, completion_union.c.round_id == Round.round_id)
            .where(
                Transaction.type == "prize_payout",
                Transaction.amount > 0,
                Transaction.player_id == Round.player_id,
                completion_union.c.completed_at >= window_start,
            )
        )

        vote_earnings_entries = (
            select(
                Transaction.player_id.label("player_id"),
                Transaction.amount.label("amount"),
            )
            .join(Vote, Vote.vote_id == Transaction.reference_id)
            .where(
                Transaction.type == "vote_payout",
                Transaction.amount > 0,
                Vote.created_at >= window_start,
            )
        )

        earnings_entries = union_all(prize_earnings_entries, vote_earnings_entries).subquery()

        earnings_subquery = (
            select(
                earnings_entries.c.player_id,
                func.sum(earnings_entries.c.amount).label("total_earnings"),
            )
            .group_by(earnings_entries.c.player_id)
            .subquery()
        )

        net_earnings_expression = (
            func.coalesce(earnings_subquery.c.total_earnings, 0)
            - func.coalesce(cost_subquery.c.total_costs, 0)
        )

        leaderboard_stmt = (
            select(
                Player.player_id,
                Player.username,
                func.coalesce(cost_subquery.c.total_costs, 0).label("total_costs"),
                func.coalesce(earnings_subquery.c.total_earnings, 0).label("total_earnings"),
                net_earnings_expression.label("net_earnings"),
            )
            .join(cost_subquery, cost_subquery.c.player_id == Player.player_id, isouter=True)
            .join(earnings_subquery, earnings_subquery.c.player_id == Player.player_id, isouter=True)
            .where(
                or_(cost_subquery.c.player_id.isnot(None), earnings_subquery.c.player_id.isnot(None)),
                ~Player.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"),
            )
            .order_by(net_earnings_expression.desc(), Player.username.asc())
        )

        result = await self.db.execute(leaderboard_stmt)

        entries: list[dict[str, Any]] = []
        for rank, row in enumerate(result.all(), start=1):
            entries.append(
                {
                    "player_id": row.player_id,
                    "username": row.username,
                    "total_costs": int(row.total_costs or 0),
                    "total_earnings": int(row.total_earnings or 0),
                    "net_earnings": int(row.net_earnings or 0),
                    "rank": rank,
                }
            )

        return entries

    @staticmethod
    def _empty_payout(phraseset: Phraseset) -> dict:
        """Return an empty payout structure when no data is available."""
        return {
            "original": {
                "points": 0,
                "payout": 0,
                "player_id": _placeholder_player_id(phraseset.phraseset_id, "prompt"),
                "phrase": phraseset.original_phrase,
            },
            "copy1": {
                "points": 0,
                "payout": 0,
                "player_id": _placeholder_player_id(phraseset.phraseset_id, "copy1"),
                "phrase": phraseset.copy_phrase_1,
            },
            "copy2": {
                "points": 0,
                "payout": 0,
                "player_id": _placeholder_player_id(phraseset.phraseset_id, "copy2"),
                "phrase": phraseset.copy_phrase_2,
            },
        }
