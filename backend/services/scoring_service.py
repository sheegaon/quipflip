"""Scoring and payout calculation service."""

from collections import defaultdict
import json
from datetime import UTC, datetime, timedelta
import logging
from typing import Any, Iterable
from uuid import UUID, uuid5

from sqlalchemy import and_, cast, func, or_, select, union_all, Integer, Float
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
WEEKLY_LEADERBOARD_CACHE_KEY = "leaderboard:weekly:v4"  # v4: split by role with win rates
AI_PLAYER_EMAIL_DOMAIN = "@quipflip.internal"
LEADERBOARD_ROLES = ["prompt", "copy", "voter"]


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


async def _load_cached_weekly_leaderboard() -> tuple[dict[str, list[dict[str, Any]]], datetime] | None:
    """Fetch cached role-based weekly leaderboard data from Redis, if available."""

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

        role_leaderboards: dict[str, list[dict[str, Any]]] = {}

        for role in LEADERBOARD_ROLES:
            entries: list[dict[str, Any]] = []
            for entry in payload.get(f"{role}_leaderboard", []):
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
            role_leaderboards[role] = entries

        if generated_at is None:
            return None

        return role_leaderboards, generated_at
    except Exception as exc:  # pragma: no cover - cache corruption fallback
        logger.error(f"Invalid data in weekly leaderboard cache: {exc}")
        return None


async def _store_weekly_leaderboard_cache(
    role_leaderboards: dict[str, list[dict[str, Any]]], generated_at: datetime
) -> None:
    """Persist role-based leaderboard results to Redis for reuse across workers."""

    client = _get_redis_client()
    if client is None:
        return

    payload: dict[str, Any] = {
        "generated_at": generated_at.isoformat(),
    }

    for role, entries in role_leaderboards.items():
        cache_entries: list[dict[str, Any]] = []
        for entry in entries:
            cache_entries.append(
                {
                    **entry,
                    "player_id": str(entry["player_id"]),
                }
            )
        payload[f"{role}_leaderboard"] = cache_entries

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

    async def get_weekly_leaderboard_snapshot(
        self,
    ) -> tuple[dict[str, list[dict[str, Any]]], datetime | None]:
        """Return cached role-based weekly leaderboards, computing them when missing."""

        cached = await _load_cached_weekly_leaderboard()
        if cached:
            return cached

        role_leaderboards = await self._compute_role_based_weekly_leaderboards()
        generated_at = datetime.now(UTC)
        await _store_weekly_leaderboard_cache(role_leaderboards, generated_at)
        return role_leaderboards, generated_at

    async def refresh_weekly_leaderboard(self) -> None:
        """Recalculate weekly leaderboard and persist the shared cache."""

        role_leaderboards = await self._compute_role_based_weekly_leaderboards()
        generated_at = datetime.now(UTC)
        await _store_weekly_leaderboard_cache(role_leaderboards, generated_at)

    async def get_weekly_leaderboard_for_player(
        self,
        player_id: UUID,
        username: str | None,
    ) -> tuple[dict[str, list[dict[str, Any]]], datetime | None]:
        """Return top leaderboard entries plus the current player for each role."""

        role_leaderboards, generated_at = await self.get_weekly_leaderboard_snapshot()

        result = {}

        for role in LEADERBOARD_ROLES:
            entries = role_leaderboards.get(role, [])
            lookup = {entry["player_id"]: entry for entry in entries}
            top_entries = entries[:WEEKLY_LEADERBOARD_LIMIT]

            player_entry = lookup.get(player_id)
            if player_entry is None:
                player_entry = {
                    "player_id": player_id,
                    "username": username or "Unknown Player",
                    "role": role,
                    "total_costs": 0,
                    "total_earnings": 0,
                    "net_earnings": 0,
                    "win_rate": 0.0,
                    "total_rounds": 0,
                    "rank": None,
                }

            combined = [dict(entry) for entry in top_entries]
            if all(entry["player_id"] != player_entry["player_id"] for entry in combined):
                combined.append(dict(player_entry))

            for entry in combined:
                entry["is_current_player"] = entry["player_id"] == player_id

            result[role] = combined

        return result, generated_at

    async def _compute_role_leaderboard(self, role: str) -> list[dict]:
        """Calculate weekly leaderboard for a specific role."""

        window_start = datetime.now(UTC) - timedelta(days=7)

        # Determine completion criteria based on role
        if role == "prompt":
            completion_query = (
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
        elif role == "copy":
            completion_query = (
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
        else:  # voter
            completion_query = (
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

        completion_subquery = completion_query.subquery()

        # Get costs and round counts for this role
        rounds_subquery = (
            select(
                Round.player_id.label("player_id"),
                func.sum(Round.cost).label("total_costs"),
                func.count(Round.round_id).label("total_rounds"),
            )
            .join(completion_subquery, completion_subquery.c.round_id == Round.round_id)
            .where(
                Round.status == "submitted",
                Round.round_type == role,
                completion_subquery.c.completed_at >= window_start,
            )
            .group_by(Round.player_id)
            .subquery()
        )

        # Get earnings for this role
        if role in ["prompt", "copy"]:
            # Prize payouts for prompt/copy roles
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

            earnings_query = (
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
                .join(completion_subquery, completion_subquery.c.round_id == Round.round_id)
                .where(
                    Transaction.type == "prize_payout",
                    Transaction.amount > 0,
                    Transaction.player_id == Round.player_id,
                    Round.round_type == role,
                    completion_subquery.c.completed_at >= window_start,
                )
            )
        else:  # voter
            # Vote payouts for voter role
            earnings_query = (
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

        earnings_subquery = (
            select(
                earnings_query.c.player_id,
                func.sum(earnings_query.c.amount).label("total_earnings"),
            )
            .group_by(earnings_query.c.player_id)
            .subquery()
        )

        # Calculate rounds with positive net earnings for win rate
        if role in ["prompt", "copy"]:
            # For prompt/copy: group by round and check if (earnings - cost) > 0
            round_performance = (
                select(
                    Round.player_id.label("player_id"),
                    Round.round_id.label("round_id"),
                    Round.cost.label("cost"),
                    func.coalesce(func.sum(Transaction.amount), 0).label("earnings"),
                )
                .join(completion_subquery, completion_subquery.c.round_id == Round.round_id)
                .join(
                    phraseset_contributors,
                    phraseset_contributors.c.round_id == Round.round_id,
                    isouter=True,
                )
                .join(
                    Phraseset,
                    Phraseset.phraseset_id == phraseset_contributors.c.phraseset_id,
                    isouter=True,
                )
                .join(
                    Transaction,
                    and_(
                        Transaction.reference_id == Phraseset.phraseset_id,
                        Transaction.player_id == Round.player_id,
                        Transaction.type == "prize_payout",
                    ),
                    isouter=True,
                )
                .where(
                    Round.status == "submitted",
                    Round.round_type == role,
                    completion_subquery.c.completed_at >= window_start,
                )
                .group_by(Round.player_id, Round.round_id, Round.cost)
                .subquery()
            )
        else:  # voter
            # For voter: group by round and check if earnings > cost
            round_performance = (
                select(
                    Round.player_id.label("player_id"),
                    Round.round_id.label("round_id"),
                    Round.cost.label("cost"),
                    func.coalesce(func.sum(Transaction.amount), 0).label("earnings"),
                )
                .join(completion_subquery, completion_subquery.c.round_id == Round.round_id)
                .join(
                    Vote,
                    and_(
                        Vote.round_id == Round.round_id,
                        Vote.player_id == Round.player_id,
                    ),
                    isouter=True,
                )
                .join(
                    Transaction,
                    and_(
                        Transaction.reference_id == Vote.vote_id,
                        Transaction.player_id == Round.player_id,
                        Transaction.type == "vote_payout",
                    ),
                    isouter=True,
                )
                .where(
                    Round.status == "submitted",
                    Round.round_type == "vote",
                    completion_subquery.c.completed_at >= window_start,
                )
                .group_by(Round.player_id, Round.round_id, Round.cost)
                .subquery()
            )

        wins_subquery = (
            select(
                round_performance.c.player_id,
                func.count(
                    func.nullif(
                        cast(round_performance.c.earnings > round_performance.c.cost, Integer), 0
                    )
                ).label("winning_rounds"),
            )
            .group_by(round_performance.c.player_id)
            .subquery()
        )

        net_earnings_expression = (
            func.coalesce(earnings_subquery.c.total_earnings, 0)
            - func.coalesce(rounds_subquery.c.total_costs, 0)
        )

        win_rate_expression = cast(
            func.coalesce(wins_subquery.c.winning_rounds, 0) * 100.0
            / func.nullif(rounds_subquery.c.total_rounds, 0),
            Float,
        )

        leaderboard_stmt = (
            select(
                Player.player_id,
                Player.username,
                func.coalesce(rounds_subquery.c.total_costs, 0).label("total_costs"),
                func.coalesce(earnings_subquery.c.total_earnings, 0).label("total_earnings"),
                net_earnings_expression.label("net_earnings"),
                func.coalesce(rounds_subquery.c.total_rounds, 0).label("total_rounds"),
                func.coalesce(win_rate_expression, 0.0).label("win_rate"),
            )
            .join(rounds_subquery, rounds_subquery.c.player_id == Player.player_id, isouter=True)
            .join(earnings_subquery, earnings_subquery.c.player_id == Player.player_id, isouter=True)
            .join(wins_subquery, wins_subquery.c.player_id == Player.player_id, isouter=True)
            .where(
                or_(rounds_subquery.c.player_id.isnot(None), earnings_subquery.c.player_id.isnot(None)),
                ~Player.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"),
            )
            .order_by(win_rate_expression.desc(), Player.username.asc())
        )

        result = await self.db.execute(leaderboard_stmt)

        entries: list[dict[str, Any]] = []
        for rank, row in enumerate(result.all(), start=1):
            entries.append(
                {
                    "player_id": row.player_id,
                    "username": row.username,
                    "role": role,
                    "total_costs": int(row.total_costs or 0),
                    "total_earnings": int(row.total_earnings or 0),
                    "net_earnings": int(row.net_earnings or 0),
                    "total_rounds": int(row.total_rounds or 0),
                    "win_rate": float(row.win_rate or 0.0),
                    "rank": rank,
                }
            )

        return entries

    async def _compute_role_based_weekly_leaderboards(self) -> dict[str, list[dict]]:
        """Calculate weekly leaderboards for all three roles concurrently."""
        import asyncio

        tasks = [self._compute_role_leaderboard(role) for role in LEADERBOARD_ROLES]
        results = await asyncio.gather(*tasks)

        return dict(zip(LEADERBOARD_ROLES, results))

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
