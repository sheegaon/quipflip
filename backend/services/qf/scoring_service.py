"""Scoring and payout calculation service."""

import asyncio
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

from backend.models.qf.phraseset import Phraseset
from backend.models.qf.phraseset_activity import PhrasesetActivity
from backend.models.qf.player import QFPlayer
from backend.models.qf.transaction import QFTransaction
from backend.models.qf.vote import Vote
from backend.models.qf.round import Round
from backend.services.ai.ai_service import AI_PLAYER_EMAIL_DOMAIN
from backend.config import get_settings

logger = logging.getLogger(__name__)


settings = get_settings()


PLACEHOLDER_PLAYER_NAMESPACE = UUID("6c057f58-7199-43ff-b4fc-17b77df5e6a2")
WEEKLY_LEADERBOARD_LIMIT = 5
WEEKLY_LEADERBOARD_CACHE_KEY = "leaderboard:weekly:v5"  # v5: added gross earnings category
ALLTIME_LEADERBOARD_LIMIT = 10
ALLTIME_LEADERBOARD_CACHE_KEY = "leaderboard:alltime:v2"  # v2: added gross earnings category
LEADERBOARD_ROLES = ["prompt", "copy", "voter"]
GROSS_EARNINGS_LEADERBOARD_LIMIT_WEEKLY = 10
GROSS_EARNINGS_LEADERBOARD_LIMIT_ALLTIME = 20


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


def _normalize_cached_entries(entries: list[dict[str, Any]], entry_type: str) -> list[dict[str, Any]]:
    """Normalize cached leaderboard entries by converting player_id strings to UUIDs.

    Args:
        entries: List of cached leaderboard entries with string player_ids
        entry_type: Description of entry type for error logging (e.g., "role", "gross earnings")

    Returns:
        List of normalized entries with UUID player_ids
    """
    normalized_entries: list[dict[str, Any]] = []
    for entry in entries:
        normalized = dict(entry)
        if "player_id" in normalized:
            try:
                normalized["player_id"] = UUID(str(normalized["player_id"]))
            except Exception:
                logger.error(
                    f"Skipping cached {entry_type} entry with invalid player_id: {normalized.get('player_id')}"
                )
                continue
        normalized_entries.append(normalized)
    return normalized_entries


async def _load_cached_leaderboard(cache_key: str, cache_type: str) -> tuple[dict[str, list[dict[str, Any]]], datetime] | None:
    """Fetch cached role-based leaderboard data from Redis, if available.

    Args:
        cache_key: The Redis cache key to fetch from
        cache_type: Type description for logging (e.g., "weekly", "all-time")
    """
    client = _get_redis_client()
    if client is None:
        return None

    try:
        raw_value = await client.get(cache_key)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Failed to read {cache_type} leaderboard cache: {exc}")
        return None

    if not raw_value:
        return None

    try:
        payload = json.loads(raw_value)
        generated_at_raw = payload.get("generated_at")
        generated_at = datetime.fromisoformat(generated_at_raw) if generated_at_raw else None

        role_leaderboards: dict[str, list[dict[str, Any]]] = {}

        # Load role-based leaderboards
        for role in LEADERBOARD_ROLES:
            raw_entries = payload.get(f"{role}_leaderboard", [])
            role_leaderboards[role] = _normalize_cached_entries(raw_entries, f"{role} leaderboard")

        # Load gross earnings leaderboard
        gross_raw_entries = payload.get("gross_earnings_leaderboard", [])
        role_leaderboards["gross_earnings"] = _normalize_cached_entries(gross_raw_entries, "gross earnings")

        if generated_at is None:
            return None

        return role_leaderboards, generated_at
    except Exception as exc:  # pragma: no cover - cache corruption fallback
        logger.error(f"Invalid data in {cache_type} leaderboard cache: {exc}")
        return None


async def _store_leaderboard_cache(
    role_leaderboards: dict[str, list[dict[str, Any]]],
    generated_at: datetime,
    cache_key: str,
    cache_type: str,
    expiration_seconds: int,
) -> None:
    """Persist role-based leaderboard results to Redis for reuse across workers.

    Args:
        role_leaderboards: Dictionary of role names to leaderboard entries (includes 'gross_earnings')
        generated_at: Timestamp when the leaderboard was generated
        cache_key: The Redis cache key to store to
        cache_type: Type description for logging (e.g., "weekly", "all-time")
        expiration_seconds: Cache TTL in seconds
    """
    client = _get_redis_client()
    if client is None:
        return

    payload: dict[str, Any] = {
        "generated_at": generated_at.isoformat(),
    }

    # Map leaderboard types to their cache payload keys
    leaderboard_mappings = {
        **{role: f"{role}_leaderboard" for role in LEADERBOARD_ROLES},
        "gross_earnings": "gross_earnings_leaderboard",
    }

    # Store all leaderboards using the mapping
    for leaderboard_type, payload_key in leaderboard_mappings.items():
        if leaderboard_type in role_leaderboards:
            cache_entries: list[dict[str, Any]] = []
            for entry in role_leaderboards[leaderboard_type]:
                cache_entries.append(
                    {
                        **entry,
                        "player_id": str(entry["player_id"]),
                    }
                )
            payload[payload_key] = cache_entries

    try:
        await client.set(cache_key, json.dumps(payload), ex=expiration_seconds)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Failed to write {cache_type} leaderboard cache: {exc}")


async def _load_cached_weekly_leaderboard() -> tuple[dict[str, list[dict[str, Any]]], datetime] | None:
    """Fetch cached role-based weekly leaderboard data from Redis, if available."""
    return await _load_cached_leaderboard(WEEKLY_LEADERBOARD_CACHE_KEY, "weekly")


async def _store_weekly_leaderboard_cache(
    role_leaderboards: dict[str, list[dict[str, Any]]], generated_at: datetime
) -> None:
    """Persist role-based weekly leaderboard results to Redis for reuse across workers."""
    await _store_leaderboard_cache(role_leaderboards, generated_at, WEEKLY_LEADERBOARD_CACHE_KEY, "weekly", 3600)


async def _load_cached_alltime_leaderboard() -> tuple[dict[str, list[dict[str, Any]]], datetime] | None:
    """Fetch cached role-based all-time leaderboard data from Redis, if available."""
    return await _load_cached_leaderboard(ALLTIME_LEADERBOARD_CACHE_KEY, "all-time")


async def _store_alltime_leaderboard_cache(
    role_leaderboards: dict[str, list[dict[str, Any]]], generated_at: datetime
) -> None:
    """Persist role-based all-time leaderboard results to Redis for reuse across workers."""
    await _store_leaderboard_cache(role_leaderboards, generated_at, ALLTIME_LEADERBOARD_CACHE_KEY, "all-time", 7200)


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

        logger.debug(
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

    def _add_current_player_to_leaderboard(
        self,
        entries: list[dict[str, Any]],
        top_limit: int,
        player_id: UUID,
        username: str | None,
        default_entry: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Add current player to leaderboard if not already in top entries.

        Args:
            entries: All leaderboard entries
            top_limit: Maximum number of top entries to include
            player_id: ID of current player
            username: Username of current player
            default_entry: Default entry structure if player not found

        Returns:
            List of leaderboard entries with current player included
        """
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

    async def get_weekly_leaderboard_for_player(
        self,
        player_id: UUID,
        username: str | None,
    ) -> tuple[dict[str, list[dict[str, Any]]], datetime | None]:
        """Return top leaderboard entries plus the current player for each role and gross earnings."""

        role_leaderboards, generated_at = await self.get_weekly_leaderboard_snapshot()

        result = {}

        # Handle role-based leaderboards
        for role in LEADERBOARD_ROLES:
            entries = role_leaderboards.get(role, [])
            result[role] = self._add_current_player_to_leaderboard(
                entries,
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
                },
            )

        # Handle gross earnings leaderboard (vault-based)
        gross_entries = role_leaderboards.get("gross_earnings", [])
        result["gross_earnings"] = self._add_current_player_to_leaderboard(
            gross_entries,
            GROSS_EARNINGS_LEADERBOARD_LIMIT_WEEKLY,
            player_id,
            username,
            {
                "vault_balance": 0,
                "total_rounds": 0,
                "rank": None,
            },
        )

        return result, generated_at

    def _build_completion_subquery(self, role: str):
        """Build completion criteria subquery based on role.

        Args:
            role: The role type ('prompt', 'copy', or 'voter')

        Returns:
            A SQLAlchemy subquery for completion criteria
        """
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

        return completion_query.subquery()

    def _build_rounds_subquery(self, role: str, completion_subquery, start_date: datetime | None):
        """Build rounds and costs subquery.

        Args:
            role: The role type ('prompt', 'copy', or 'voter')
            completion_subquery: The completion criteria subquery
            start_date: Optional start date for filtering (None for all-time)

        Returns:
            A SQLAlchemy subquery for rounds and costs
        """
        where_conditions = [
            Round.status == "submitted",
            Round.round_type == role,
        ]
        if start_date:
            where_conditions.append(completion_subquery.c.completed_at >= start_date)

        return (
            select(
                Round.player_id.label("player_id"),
                func.sum(Round.cost).label("total_costs"),
                func.count(Round.round_id).label("total_rounds"),
            )
            .join(completion_subquery, completion_subquery.c.round_id == Round.round_id)
            .where(*where_conditions)
            .group_by(Round.player_id)
            .subquery()
        )

    def _build_phraseset_contributors_subquery(self):
        """Build subquery for phraseset contributors (prompt/copy roles).

        Returns:
            A SQLAlchemy subquery mapping phrasesets to rounds
        """
        return union_all(
            select(
                Phraseset.phraseset_id.label("phraseset_id"),
                Phraseset.prompt_round_id.label("round_id"),
            ).select_from(Phraseset),
            select(
                Phraseset.phraseset_id.label("phraseset_id"),
                Phraseset.copy_round_1_id.label("round_id"),
            ).select_from(Phraseset),
            select(
                Phraseset.phraseset_id.label("phraseset_id"),
                Phraseset.copy_round_2_id.label("round_id"),
            ).select_from(Phraseset),
        ).subquery()

    def _build_earnings_subquery(self, role: str, completion_subquery, start_date: datetime | None):
        """Build earnings subquery based on role.

        Args:
            role: The role type ('prompt', 'copy', or 'voter')
            completion_subquery: The completion criteria subquery
            start_date: Optional start date for filtering (None for all-time)

        Returns:
            A SQLAlchemy subquery for earnings
        """
        if role in ["prompt", "copy"]:
            # Prize payouts for prompt/copy roles
            phraseset_contributors = self._build_phraseset_contributors_subquery()

            where_conditions = [
                QFTransaction.type == "prize_payout",
                QFTransaction.amount > 0,
                QFTransaction.player_id == Round.player_id,
                Round.round_type == role,
            ]
            if start_date:
                where_conditions.append(completion_subquery.c.completed_at >= start_date)

            earnings_query = (
                select(
                    QFTransaction.player_id.label("player_id"),
                    QFTransaction.amount.label("amount"),
                )
                .join(Phraseset, Phraseset.phraseset_id == QFTransaction.reference_id)
                .join(
                    phraseset_contributors,
                    phraseset_contributors.c.phraseset_id == Phraseset.phraseset_id,
                )
                .join(Round, Round.round_id == phraseset_contributors.c.round_id)
                .join(completion_subquery, completion_subquery.c.round_id == Round.round_id)
                .where(*where_conditions)
            )
        else:  # voter
            # Vote payouts for voter role
            where_conditions = [
                QFTransaction.type == "vote_payout",
                QFTransaction.amount > 0,
            ]
            if start_date:
                where_conditions.append(Vote.created_at >= start_date)

            earnings_query = (
                select(
                    QFTransaction.player_id.label("player_id"),
                    QFTransaction.amount.label("amount"),
                )
                .join(Vote, Vote.vote_id == QFTransaction.reference_id)
                .where(*where_conditions)
            )

        return (
            select(
                earnings_query.c.player_id,
                func.sum(earnings_query.c.amount).label("total_earnings"),
            )
            .group_by(earnings_query.c.player_id)
            .subquery()
        )

    def _build_wins_subquery(self, role: str, completion_subquery, start_date: datetime | None):
        """Build win rate calculation subquery.

        Args:
            role: The role type ('prompt', 'copy', or 'voter')
            completion_subquery: The completion criteria subquery
            start_date: Optional start date for filtering (None for all-time)

        Returns:
            A SQLAlchemy subquery for win counts
        """
        where_conditions = [
            Round.status == "submitted",
            Round.round_type == role,
        ]
        if start_date:
            where_conditions.append(completion_subquery.c.completed_at >= start_date)

        if role in ["prompt", "copy"]:
            # For prompt/copy: group by round and check if (earnings - cost) > 0
            phraseset_contributors = self._build_phraseset_contributors_subquery()

            round_performance = (
                select(
                    Round.player_id.label("player_id"),
                    Round.round_id.label("round_id"),
                    Round.cost.label("cost"),
                    func.coalesce(func.sum(QFTransaction.amount), 0).label("earnings"),
                )
                .join(completion_subquery, completion_subquery.c.round_id == Round.round_id)
                .join(
                    phraseset_contributors,
                    phraseset_contributors.c.round_id == Round.round_id,
                    isouter=True,
                )
                .join(
                    QFTransaction,
                    and_(
                        QFTransaction.reference_id == phraseset_contributors.c.phraseset_id,
                        QFTransaction.player_id == Round.player_id,
                        QFTransaction.type == "prize_payout",
                    ),
                    isouter=True,
                )
                .where(*where_conditions)
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
                    func.coalesce(func.sum(QFTransaction.amount), 0).label("earnings"),
                )
                .join(completion_subquery, completion_subquery.c.round_id == Round.round_id)
                .join(
                    Vote,
                    and_(
                        Vote.phraseset_id == Round.phraseset_id,
                        Vote.player_id == Round.player_id,
                    ),
                )
                .join(
                    QFTransaction,
                    and_(
                        QFTransaction.reference_id == Vote.vote_id,
                        QFTransaction.player_id == Round.player_id,
                        QFTransaction.type == "vote_payout",
                    ),
                    isouter=True,
                )
                .where(*where_conditions)
                .group_by(Round.player_id, Round.round_id, Round.cost)
                .subquery()
            )

        return (
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

    async def _compute_role_leaderboard(self, role: str, start_date: datetime | None = None) -> list[dict]:
        """Calculate leaderboard for a specific role.

        Args:
            role: The role type ('prompt', 'copy', or 'voter')
            start_date: Optional start date for filtering (None for all-time, or datetime for weekly)

        Returns:
            List of leaderboard entries with rankings
        """
        # Build all subqueries using helper methods
        completion_subquery = self._build_completion_subquery(role)
        rounds_subquery = self._build_rounds_subquery(role, completion_subquery, start_date)
        earnings_subquery = self._build_earnings_subquery(role, completion_subquery, start_date)
        wins_subquery = self._build_wins_subquery(role, completion_subquery, start_date)

        # Build expressions for final query
        net_earnings_expression = (
            func.coalesce(earnings_subquery.c.total_earnings, 0)
            - func.coalesce(rounds_subquery.c.total_costs, 0)
        )

        win_rate_expression = cast(
            func.coalesce(wins_subquery.c.winning_rounds, 0) * 100.0
            / func.nullif(rounds_subquery.c.total_rounds, 0),
            Float,
        )

        # Build and execute final leaderboard query
        leaderboard_stmt = (
            select(
                QFPlayer.player_id,
                QFPlayer.username,
                func.coalesce(rounds_subquery.c.total_costs, 0).label("total_costs"),
                func.coalesce(earnings_subquery.c.total_earnings, 0).label("total_earnings"),
                net_earnings_expression.label("net_earnings"),
                func.coalesce(rounds_subquery.c.total_rounds, 0).label("total_rounds"),
                func.coalesce(win_rate_expression, 0.0).label("win_rate"),
            )
            .join(rounds_subquery, rounds_subquery.c.player_id == QFPlayer.player_id, isouter=True)
            .join(earnings_subquery, earnings_subquery.c.player_id == QFPlayer.player_id, isouter=True)
            .join(wins_subquery, wins_subquery.c.player_id == QFPlayer.player_id, isouter=True)
            .where(
                or_(rounds_subquery.c.player_id.isnot(None), earnings_subquery.c.player_id.isnot(None)),
                ~QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"),
            )
            .order_by(win_rate_expression.desc(), QFPlayer.username.asc())
        )

        result = await self.db.execute(leaderboard_stmt)

        # Format results
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
        """Calculate weekly leaderboards for all three roles plus gross earnings concurrently."""
        window_start = datetime.now(UTC) - timedelta(days=7)
        tasks = [self._compute_role_leaderboard(role, window_start) for role in LEADERBOARD_ROLES]
        tasks.append(self._compute_gross_earnings_leaderboard(window_start))
        results = await asyncio.gather(*tasks)

        leaderboards = dict(zip(LEADERBOARD_ROLES, results[:-1]))
        leaderboards["gross_earnings"] = results[-1]
        return leaderboards

    async def get_alltime_leaderboard_snapshot(
        self,
    ) -> tuple[dict[str, list[dict[str, Any]]], datetime | None]:
        """Return cached role-based all-time leaderboards, computing them when missing."""

        cached = await _load_cached_alltime_leaderboard()
        if cached:
            return cached

        role_leaderboards = await self._compute_role_based_alltime_leaderboards()
        generated_at = datetime.now(UTC)
        await _store_alltime_leaderboard_cache(role_leaderboards, generated_at)
        return role_leaderboards, generated_at

    async def refresh_alltime_leaderboard(self) -> None:
        """Recalculate all-time leaderboard and persist the shared cache."""

        role_leaderboards = await self._compute_role_based_alltime_leaderboards()
        generated_at = datetime.now(UTC)
        await _store_alltime_leaderboard_cache(role_leaderboards, generated_at)

    async def get_alltime_leaderboard_for_player(
        self,
        player_id: UUID,
        username: str | None,
    ) -> tuple[dict[str, list[dict[str, Any]]], datetime | None]:
        """Return top all-time leaderboard entries plus the current player for each role and gross earnings."""

        role_leaderboards, generated_at = await self.get_alltime_leaderboard_snapshot()

        result = {}

        # Handle role-based leaderboards
        for role in LEADERBOARD_ROLES:
            entries = role_leaderboards.get(role, [])
            result[role] = self._add_current_player_to_leaderboard(
                entries,
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
                },
            )

        # Handle gross earnings leaderboard (vault-based)
        gross_entries = role_leaderboards.get("gross_earnings", [])
        result["gross_earnings"] = self._add_current_player_to_leaderboard(
            gross_entries,
            GROSS_EARNINGS_LEADERBOARD_LIMIT_ALLTIME,
            player_id,
            username,
            {
                "vault_balance": 0,
                "total_rounds": 0,
                "rank": None,
            },
        )

        return result, generated_at

    async def _compute_role_based_alltime_leaderboards(self) -> dict[str, list[dict]]:
        """Calculate all-time leaderboards for all three roles plus gross earnings concurrently."""
        tasks = [self._compute_role_leaderboard(role, start_date=None) for role in LEADERBOARD_ROLES]
        tasks.append(self._compute_gross_earnings_leaderboard(start_date=None))
        results = await asyncio.gather(*tasks)

        leaderboards = dict(zip(LEADERBOARD_ROLES, results[:-1]))
        leaderboards["gross_earnings"] = results[-1]
        return leaderboards

    async def _compute_gross_earnings_leaderboard(self, start_date: datetime | None = None) -> list[dict]:
        """Calculate leaderboard ranking all players by vault balance.

        All-time leaderboard ranks by total vault balance.
        Weekly leaderboard ranks by change in vault balance over the past week.

        Args:
            start_date: Optional start date for filtering (None for all-time, datetime for weekly)

        Returns:
            List of leaderboard entries sorted by vault balance/change
        """
        # Calculate total rounds completed per player across all roles
        completion_conditions = [
            Round.status == "submitted",
        ]
        if start_date:
            # Filter rounds by creation date as a proxy for completion
            completion_conditions.append(Round.created_at >= start_date)

        rounds_stmt = (
            select(
                Round.player_id.label("player_id"),
                func.count(Round.round_id).label("total_rounds"),
            )
            .where(*completion_conditions)
            .group_by(Round.player_id)
            .subquery()
        )

        if start_date:
            # Weekly leaderboard: rank by change in vault balance
            # Calculate vault balance change by summing vault transactions since start_date
            vault_change_stmt = (
                select(
                    QFTransaction.player_id.label("player_id"),
                    func.sum(QFTransaction.amount).label("vault_change"),
                )
                .where(
                    QFTransaction.wallet_type == "vault",
                    QFTransaction.created_at >= start_date,
                )
                .group_by(QFTransaction.player_id)
                .subquery()
            )

            leaderboard_stmt = (
                select(
                    QFPlayer.player_id,
                    QFPlayer.username,
                    func.coalesce(vault_change_stmt.c.vault_change, 0).label("gross_earnings"),
                    func.coalesce(rounds_stmt.c.total_rounds, 0).label("total_rounds"),
                )
                .join(vault_change_stmt, vault_change_stmt.c.player_id == QFPlayer.player_id)
                .join(rounds_stmt, rounds_stmt.c.player_id == QFPlayer.player_id, isouter=True)
                .where(
                    ~QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"),
                    vault_change_stmt.c.vault_change > 0,  # Only show players with positive vault change
                )
                .group_by(QFPlayer.player_id, QFPlayer.username, vault_change_stmt.c.vault_change, rounds_stmt.c.total_rounds)
                .order_by(vault_change_stmt.c.vault_change.desc(), QFPlayer.username.asc())
            )
        else:
            # All-time leaderboard: rank by total vault balance
            leaderboard_stmt = (
                select(
                    QFPlayer.player_id,
                    QFPlayer.username,
                    QFPlayer.vault.label("gross_earnings"),
                    func.coalesce(rounds_stmt.c.total_rounds, 0).label("total_rounds"),
                )
                .join(rounds_stmt, rounds_stmt.c.player_id == QFPlayer.player_id, isouter=True)
                .where(
                    ~QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"),
                    QFPlayer.vault > 0,  # Only show players with non-zero vault
                )
                .order_by(QFPlayer.vault.desc(), QFPlayer.username.asc())
            )

        result = await self.db.execute(leaderboard_stmt)

        # Format results
        entries: list[dict[str, Any]] = []
        for rank, row in enumerate(result.all(), start=1):
            entries.append(
                {
                    "player_id": row.player_id,
                    "username": row.username,
                    "vault_balance": int(row.gross_earnings or 0),
                    "total_rounds": int(row.total_rounds or 0),
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
