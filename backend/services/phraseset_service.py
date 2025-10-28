"""Service layer for phraseset tracking and summaries."""
from __future__ import annotations

from datetime import datetime, UTC
from typing import Iterable, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.player import Player
from backend.models.phraseset import Phraseset
from backend.models.result_view import ResultView
from backend.models.round import Round
from backend.models.vote import Vote
from backend.services.activity_service import ActivityService
from backend.services.scoring_service import ScoringService


class PhrasesetService:
    """Provide player-facing phraseset data with activity and payouts."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.activity_service = ActivityService(db)
        self.scoring_service = ScoringService(db)
        # Request-scoped cache to avoid re-querying _build_contributions multiple times
        # within a single request (e.g., dashboard endpoint calls it 3x)
        self._contributions_cache: dict[UUID, list[dict]] = {}

    def _invalidate_contributions_cache(self, player_id: UUID) -> None:
        """Invalidate cached contributions for a player after data changes."""
        self._contributions_cache.pop(player_id, None)

    async def get_player_phrasesets(
        self,
        player_id: UUID,
        role: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[list[dict], int]:
        """Return paginated phraseset summaries for a player."""
        contributions = await self._build_contributions(player_id)

        def role_filter(entry: dict) -> bool:
            if not role or role == "all":
                return True
            return entry["your_role"] == role

        STATUS_BUCKETS = {
            "in_progress": {"waiting_copies", "waiting_copy1", "active", "voting", "closing"},
            "voting": {"voting", "closing"},
            "finalized": {"finalized"},
            "abandoned": {"abandoned"},
        }

        def status_filter(entry: dict) -> bool:
            if not status or status == "all":
                return True
            bucket = STATUS_BUCKETS.get(status)
            if not bucket:
                return entry["status"] == status
            return entry["status"] in bucket

        filtered = [entry for entry in contributions if role_filter(entry) and status_filter(entry)]
        total = len(filtered)
        page = filtered[offset: offset + limit]
        return page, total

    async def get_phraseset_summary(self, player_id: UUID) -> dict:
        """Return dashboard summary metrics for a player."""
        contributions = await self._build_contributions(player_id)

        summary = {
            "in_progress": {
                "prompts": 0,
                "copies": 0,
                "unclaimed_prompts": 0,
                "unclaimed_copies": 0,
            },
            "finalized": {
                "prompts": 0,
                "copies": 0,
                "unclaimed_prompts": 0,
                "unclaimed_copies": 0,
            },
            "total_unclaimed_amount": 0,
        }

        for entry in contributions:
            is_finalized = entry["status"] == "finalized"
            bucket = "finalized" if is_finalized else "in_progress"
            role_key = "prompts" if entry["your_role"] == "prompt" else "copies"
            summary[bucket][role_key] += 1

            if is_finalized and not entry.get("result_viewed", False) and entry.get("your_payout"):
                summary["finalized"][f"unclaimed_{role_key}"] += 1
                summary["total_unclaimed_amount"] += entry["your_payout"] or 0
            if not is_finalized and not entry.get("result_viewed", False) and entry.get("your_payout"):
                summary["in_progress"][f"unclaimed_{role_key}"] += 1

        return summary

    async def get_unclaimed_results(self, player_id: UUID) -> dict:
        """Return finalized phrasesets with unviewed results."""
        contributions = await self._build_contributions(player_id)
        unclaimed: list[dict] = []
        total_amount = 0

        for entry in contributions:
            if entry["status"] != "finalized":
                continue
            if entry["phraseset_id"] is None:
                continue
            if entry.get("result_viewed"):
                continue
            if entry.get("your_payout") is None:
                continue

            unclaimed.append(
                {
                    "phraseset_id": entry["phraseset_id"],
                    "prompt_text": entry["prompt_text"],
                    "your_role": entry["your_role"],
                    "your_phrase": entry.get("your_phrase"),
                    "finalized_at": entry.get("finalized_at"),
                    "your_payout": entry.get("your_payout") or 0,
                }
            )
            total_amount += entry.get("your_payout") or 0

        return {
            "unclaimed": sorted(
                unclaimed,
                key=lambda item: item["finalized_at"] or datetime.now(UTC),
                reverse=True,
            ),
            "total_unclaimed_amount": total_amount,
        }

    async def get_phraseset_details(
        self,
        phraseset_id: UUID,
        player_id: UUID,
    ) -> dict:
        """Return full detail view for a phraseset the player contributed to."""
        phraseset = await self.db.get(Phraseset, phraseset_id)
        if not phraseset:
            raise ValueError("Phraseset not found")

        prompt_round, copy1_round, copy2_round = await self._load_contributor_rounds(phraseset)
        contributor_ids = {
            prompt_round.player_id,
            copy1_round.player_id,
            copy2_round.player_id,
        }

        if player_id not in contributor_ids:
            raise ValueError("Not a contributor to this phraseset")

        player_records = await self._load_players(contributor_ids)

        # Build contributor list
        contributors = [
            {
                "player_id": prompt_round.player_id,
                "username": player_records.get(prompt_round.player_id, {}).get("username", str(prompt_round.player_id)),
                "pseudonym": player_records.get(prompt_round.player_id, {}).get("pseudonym", "Unknown"),
                "is_you": prompt_round.player_id == player_id,
                "phrase": phraseset.original_phrase,
            },
            {
                "player_id": copy1_round.player_id,
                "username": player_records.get(copy1_round.player_id, {}).get("username", str(copy1_round.player_id)),
                "pseudonym": player_records.get(copy1_round.player_id, {}).get("pseudonym", "Unknown"),
                "is_you": copy1_round.player_id == player_id,
                "phrase": phraseset.copy_phrase_1,
            },
            {
                "player_id": copy2_round.player_id,
                "username": player_records.get(copy2_round.player_id, {}).get("username", str(copy2_round.player_id)),
                "pseudonym": player_records.get(copy2_round.player_id, {}).get("pseudonym", "Unknown"),
                "is_you": copy2_round.player_id == player_id,
                "phrase": phraseset.copy_phrase_2,
            },
        ]

        your_role, your_phrase = self._identify_player_role(
            player_id,
            phraseset,
            prompt_round,
            copy1_round,
            copy2_round,
        )

        result_view = await self._load_result_view(phraseset, player_id)
        payouts_cache: dict[UUID, dict] = {}
        your_payout = None
        result_viewed = result_view.result_viewed if result_view else False
        if phraseset.status == "finalized":
            payouts = await self._get_payouts_cached(phraseset, payouts_cache)
            your_payout = self._extract_player_payout(payouts, player_id)
            if result_view and result_view.payout_amount:
                your_payout = result_view.payout_amount

        # Votes and voters
        vote_rows = await self.db.execute(
            select(Vote)
            .where(Vote.phraseset_id == phraseset.phraseset_id)
            .order_by(Vote.created_at.asc())
        )
        votes = list(vote_rows.scalars().all())
        vote_player_ids = {vote.player_id for vote in votes}
        vote_player_records = await self._load_players(vote_player_ids, existing=player_records)

        votes_payload = [
            {
                "vote_id": vote.vote_id,
                "voter_id": vote.player_id,
                "voter_username": vote_player_records.get(vote.player_id, {}).get("username", str(vote.player_id)),
                "voter_pseudonym": vote_player_records.get(vote.player_id, {}).get("pseudonym", "Unknown"),
                "voted_phrase": vote.voted_phrase,
                "correct": vote.correct,
                "voted_at": self._ensure_utc(vote.created_at),
            }
            for vote in votes
        ]

        # Activity timeline
        activities = await self.activity_service.get_phraseset_activity(phraseset.phraseset_id)
        activity_player_ids = {act.player_id for act in activities if act.player_id}
        activity_players = await self._load_players(activity_player_ids, existing=vote_player_records)
        activity_payload = [
            {
                "activity_id": activity.activity_id,
                "activity_type": activity.activity_type,
                "created_at": self._ensure_utc(activity.created_at),
                "player_id": activity.player_id,
                "player_username": activity_players.get(activity.player_id, {}).get("username", str(activity.player_id)) if activity.player_id else None,
                "metadata": activity.payload or {},
            }
            for activity in activities
        ]

        results_payload = None
        if phraseset.status == "finalized":
            payouts = await self._get_payouts_cached(phraseset, payouts_cache)
            results_payload = {
                "vote_counts": self._count_votes(phraseset, votes),
                "payouts": {
                    role: {
                        "player_id": info["player_id"],
                        "payout": info["payout"],
                        "points": info["points"],
                    }
                    for role, info in payouts.items()
                },
                "total_pool": phraseset.total_pool,
            }

        return {
            "phraseset_id": phraseset.phraseset_id,
            "prompt_round_id": phraseset.prompt_round_id,
            "prompt_text": phraseset.prompt_text,
            "status": self._derive_status(prompt_round, phraseset),
            "original_phrase": phraseset.original_phrase,
            "copy_phrase_1": phraseset.copy_phrase_1,
            "copy_phrase_2": phraseset.copy_phrase_2,
            "contributors": contributors,
            "vote_count": phraseset.vote_count,
            "third_vote_at": self._ensure_utc(phraseset.third_vote_at),
            "fifth_vote_at": self._ensure_utc(phraseset.fifth_vote_at),
            "closes_at": self._ensure_utc(phraseset.closes_at),
            "votes": votes_payload,
            "total_pool": phraseset.total_pool,
            "results": results_payload,
            "your_role": your_role,
            "your_phrase": your_phrase,
            "your_payout": your_payout,
            "payout_claimed": result_viewed,
            "activity": activity_payload,
            "created_at": self._ensure_utc(phraseset.created_at),
            "finalized_at": self._ensure_utc(phraseset.finalized_at),
        }

    async def claim_prize(
        self,
        phraseset_id: UUID,
        player_id: UUID,
    ) -> dict:
        """Mark a finalized phraseset result as viewed (legacy endpoint for compatibility)."""
        phraseset = await self.db.get(Phraseset, phraseset_id)
        if not phraseset:
            raise ValueError("Phraseset not found")
        if phraseset.status != "finalized":
            raise ValueError("Phraseset not yet finalized")

        prompt_round, copy1_round, copy2_round = await self._load_contributor_rounds(phraseset)
        contributor_map = {
            prompt_round.player_id,
            copy1_round.player_id,
            copy2_round.player_id,
        }
        if player_id not in contributor_map:
            raise ValueError("Not a contributor to this phraseset")

        result_view = await self._load_result_view(phraseset, player_id, create_if_missing=True)
        already_viewed = result_view.result_viewed

        if not result_view.first_viewed_at:
            result_view.first_viewed_at = datetime.now(UTC)

        if not result_view.result_viewed:
            result_view.result_viewed = True
            result_view.result_viewed_at = datetime.now(UTC)
            await self.db.commit()
        else:
            await self.db.commit()

        player = await self.db.get(Player, player_id)
        if player:
            await self.db.refresh(player)

        # Invalidate cached contributions since result_viewed status changed
        self._invalidate_contributions_cache(player_id)

        return {
            "success": True,
            "amount": result_view.payout_amount,
            "new_balance": player.balance if player else 0,
            "already_claimed": already_viewed,  # For compatibility with frontend
        }

    async def is_contributor(self, phraseset_id: UUID, player_id: UUID) -> bool:
        """Return True if player contributed to the phraseset."""
        phraseset = await self.db.get(Phraseset, phraseset_id)
        if not phraseset:
            return False
        prompt_round, copy1_round, copy2_round = await self._load_contributor_rounds(phraseset)
        return player_id in {
            prompt_round.player_id,
            copy1_round.player_id,
            copy2_round.player_id,
        }

    # ---------------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------------

    async def _build_contributions(self, player_id: UUID) -> list[dict]:
        """Load prompt and copy contributions and derive summary fields.

        Results are cached per player_id for the lifetime of this service instance
        to avoid redundant queries within a single request.
        """
        # Check cache first
        if player_id in self._contributions_cache:
            return self._contributions_cache[player_id]

        # Build contributions if not cached
        prompt_result = await self.db.execute(
            select(Round)
            .where(Round.player_id == player_id)
            .where(Round.round_type == "prompt")
            .where(Round.submitted_phrase.is_not(None))
        )
        prompt_rounds = list(prompt_result.scalars().all())
        prompt_round_map = {prompt.round_id: prompt for prompt in prompt_rounds}

        copy_result = await self.db.execute(
            select(Round)
            .where(Round.player_id == player_id)
            .where(Round.round_type == "copy")
            .where(Round.status == "submitted")
        )
        copy_rounds = list(copy_result.scalars().all())

        copy_prompt_ids = {
            copy.prompt_round_id
            for copy in copy_rounds
            if copy.prompt_round_id is not None
        }
        missing_prompt_ids = copy_prompt_ids - set(prompt_round_map.keys())
        if missing_prompt_ids:
            missing_prompt_result = await self.db.execute(
                select(Round).where(Round.round_id.in_(list(missing_prompt_ids)))
            )
            for prompt in missing_prompt_result.scalars().all():
                prompt_round_map[prompt.round_id] = prompt

        all_prompt_ids = set(prompt_round_map.keys())
        if not all_prompt_ids:
            return []

        phraseset_result = await self.db.execute(
            select(Phraseset).where(Phraseset.prompt_round_id.in_(all_prompt_ids))
        )
        phrasesets = list(phraseset_result.scalars().all())
        phraseset_map = {phraseset.prompt_round_id: phraseset for phraseset in phrasesets}

        phraseset_ids = [phraseset.phraseset_id for phraseset in phrasesets]
        result_view_map: dict[UUID, ResultView] = {}
        if phraseset_ids:
            rv_result = await self.db.execute(
                select(ResultView)
                .where(ResultView.player_id == player_id)
                .where(ResultView.phraseset_id.in_(phraseset_ids))
            )
            result_view_map = {
                rv.phraseset_id: rv
                for rv in rv_result.scalars().all()
            }

        contributions: list[dict] = []
        payout_cache: dict[UUID, dict] = {}

        for prompt_round in prompt_rounds:
            phraseset = phraseset_map.get(prompt_round.round_id)
            result_view = result_view_map.get(phraseset.phraseset_id) if phraseset else None
            result_viewed = result_view.result_viewed if result_view else False
            your_payout = None
            if phraseset and phraseset.status == "finalized":
                payouts = await self._get_payouts_cached(phraseset, payout_cache)
                your_payout = self._extract_player_payout(payouts, prompt_round.player_id)
                if result_view and result_view.payout_amount:
                    your_payout = result_view.payout_amount

            contributions.append(
                {
                    "phraseset_id": phraseset.phraseset_id if phraseset else None,
                    "prompt_round_id": prompt_round.round_id,
                    "prompt_text": phraseset.prompt_text if phraseset else prompt_round.prompt_text,
                    "your_role": "prompt",
                    "your_phrase": prompt_round.submitted_phrase,
                    "status": self._derive_status(prompt_round, phraseset),
                    "created_at": self._ensure_utc(prompt_round.created_at),
                    "updated_at": self._determine_updated_at(prompt_round, phraseset),
                    "vote_count": phraseset.vote_count if phraseset else 0,
                    "third_vote_at": self._ensure_utc(phraseset.third_vote_at) if phraseset else None,
                    "fifth_vote_at": self._ensure_utc(phraseset.fifth_vote_at) if phraseset else None,
                    "finalized_at": self._ensure_utc(phraseset.finalized_at) if phraseset else None,
                    "has_copy1": bool(prompt_round.copy1_player_id),
                    "has_copy2": bool(prompt_round.copy2_player_id),
                    "your_payout": your_payout,
                    "result_viewed": result_viewed,
                    "new_activity_count": 0,
                }
            )

        for copy_round in copy_rounds:
            prompt_round = prompt_round_map.get(copy_round.prompt_round_id)
            phraseset = phraseset_map.get(copy_round.prompt_round_id)

            # Skip if phraseset exists but this copy round is not one of the actual contributors
            # This can happen when a player submitted a copy but was not selected for the final phraseset
            if phraseset:
                if copy_round.round_id not in {phraseset.copy_round_1_id, phraseset.copy_round_2_id}:
                    continue

            result_view = result_view_map.get(phraseset.phraseset_id) if phraseset else None
            result_viewed = result_view.result_viewed if result_view else False
            your_payout = None
            if phraseset and phraseset.status == "finalized":
                payouts = await self._get_payouts_cached(phraseset, payout_cache)
                your_payout = self._extract_player_payout(payouts, copy_round.player_id)
                if result_view and result_view.payout_amount:
                    your_payout = result_view.payout_amount

            contributions.append(
                {
                    "phraseset_id": phraseset.phraseset_id if phraseset else None,
                    "prompt_round_id": copy_round.prompt_round_id,
                    "prompt_text": phraseset.prompt_text if phraseset else (prompt_round.prompt_text if prompt_round else ""),
                    "your_role": "copy",
                    "your_phrase": copy_round.copy_phrase,
                    "status": self._derive_status(prompt_round, phraseset),
                    "created_at": self._ensure_utc(copy_round.created_at),
                    "updated_at": self._determine_updated_at(prompt_round, phraseset, fallback=copy_round.created_at),
                    "vote_count": phraseset.vote_count if phraseset else 0,
                    "third_vote_at": self._ensure_utc(phraseset.third_vote_at) if phraseset else None,
                    "fifth_vote_at": self._ensure_utc(phraseset.fifth_vote_at) if phraseset else None,
                    "finalized_at": self._ensure_utc(phraseset.finalized_at) if phraseset else None,
                    "has_copy1": bool(prompt_round.copy1_player_id) if prompt_round else bool(phraseset),
                    "has_copy2": bool(prompt_round.copy2_player_id) if prompt_round else bool(phraseset),
                    "your_payout": your_payout,
                    "result_viewed": result_viewed,
                    "new_activity_count": 0,
                }
            )

        # Sort descending by created_at
        contributions.sort(key=lambda entry: entry["created_at"] or datetime.now(UTC), reverse=True)

        # Cache the results for this request
        self._contributions_cache[player_id] = contributions

        return contributions

    async def _load_contributor_rounds(self, phraseset: Phraseset) -> tuple[Round, Round, Round]:
        """Load prompt and copy rounds for a phraseset."""
        prompt_round = await self.db.get(Round, phraseset.prompt_round_id)
        copy1_round = await self.db.get(Round, phraseset.copy_round_1_id)
        copy2_round = await self.db.get(Round, phraseset.copy_round_2_id)
        if not prompt_round or not copy1_round or not copy2_round:
            raise ValueError("Phraseset contributors missing")
        return prompt_round, copy1_round, copy2_round

    async def _load_result_view(
        self,
        phraseset: Phraseset,
        player_id: UUID,
        create_if_missing: bool = False,
    ) -> ResultView:
        """Fetch or optionally create a result view record."""
        result = await self.db.execute(
            select(ResultView)
            .where(ResultView.phraseset_id == phraseset.phraseset_id)
            .where(ResultView.player_id == player_id)
        )
        result_view = result.scalar_one_or_none()

        if create_if_missing and not result_view:
            payouts = await self.scoring_service.calculate_payouts(phraseset)
            payout_amount = self._extract_player_payout(payouts, player_id) or 0
            result_view = ResultView(
                view_id=uuid4(),
                phraseset_id=phraseset.phraseset_id,
                player_id=player_id,
                payout_amount=payout_amount,
                result_viewed=False,  # Updated to use result_viewed
            )
            self.db.add(result_view)
            await self.db.flush()

        return result_view

    async def _load_players(
        self,
        player_ids: Iterable[UUID],
        existing: Optional[dict] = None,
    ) -> dict[UUID, dict]:
        """Fetch usernames and pseudonyms for player IDs, merging into existing mapping."""
        mapping = dict(existing or {})
        ids = {pid for pid in player_ids if pid and pid not in mapping}
        if not ids:
            return mapping

        result = await self.db.execute(
            select(Player.player_id, Player.username, Player.pseudonym).where(Player.player_id.in_(ids))
        )
        for player_id, username, pseudonym in result.all():
            mapping[player_id] = {"username": username, "pseudonym": pseudonym}
        return mapping

    async def _get_payouts_cached(
        self,
        phraseset: Phraseset,
        cache: dict[UUID, dict],
    ) -> dict:
        """Calculate payouts with memoization for repeated access."""
        if phraseset.phraseset_id not in cache:
            cache[phraseset.phraseset_id] = await self.scoring_service.calculate_payouts(phraseset)
        return cache[phraseset.phraseset_id]

    def _extract_player_payout(self, payouts: dict, player_id: UUID) -> Optional[int]:
        """Get payout value for specific player from payout structure."""
        for info in payouts.values():
            if info["player_id"] == player_id:
                return info["payout"]
        return None

    def _identify_player_role(
        self,
        player_id: UUID,
        phraseset: Phraseset,
        prompt_round: Round,
        copy1_round: Round,
        copy2_round: Round,
    ) -> tuple[str, Optional[str]]:
        """Determine player's role and phrase in the phraseset."""
        if player_id == prompt_round.player_id:
            return "prompt", phraseset.original_phrase
        if player_id == copy1_round.player_id:
            return "copy", phraseset.copy_phrase_1
        if player_id == copy2_round.player_id:
            return "copy", phraseset.copy_phrase_2
        return "copy", None

    def _derive_status(self, prompt_round: Optional[Round], phraseset: Optional[Phraseset]) -> str:
        """Normalize status values between prompt rounds and phrasesets."""
        if phraseset:
            mapping = {
                "open": "voting",
                "closing": "closing",
                "closed": "closing",
                "finalized": "finalized",
            }
            return mapping.get(phraseset.status, phraseset.status)

        if prompt_round and prompt_round.phraseset_status:
            mapping = {
                "active": "voting",
            }
            return mapping.get(prompt_round.phraseset_status, prompt_round.phraseset_status)

        return "waiting_copies"

    def _determine_updated_at(
        self,
        prompt_round: Optional[Round],
        phraseset: Optional[Phraseset],
        fallback: Optional[datetime] = None,
    ) -> Optional[datetime]:
        """Derive an updated timestamp for summary ordering."""
        candidates = [
            self._ensure_utc(phraseset.finalized_at) if phraseset else None,
            self._ensure_utc(phraseset.closes_at) if phraseset else None,
            self._ensure_utc(phraseset.created_at) if phraseset else None,
            self._ensure_utc(prompt_round.created_at) if prompt_round else None,
            self._ensure_utc(fallback) if fallback else None,
        ]
        for value in candidates:
            if value:
                return value
        return None

    def _count_votes(self, phraseset: Phraseset, votes: list[Vote]) -> dict:
        """Aggregate vote counts by phrase for detail view."""
        counts = {
            phraseset.original_phrase: 0,
            phraseset.copy_phrase_1: 0,
            phraseset.copy_phrase_2: 0,
        }
        for vote in votes:
            if vote.voted_phrase in counts:
                counts[vote.voted_phrase] += 1
        return counts

    def _ensure_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Ensure datetimes are timezone-aware in UTC."""
        if not dt:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
