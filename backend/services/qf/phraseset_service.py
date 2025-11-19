"""Service layer for phraseset tracking and summaries."""
from __future__ import annotations
import logging
from datetime import datetime, UTC
from typing import Iterable, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.qf.player import QFPlayer
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.result_view import QFResultView
from backend.models.qf.round import Round
from backend.models.qf.vote import Vote
from backend.services.qf.phraseset_activity_service import ActivityService
from backend.services.qf.scoring_service import ScoringService
from backend.services.qf.helpers import upsert_result_view
from backend.services.ai.ai_service import AI_PLAYER_EMAIL_DOMAIN

logger = logging.getLogger(__name__)


class PhrasesetService:
    """Provide player-facing phraseset data with activity and payouts."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.activity_service = ActivityService(db)
        self.scoring_service = ScoringService(db)
        # Request-scoped cache to avoid re-querying _build_contributions multiple times
        # within a single request (e.g., dashboard endpoint calls it 3x)
        self._contributions_cache: dict[UUID, list[dict]] = {}
        # Request-scoped cache so we only calculate payouts for a phraseset once
        self._payouts_cache: dict[UUID, dict] = {}

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
            # Skip vote contributions - they don't appear in unclaimed results
            if entry["your_role"] == "vote":
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
        """Return full detail view for a phraseset the player contributed to or voted on."""
        phraseset = await self.db.get(Phraseset, phraseset_id)
        if not phraseset:
            raise ValueError("Phraseset not found")

        prompt_round, copy1_round, copy2_round = await self._load_contributor_rounds(phraseset)
        contributor_ids = {
            prompt_round.player_id,
            copy1_round.player_id,
            copy2_round.player_id,
        }

        # Check if player is a contributor or voter
        is_contributor = player_id in contributor_ids
        is_voter = False
        if not is_contributor:
            # Check if player has voted on this phraseset
            voter_check = await self.db.execute(
                select(Vote)
                .where(Vote.phraseset_id == phraseset_id)
                .where(Vote.player_id == player_id)
            )
            is_voter = voter_check.scalar_one_or_none() is not None

        if not is_contributor and not is_voter:
            raise ValueError("Not a contributor or voter for this phraseset")

        player_records = await self._load_players(contributor_ids)

        # Build contributor list
        contributors = [
            {
                "round_id": prompt_round.round_id,
                "player_id": prompt_round.player_id,
                "username": player_records.get(prompt_round.player_id, {}).get("username", str(prompt_round.player_id)),
                "is_you": prompt_round.player_id == player_id,
                "is_ai": player_records.get(prompt_round.player_id, {}).get("is_ai", False),
                "phrase": phraseset.original_phrase,
            },
            {
                "round_id": copy1_round.round_id,
                "player_id": copy1_round.player_id,
                "username": player_records.get(copy1_round.player_id, {}).get("username", str(copy1_round.player_id)),
                "is_you": copy1_round.player_id == player_id,
                "is_ai": player_records.get(copy1_round.player_id, {}).get("is_ai", False),
                "phrase": phraseset.copy_phrase_1,
            },
            {
                "round_id": copy2_round.round_id,
                "player_id": copy2_round.player_id,
                "username": player_records.get(copy2_round.player_id, {}).get("username", str(copy2_round.player_id)),
                "is_you": copy2_round.player_id == player_id,
                "is_ai": player_records.get(copy2_round.player_id, {}).get("is_ai", False),
                "phrase": phraseset.copy_phrase_2,
            },
        ]

        # Votes and voters (load early to check if player is a voter)
        vote_rows = await self.db.execute(
            select(Vote)
            .where(Vote.phraseset_id == phraseset.phraseset_id)
            .order_by(Vote.created_at.asc())
        )
        votes = list(vote_rows.scalars().all())
        player_vote = next((v for v in votes if v.player_id == player_id), None)

        your_role, your_phrase = self._identify_player_role(
            player_id,
            phraseset,
            prompt_round,
            copy1_round,
            copy2_round,
            player_vote,
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
        elif is_voter and player_vote:
            # For voters, use the payout from the vote record
            your_payout = player_vote.payout
        vote_player_ids = {vote.player_id for vote in votes}
        vote_player_records = await self._load_players(vote_player_ids, existing=player_records)

        votes_payload = [
            {
                "vote_id": vote.vote_id,
                "voter_id": vote.player_id,
                "voter_username": vote_player_records.get(vote.player_id, {}).get("username", str(vote.player_id)),
                "is_ai": vote_player_records.get(vote.player_id, {}).get("is_ai", False),
                "voted_phrase": vote.voted_phrase,
                "correct": vote.correct,
                "voted_at": self._ensure_utc(vote.created_at),
            }
            for vote in votes
        ]

        # Activity timeline
        activities = await self.activity_service.get_phraseset_activity(phraseset.phraseset_id)
        activity_player_ids = {act.get("player_id") for act in activities if act.get("player_id")}
        activity_players = await self._load_players(activity_player_ids, existing=vote_player_records)
        activity_payload = [
            {
                "activity_id": activity["activity_id"],
                "activity_type": activity["activity_type"],
                "created_at": self._ensure_utc(activity["created_at"]),
                "player_id": activity.get("player_id"),
                "player_username": activity_players.get(activity.get("player_id"), {}).get("username", str(activity.get("player_id"))) if activity.get("player_id") else None,
                "metadata": activity.get("metadata", {}),
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
            "copy_round_1_id": phraseset.copy_round_1_id,
            "copy_round_2_id": phraseset.copy_round_2_id,
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
            "result_viewed": result_viewed,
            "activity": activity_payload,
            "created_at": self._ensure_utc(phraseset.created_at),
            "finalized_at": self._ensure_utc(phraseset.finalized_at),
        }

    async def get_public_phraseset_details(
        self,
        phraseset_id: UUID,
    ) -> dict:
        """Return full detail view for a COMPLETED phraseset (public access for review)."""
        phraseset = await self.db.get(Phraseset, phraseset_id)
        if not phraseset:
            raise ValueError("Phraseset not found")

        # Only allow access to finalized phrasesets
        if phraseset.status != "finalized":
            raise ValueError("Phraseset not finalized")

        prompt_round, copy1_round, copy2_round = await self._load_contributor_rounds(phraseset)
        contributor_ids = {
            prompt_round.player_id,
            copy1_round.player_id,
            copy2_round.player_id,
        }

        player_records = await self._load_players(contributor_ids)

        # Build contributor list (without "is_you" flag for public access)
        contributors = [
            {
                "round_id": prompt_round.round_id,
                "player_id": prompt_round.player_id,
                "username": player_records.get(prompt_round.player_id, {}).get("username", str(prompt_round.player_id)),
                "is_you": False,  # Always False for public access
                "is_ai": player_records.get(prompt_round.player_id, {}).get("is_ai", False),
                "phrase": phraseset.original_phrase,
            },
            {
                "round_id": copy1_round.round_id,
                "player_id": copy1_round.player_id,
                "username": player_records.get(copy1_round.player_id, {}).get("username", str(copy1_round.player_id)),
                "is_you": False,
                "is_ai": player_records.get(copy1_round.player_id, {}).get("is_ai", False),
                "phrase": phraseset.copy_phrase_1,
            },
            {
                "round_id": copy2_round.round_id,
                "player_id": copy2_round.player_id,
                "username": player_records.get(copy2_round.player_id, {}).get("username", str(copy2_round.player_id)),
                "is_you": False,
                "is_ai": player_records.get(copy2_round.player_id, {}).get("is_ai", False),
                "phrase": phraseset.copy_phrase_2,
            },
        ]

        # Votes and voters (public information for completed rounds)
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
                "is_ai": vote_player_records.get(vote.player_id, {}).get("is_ai", False),
                "voted_phrase": vote.voted_phrase,
                "correct": vote.correct,
                "voted_at": self._ensure_utc(vote.created_at),
            }
            for vote in votes
        ]

        # Activity timeline
        activities = await self.activity_service.get_phraseset_activity(phraseset.phraseset_id)
        activity_player_ids = {act.get("player_id") for act in activities if act.get("player_id")}
        activity_players = await self._load_players(activity_player_ids, existing=vote_player_records)
        activity_payload = [
            {
                "activity_id": activity["activity_id"],
                "activity_type": activity["activity_type"],
                "created_at": self._ensure_utc(activity["created_at"]),
                "player_id": activity.get("player_id"),
                "player_username": activity_players.get(activity.get("player_id"), {}).get("username", str(activity.get("player_id"))) if activity.get("player_id") else None,
                "metadata": activity.get("metadata", {}),
            }
            for activity in activities
        ]

        # Results (public for completed rounds)
        payouts_cache: dict[UUID, dict] = {}
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
            "copy_round_1_id": phraseset.copy_round_1_id,
            "copy_round_2_id": phraseset.copy_round_2_id,
            "prompt_text": phraseset.prompt_text,
            "status": "finalized",  # Always finalized for public access
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
            "your_role": None,  # No personal context for public access
            "your_phrase": None,
            "your_payout": None,
            "result_viewed": False,
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
        already_viewed = False
        payout_amount = 0
        result_view: Optional[QFResultView] = None

        async def _apply_claim_updates() -> None:
            nonlocal already_viewed, payout_amount, result_view

            phraseset_local = await self._lock_phraseset(phraseset_id)
            if not phraseset_local:
                raise ValueError("Phraseset not found")
            if phraseset_local.status != "finalized":
                raise ValueError("Phraseset not yet finalized")

            prompt_round, copy1_round, copy2_round = await self._load_contributor_rounds(phraseset_local)
            contributor_map = {
                prompt_round.player_id,
                copy1_round.player_id,
                copy2_round.player_id,
            }
            if player_id not in contributor_map:
                raise ValueError("Not a contributor to this phraseset")

            result_view = await self._load_result_view(phraseset_local, player_id)
            already_viewed = bool(result_view and result_view.result_viewed)
            if result_view is None:
                result_view = await self._create_result_view(phraseset_local, player_id)

            payout_amount = result_view.payout_amount

            if not result_view.first_viewed_at:
                result_view.first_viewed_at = datetime.now(UTC)

            if not result_view.result_viewed:
                result_view.result_viewed = True
                result_view.result_viewed_at = datetime.now(UTC)

        try:
            async with self.db.begin():
                await _apply_claim_updates()
        except InvalidRequestError as exc:
            if "already begun" not in str(exc).lower():
                raise
            await _apply_claim_updates()

        player = await self.db.get(QFPlayer, player_id)
        if player:
            await self.db.refresh(player)

        # Invalidate cached contributions since result_viewed status changed
        self._invalidate_contributions_cache(player_id)

        return {
            "success": True,
            "amount": payout_amount,
            "new_wallet": player.wallet if player else 0,
            "new_vault": player.vault if player else 0,
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

    async def get_phraseset_history(self, phraseset_id: UUID, player_id: UUID) -> dict:
        """Return the complete event timeline for a phraseset.

        Returns all events from prompt submission through finalization,
        including usernames and timestamps for each event.

        Access is restricted to:
        1. Finalized phrasesets only (prevents viewing active phraseset details)
        2. Participants only (contributors or voters)
        """
        phraseset = await self.db.get(Phraseset, phraseset_id)
        if not phraseset:
            raise ValueError("Phraseset not found")

        # Restrict access to finalized phrasesets only
        if phraseset.status != "finalized":
            raise ValueError("Phraseset not finalized")

        # Load all votes first to check voter participation
        vote_rows = await self.db.execute(
            select(Vote)
            .where(Vote.phraseset_id == phraseset.phraseset_id)
            .order_by(Vote.created_at.asc())
        )
        votes = list(vote_rows.scalars().all())

        # Check if player is a voter
        is_voter = any(vote.player_id == player_id for vote in votes)

        # Load contributor rounds (may be incomplete for abandoned phrasesets)
        round_ids = [
            phraseset.prompt_round_id,
            phraseset.copy_round_1_id,
            phraseset.copy_round_2_id,
        ]
        result = await self.db.execute(
            select(Round).where(Round.round_id.in_([rid for rid in round_ids if rid]))
        )
        rounds = {round_.round_id: round_ for round_ in result.scalars().all()}

        prompt_round = rounds.get(phraseset.prompt_round_id)
        copy1_round = rounds.get(phraseset.copy_round_1_id) if phraseset.copy_round_1_id else None
        copy2_round = rounds.get(phraseset.copy_round_2_id) if phraseset.copy_round_2_id else None

        # Collect contributor IDs (only for rounds that exist)
        contributor_ids = set()
        if prompt_round:
            contributor_ids.add(prompt_round.player_id)
        if copy1_round:
            contributor_ids.add(copy1_round.player_id)
        if copy2_round:
            contributor_ids.add(copy2_round.player_id)

        # Check if player is a contributor
        is_contributor = player_id in contributor_ids

        # Verify player is either a contributor or voter
        if not is_contributor and not is_voter:
            raise ValueError("Not a participant in this phraseset")

        # Collect all player IDs for loading usernames
        player_ids = contributor_ids.copy()
        player_ids.update(vote.player_id for vote in votes)

        # Load player information
        player_records = await self._load_players(player_ids)

        # Helper function to create submission events
        def create_submission_event(
            event_type: str,
            round_obj: Round,
            phrase: str,
            extra_metadata: dict = None
        ) -> dict:
            metadata = {"round_id": round_obj.round_id}
            if extra_metadata:
                metadata.update(extra_metadata)

            return {
                "event_type": event_type,
                "timestamp": self._ensure_utc(round_obj.created_at),
                "player_id": round_obj.player_id,
                "username": player_records.get(round_obj.player_id, {}).get("username"),
                "phrase": phrase,
                "correct": None,
                "metadata": metadata,
            }

        # Build events timeline
        events = []

        # Add prompt submission event (if round exists)
        if prompt_round:
            events.append(create_submission_event(
                "prompt_submitted",
                prompt_round,
                phraseset.original_phrase,
                {"prompt_text": phraseset.prompt_text}
            ))

        # Add copy submission events (only for rounds that exist)
        if copy1_round:
            events.append(create_submission_event(
                "copy_submitted",
                copy1_round,
                phraseset.copy_phrase_1,
                {"copy_number": 1}
            ))

        if copy2_round:
            events.append(create_submission_event(
                "copy_submitted",
                copy2_round,
                phraseset.copy_phrase_2,
                {"copy_number": 2}
            ))

        # Add vote events
        for vote in votes:
            events.append({
                "event_type": "vote_submitted",
                "timestamp": self._ensure_utc(vote.created_at),
                "player_id": vote.player_id,
                "username": player_records.get(vote.player_id, {}).get("username"),
                "phrase": vote.voted_phrase,
                "correct": vote.correct,
                "metadata": {
                    "vote_id": vote.vote_id,
                    "payout": vote.payout,
                },
            })

        # Add finalization event if finalized
        if phraseset.status == "finalized" and phraseset.finalized_at:
            events.append({
                "event_type": "finalized",
                "timestamp": self._ensure_utc(phraseset.finalized_at),
                "player_id": None,
                "username": None,
                "phrase": None,
                "correct": None,
                "metadata": {
                    "total_votes": phraseset.vote_count,
                    "total_pool": phraseset.total_pool,
                },
            })

        # Sort events by timestamp
        events.sort(key=lambda e: e["timestamp"])

        return {
            "phraseset_id": phraseset.phraseset_id,
            "prompt_text": phraseset.prompt_text,
            "original_phrase": phraseset.original_phrase,
            "copy_phrase_1": phraseset.copy_phrase_1,
            "copy_phrase_2": phraseset.copy_phrase_2,
            "status": phraseset.status,
            "created_at": self._ensure_utc(phraseset.created_at),
            "finalized_at": self._ensure_utc(phraseset.finalized_at),
            "total_votes": phraseset.vote_count,
            "events": events,
        }

    async def get_completed_phrasesets(
        self,
        limit: int = 10,
        offset: int = 0
    ) -> dict:
        """Return a list of completed (finalized) phrasesets.

        Returns up to 500 phrasesets. When more than 500 exist, prioritizes
        phrasesets with the least AI player involvement.

        AI players are identified by email ending with AI_PLAYER_EMAIL_DOMAIN.
        """
        from sqlalchemy import func, or_
        from backend.models.qf.round import Round
        from backend.models.qf.player import QFPlayer
        from backend.models.qf.vote import Vote

        MAX_RESULTS = 500

        # Get total count to determine if we need special handling
        count_result = await self.db.execute(
            select(func.count(Phraseset.phraseset_id))
            .where(Phraseset.status == "finalized")
        )
        total = count_result.scalar() or 0

        if total <= MAX_RESULTS:
            # Simple case: fetch all and order by finalization time
            result = await self.db.execute(
                select(Phraseset)
                .where(Phraseset.status == "finalized")
                .order_by(Phraseset.finalized_at.desc())
                .limit(MAX_RESULTS)
            )
            phrasesets = list(result.scalars().all())
        else:
            # Complex case: prioritize phrasesets with least AI involvement
            # Calculate AI involvement score for each phraseset

            # Subquery to count AI contributors (prompt, copy1, copy2)
            ai_contributors = (
                select(Phraseset.phraseset_id, func.count().label('ai_count'))
                .select_from(Phraseset)
                .outerjoin(
                    Round,
                    or_(
                        Phraseset.prompt_round_id == Round.round_id,
                        Phraseset.copy_round_1_id == Round.round_id,
                        Phraseset.copy_round_2_id == Round.round_id
                    )
                )
                .outerjoin(QFPlayer, Round.player_id == QFPlayer.player_id)
                .where(
                    Phraseset.status == "finalized",
                    QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}")
                )
                .group_by(Phraseset.phraseset_id)
                .subquery()
            )

            # Subquery to count AI voters
            ai_voters = (
                select(Vote.phraseset_id, func.count().label('ai_voter_count'))
                .select_from(Vote)
                .join(QFPlayer, Vote.player_id == QFPlayer.player_id)
                .where(QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"))
                .group_by(Vote.phraseset_id)
                .subquery()
            )

            # Main query: order by AI involvement (least first), then by finalization time
            result = await self.db.execute(
                select(Phraseset)
                .outerjoin(ai_contributors, Phraseset.phraseset_id == ai_contributors.c.phraseset_id)
                .outerjoin(ai_voters, Phraseset.phraseset_id == ai_voters.c.phraseset_id)
                .where(Phraseset.status == "finalized")
                .order_by(
                    func.coalesce(ai_contributors.c.ai_count, 0).asc(),
                    func.coalesce(ai_voters.c.ai_voter_count, 0).asc(),
                    Phraseset.finalized_at.desc()
                )
                .limit(MAX_RESULTS)
            )
            phrasesets = list(result.scalars().all())

        # Build response (excluding original_phrase per requirements)
        items = []
        for phraseset in phrasesets:
            items.append({
                "phraseset_id": phraseset.phraseset_id,
                "prompt_text": phraseset.prompt_text,
                "created_at": self._ensure_utc(phraseset.created_at),
                "finalized_at": self._ensure_utc(phraseset.finalized_at),
                "vote_count": phraseset.vote_count,
                "total_pool": phraseset.total_pool,
            })

        return {
            "phrasesets": items,
        }

    async def get_random_practice_phraseset(self, player_id: UUID) -> dict:
        """Get a random finalized phraseset for practice mode.

        Returns a phraseset that the player was NOT involved in (prompt, copy, or vote).
        """
        from sqlalchemy import func, or_

        # Get all phraseset IDs where player was involved
        # Check prompt rounds
        prompt_result = await self.db.execute(
            select(Phraseset.phraseset_id)
            .join(Round, Phraseset.prompt_round_id == Round.round_id)
            .where(Round.player_id == player_id)
        )
        prompt_phrasesets = {row[0] for row in prompt_result.all()}

        # Check copy rounds
        copy_result = await self.db.execute(
            select(Phraseset.phraseset_id)
            .where(
                or_(
                    Phraseset.copy_round_1_id.in_(
                        select(Round.round_id).where(Round.player_id == player_id)
                    ),
                    Phraseset.copy_round_2_id.in_(
                        select(Round.round_id).where(Round.player_id == player_id)
                    )
                )
            )
        )
        copy_phrasesets = {row[0] for row in copy_result.all()}

        # Check votes
        vote_result = await self.db.execute(
            select(Vote.phraseset_id)
            .where(Vote.player_id == player_id)
        )
        vote_phrasesets = {row[0] for row in vote_result.all()}

        # Combine all phrasesets to exclude
        excluded_phrasesets = prompt_phrasesets | copy_phrasesets | vote_phrasesets

        # Get a random phraseset that is finalized and not in the excluded list
        query = (
            select(Phraseset)
            .where(Phraseset.status == "finalized")
        )

        if excluded_phrasesets:
            query = query.where(~Phraseset.phraseset_id.in_(list(excluded_phrasesets)))

        query = query.order_by(func.random()).limit(1)

        result = await self.db.execute(query)
        phraseset = result.scalar_one_or_none()

        if not phraseset:
            raise ValueError("No phrasesets available for practice")

        # Load contributor rounds to get usernames
        prompt_round, copy1_round, copy2_round = await self._load_contributor_rounds(phraseset)

        # Load player records to get usernames
        player_ids = [prompt_round.player_id, copy1_round.player_id, copy2_round.player_id]
        player_records = await self._load_players(player_ids)

        # Load hints for the prompt round (if they exist)
        from backend.models.qf.hint import Hint
        hint_result = await self.db.execute(
            select(Hint).where(Hint.prompt_round_id == phraseset.prompt_round_id)
        )
        hint_record = hint_result.scalar_one_or_none()
        hints = hint_record.hint_phrases if hint_record else None

        # Load votes for the phraseset
        vote_result = await self.db.execute(
            select(Vote)
            .where(Vote.phraseset_id == phraseset.phraseset_id)
            .order_by(Vote.created_at)
        )
        votes = vote_result.scalars().all()

        # Load voter usernames
        voter_ids = [vote.player_id for vote in votes]
        voter_records = await self._load_players(voter_ids) if voter_ids else {}

        # Build vote details
        vote_details = []
        for vote in votes:
            vote_details.append({
                "vote_id": str(vote.vote_id),
                "voter_id": str(vote.player_id),
                "voter_username": voter_records.get(vote.player_id, {}).get("username", "Unknown"),
                "is_ai": voter_records.get(vote.player_id, {}).get("is_ai", False),
                "voted_phrase": vote.voted_phrase,
                "correct": vote.voted_phrase == phraseset.original_phrase,
                "voted_at": self._ensure_utc(vote.created_at).isoformat(),
            })

        return {
            "phraseset_id": phraseset.phraseset_id,
            "prompt_text": phraseset.prompt_text,
            "original_phrase": phraseset.original_phrase,
            "copy_phrase_1": phraseset.copy_phrase_1,
            "copy_phrase_2": phraseset.copy_phrase_2,
            "prompt_player": player_records.get(prompt_round.player_id, {}).get("username", "Unknown"),
            "copy1_player": player_records.get(copy1_round.player_id, {}).get("username", "Unknown"),
            "copy2_player": player_records.get(copy2_round.player_id, {}).get("username", "Unknown"),
            "prompt_player_is_ai": player_records.get(prompt_round.player_id, {}).get("is_ai", False),
            "copy1_player_is_ai": player_records.get(copy1_round.player_id, {}).get("is_ai", False),
            "copy2_player_is_ai": player_records.get(copy2_round.player_id, {}).get("is_ai", False),
            "hints": hints,
            "votes": vote_details,
        }

    # ---------------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------------

    async def _build_contributions(self, player_id: UUID) -> list[dict]:
        """Load prompt, copy, and vote contributions and derive summary fields.

        Results are cached per player_id for the lifetime of this service instance
        to avoid redundant queries within a single request.
        """
        # Check cache first
        if player_id in self._contributions_cache:
            return self._contributions_cache[player_id]

        prompt_rounds, prompt_round_map = await self._load_prompt_rounds_for_player(player_id)
        copy_rounds = await self._load_copy_rounds_for_player(player_id)
        votes = await self._load_votes_for_player(player_id)
        await self._populate_missing_prompt_rounds(copy_rounds, prompt_round_map)

        # Build phraseset map keyed by prompt_round_id for prompt/copy contributions
        phrasesets, phraseset_by_prompt_round_id = [], {}
        if prompt_round_map:
            phrasesets, phraseset_by_prompt_round_id = await self._load_phrasesets_for_prompts(prompt_round_map)

        # Build phraseset map keyed by phraseset_id for all phrasesets
        phraseset_by_id = {ps.phraseset_id: ps for ps in phrasesets}

        # Load missing phrasesets referenced by votes
        vote_phraseset_ids = {vote.phraseset_id for vote in votes}
        missing_phraseset_ids = vote_phraseset_ids - set(phraseset_by_id.keys())
        if missing_phraseset_ids:
            missing_result = await self.db.execute(
                select(Phraseset).where(Phraseset.phraseset_id.in_(list(missing_phraseset_ids)))
            )
            missing_phrasesets = list(missing_result.scalars().all())
            phrasesets.extend(missing_phrasesets)
            for phraseset in missing_phrasesets:
                phraseset_by_id[phraseset.phraseset_id] = phraseset

        result_view_map = await self._load_result_views_for_player(player_id, phrasesets)
        payouts_by_phraseset = await self._load_payouts_for_phrasesets(phrasesets)

        contributions = []
        contributions.extend(
            self._build_prompt_contribution_entries(
                prompt_rounds,
                phraseset_by_prompt_round_id,
                result_view_map,
                payouts_by_phraseset,
            )
        )
        contributions.extend(
            self._build_copy_contribution_entries(
                copy_rounds,
                prompt_round_map,
                phraseset_by_prompt_round_id,
                result_view_map,
                payouts_by_phraseset,
            )
        )
        contributions.extend(
            self._build_vote_contribution_entries(
                votes,
                phraseset_by_id,
                result_view_map,
                payouts_by_phraseset,
            )
        )

        contributions.sort(
            key=lambda entry: entry["created_at"] or datetime.now(UTC),
            reverse=True,
        )

        self._contributions_cache[player_id] = contributions
        return contributions

    async def _load_prompt_rounds_for_player(
        self, player_id: UUID
    ) -> Tuple[list[Round], dict[UUID, Round]]:
        """Fetch submitted prompt rounds and build a lookup map."""

        prompt_result = await self.db.execute(
            select(Round)
            .where(Round.player_id == player_id)
            .where(Round.round_type == "prompt")
            .where(Round.submitted_phrase.is_not(None))
        )
        prompt_rounds = list(prompt_result.scalars().all())
        prompt_round_map = {prompt.round_id: prompt for prompt in prompt_rounds}
        return prompt_rounds, prompt_round_map

    async def _load_copy_rounds_for_player(self, player_id: UUID) -> list[Round]:
        """Fetch submitted copy rounds for the player."""

        copy_result = await self.db.execute(
            select(Round)
            .where(Round.player_id == player_id)
            .where(Round.round_type == "copy")
            .where(Round.status == "submitted")
        )
        return list(copy_result.scalars().all())

    async def _populate_missing_prompt_rounds(
        self,
        copy_rounds: list[Round],
        prompt_round_map: dict[UUID, Round],
    ) -> None:
        """Ensure prompt rounds referenced by copy rounds are present in the cache."""

        copy_prompt_ids = {
            copy.prompt_round_id
            for copy in copy_rounds
            if copy.prompt_round_id is not None
        }
        missing_prompt_ids = copy_prompt_ids - set(prompt_round_map.keys())
        if not missing_prompt_ids:
            return

        missing_prompt_result = await self.db.execute(
            select(Round).where(Round.round_id.in_(list(missing_prompt_ids)))
        )
        for prompt in missing_prompt_result.scalars().all():
            prompt_round_map[prompt.round_id] = prompt

    async def _load_phrasesets_for_prompts(
        self, prompt_round_map: dict[UUID, Round]
    ) -> Tuple[list[Phraseset], dict[UUID, Phraseset]]:
        """Load phrasesets tied to the supplied prompt rounds."""

        prompt_ids = list(prompt_round_map.keys())
        if not prompt_ids:
            return [], {}

        phraseset_result = await self.db.execute(
            select(Phraseset).where(Phraseset.prompt_round_id.in_(prompt_ids))
        )
        phrasesets = list(phraseset_result.scalars().all())
        phraseset_map = {phraseset.prompt_round_id: phraseset for phraseset in phrasesets}
        return phrasesets, phraseset_map

    async def _load_result_views_for_player(
        self, player_id: UUID, phrasesets: list[Phraseset]
    ) -> dict[UUID, QFResultView]:
        """Load any existing result views for the player."""

        phraseset_ids = [phraseset.phraseset_id for phraseset in phrasesets]
        if not phraseset_ids:
            return {}

        rv_result = await self.db.execute(
            select(QFResultView)
            .where(QFResultView.player_id == player_id)
            .where(QFResultView.phraseset_id.in_(phraseset_ids))
        )
        return {rv.phraseset_id: rv for rv in rv_result.scalars().all()}

    async def _load_payouts_for_phrasesets(
        self, phrasesets: list[Phraseset]
    ) -> dict[UUID, dict]:
        """Calculate payouts for finalized phrasesets with simple memoization."""

        finalized = [
            phraseset for phraseset in phrasesets if phraseset.status == "finalized"
        ]
        if not finalized:
            return {}

        uncached = [
            phraseset
            for phraseset in finalized
            if phraseset.phraseset_id not in self._payouts_cache
        ]
        if uncached:
            payouts = await self.scoring_service.calculate_payouts_bulk(uncached)
            self._payouts_cache.update(payouts)

        return {
            phraseset.phraseset_id: self._payouts_cache[phraseset.phraseset_id]
            for phraseset in finalized
            if phraseset.phraseset_id in self._payouts_cache
        }

    def _build_prompt_contribution_entries(
        self,
        prompt_rounds: list[Round],
        phraseset_map: dict[UUID, Phraseset],
        result_view_map: dict[UUID, QFResultView],
        payouts_by_phraseset: dict[UUID, dict],
    ) -> list[dict]:
        """Build contribution metadata for prompt rounds."""

        contributions: list[dict] = []
        for prompt_round in prompt_rounds:
            phraseset = phraseset_map.get(prompt_round.round_id)
            result_view = (
                result_view_map.get(phraseset.phraseset_id) if phraseset else None
            )
            result_viewed = result_view.result_viewed if result_view else False
            your_payout = None
            if phraseset and phraseset.status == "finalized":
                payouts = payouts_by_phraseset.get(phraseset.phraseset_id)
                if payouts:
                    your_payout = self._extract_player_payout(
                        payouts,
                        prompt_round.player_id,
                    )
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
        return contributions

    def _build_copy_contribution_entries(
        self,
        copy_rounds: list[Round],
        prompt_round_map: dict[UUID, Round],
        phraseset_map: dict[UUID, Phraseset],
        result_view_map: dict[UUID, QFResultView],
        payouts_by_phraseset: dict[UUID, dict],
    ) -> list[dict]:
        """Build contribution metadata for copy rounds."""

        contributions: list[dict] = []
        for copy_round in copy_rounds:
            prompt_round = prompt_round_map.get(copy_round.prompt_round_id)
            phraseset = phraseset_map.get(copy_round.prompt_round_id)

            if phraseset and copy_round.round_id not in {
                phraseset.copy_round_1_id,
                phraseset.copy_round_2_id,
            }:
                continue

            result_view = (
                result_view_map.get(phraseset.phraseset_id) if phraseset else None
            )
            result_viewed = result_view.result_viewed if result_view else False
            your_payout = None
            if phraseset and phraseset.status == "finalized":
                payouts = payouts_by_phraseset.get(phraseset.phraseset_id)
                if payouts:
                    your_payout = self._extract_player_payout(
                        payouts,
                        copy_round.player_id,
                    )
                if result_view and result_view.payout_amount:
                    your_payout = result_view.payout_amount

            contributions.append(
                {
                    "phraseset_id": phraseset.phraseset_id if phraseset else None,
                    "prompt_round_id": copy_round.prompt_round_id,
                    "copy_round_id": copy_round.round_id,
                    "prompt_text": phraseset.prompt_text
                    if phraseset
                    else (prompt_round.prompt_text if prompt_round else ""),
                    "your_role": "copy",
                    "your_phrase": copy_round.copy_phrase,
                    "original_phrase": copy_round.original_phrase,
                    "status": self._derive_status(prompt_round, phraseset),
                    "created_at": self._ensure_utc(copy_round.created_at),
                    "updated_at": self._determine_updated_at(
                        prompt_round, phraseset, fallback=copy_round.created_at
                    ),
                    "vote_count": phraseset.vote_count if phraseset else 0,
                    "third_vote_at": self._ensure_utc(phraseset.third_vote_at)
                    if phraseset
                    else None,
                    "fifth_vote_at": self._ensure_utc(phraseset.fifth_vote_at)
                    if phraseset
                    else None,
                    "finalized_at": self._ensure_utc(phraseset.finalized_at)
                    if phraseset
                    else None,
                    "has_copy1": bool(prompt_round.copy1_player_id)
                    if prompt_round
                    else bool(phraseset),
                    "has_copy2": bool(prompt_round.copy2_player_id)
                    if prompt_round
                    else bool(phraseset),
                    "your_payout": your_payout,
                    "result_viewed": result_viewed,
                    "new_activity_count": 0,
                }
            )
        return contributions

    async def _load_votes_for_player(self, player_id: UUID) -> list[Vote]:
        """Fetch votes submitted by the player."""
        vote_result = await self.db.execute(
            select(Vote)
            .where(Vote.player_id == player_id)
        )
        return list(vote_result.scalars().all())

    def _build_vote_contribution_entries(
        self,
        votes: list[Vote],
        phraseset_map: dict[UUID, Phraseset],
        result_view_map: dict[UUID, QFResultView],
        payouts_by_phraseset: dict[UUID, dict],
    ) -> list[dict]:
        """Build contribution metadata for vote entries."""
        contributions: list[dict] = []
        for vote in votes:
            phraseset = phraseset_map.get(vote.phraseset_id)
            if not phraseset:
                continue

            result_view = result_view_map.get(vote.phraseset_id)
            result_viewed = result_view.result_viewed if result_view else False

            # Vote payouts are stored directly on the vote record, not in the prize pool
            # Use the stored payout from result_view if available, otherwise use vote.payout
            your_payout = vote.payout
            if result_view and result_view.payout_amount is not None:
                your_payout = result_view.payout_amount

            contributions.append(
                {
                    "phraseset_id": phraseset.phraseset_id,
                    "prompt_round_id": phraseset.prompt_round_id,
                    "prompt_text": phraseset.prompt_text,
                    "your_role": "vote",
                    "your_phrase": vote.voted_phrase,
                    "status": phraseset.status,
                    "created_at": self._ensure_utc(vote.created_at),
                    "updated_at": self._determine_updated_at(
                        None, phraseset, fallback=vote.created_at
                    ),
                    "vote_count": phraseset.vote_count,
                    "third_vote_at": self._ensure_utc(phraseset.third_vote_at) if phraseset.third_vote_at else None,
                    "fifth_vote_at": self._ensure_utc(phraseset.fifth_vote_at) if phraseset.fifth_vote_at else None,
                    "finalized_at": self._ensure_utc(phraseset.finalized_at) if phraseset.finalized_at else None,
                    "has_copy1": True,
                    "has_copy2": True,
                    "your_payout": your_payout,
                    "result_viewed": result_viewed,
                    "new_activity_count": 0,
                }
            )
        return contributions

    async def _load_contributor_rounds(self, phraseset: Phraseset) -> tuple[Round, Round, Round]:
        """Load prompt and copy rounds for a phraseset using a single query."""
        from backend.utils.qf.phraseset_utils import validate_phraseset_contributor_rounds

        # Validate all contributor round IDs are present
        validate_phraseset_contributor_rounds(phraseset)

        round_ids = [
            phraseset.prompt_round_id,
            phraseset.copy_round_1_id,
            phraseset.copy_round_2_id,
        ]
        result = await self.db.execute(
            select(Round).where(Round.round_id.in_(round_ids))
        )
        rounds = {round_.round_id: round_ for round_ in result.scalars().all()}

        prompt_round = rounds.get(phraseset.prompt_round_id)
        copy1_round = rounds.get(phraseset.copy_round_1_id)
        copy2_round = rounds.get(phraseset.copy_round_2_id)

        if not prompt_round or not copy1_round or not copy2_round:
            missing = []
            if not prompt_round:
                missing.append(f"prompt({phraseset.prompt_round_id})")
            if not copy1_round:
                missing.append(f"copy1({phraseset.copy_round_1_id})")
            if not copy2_round:
                missing.append(f"copy2({phraseset.copy_round_2_id})")
            logger.error(
                f"Phraseset {phraseset.phraseset_id} has missing rounds: {', '.join(missing)}. "
                f"Found {len(rounds)} of 3 expected rounds."
            )
            raise ValueError("Phraseset contributors missing")
        return prompt_round, copy1_round, copy2_round

    async def _lock_phraseset(self, phraseset_id: UUID) -> Optional[Phraseset]:
        """Load and lock a phraseset row for update within an active transaction."""
        result = await self.db.execute(
            select(Phraseset)
            .where(Phraseset.phraseset_id == phraseset_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _load_result_view(
        self,
        phraseset: Phraseset,
        player_id: UUID,
    ) -> Optional[QFResultView]:
        """Fetch an existing result view record."""
        result = await self.db.execute(
            select(QFResultView)
            .where(QFResultView.phraseset_id == phraseset.phraseset_id)
            .where(QFResultView.player_id == player_id)
        )
        return result.scalar_one_or_none()

    async def _create_result_view(
        self,
        phraseset: Phraseset,
        player_id: UUID,
    ) -> QFResultView:
        """Create a result view entry for a player with the current payout amount."""
        payouts = await self.scoring_service.calculate_payouts(phraseset)
        payout_amount = self._extract_player_payout(payouts, player_id) or 0

        values = {
            "view_id": uuid4(),
            "phraseset_id": phraseset.phraseset_id,
            "player_id": player_id,
            "payout_amount": payout_amount,
            "result_viewed": False,
        }

        result_view, inserted = await upsert_result_view(
            self.db,
            phraseset_id=phraseset.phraseset_id,
            player_id=player_id,
            values=values,
        )

        # Ensure payout amount reflects current calculation even if record already existed
        if not inserted and result_view.payout_amount != payout_amount:
            result_view.payout_amount = payout_amount

        return result_view

    async def _load_players(
        self,
        player_ids: Iterable[UUID],
        existing: Optional[dict] = None,
    ) -> dict[UUID, dict]:
        """Fetch usernames and email for player IDs, merging into existing mapping."""
        mapping = dict(existing or {})
        ids = {pid for pid in player_ids if pid and pid not in mapping}
        if not ids:
            return mapping

        result = await self.db.execute(
            select(QFPlayer.player_id, QFPlayer.username, QFPlayer.email).where(QFPlayer.player_id.in_(ids))
        )
        for player_id, username, email in result.all():
            mapping[player_id] = {
                "username": username,
                "is_ai": email.endswith(AI_PLAYER_EMAIL_DOMAIN) if email else False
            }
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
        player_vote: Optional[Vote] = None,
    ) -> tuple[str, Optional[str]]:
        """Determine player's role and phrase in the phraseset."""
        if player_id == prompt_round.player_id:
            return "prompt", phraseset.original_phrase
        if player_id == copy1_round.player_id:
            return "copy", phraseset.copy_phrase_1
        if player_id == copy2_round.player_id:
            return "copy", phraseset.copy_phrase_2
        if player_vote:
            return "vote", player_vote.voted_phrase
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

    def _ensure_utc(self, dt) -> Optional[datetime]:
        """Ensure datetimes are timezone-aware in UTC."""
        if not dt:
            return None
        
        # Handle string datetime values (from ActivityService)
        if isinstance(dt, str):
            try:
                # Parse ISO format string - use the already imported datetime class
                parsed_dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                if parsed_dt.tzinfo is None:
                    return parsed_dt.replace(tzinfo=UTC)
                return parsed_dt
            except (ValueError, AttributeError):
                return None
        
        # Handle datetime objects
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt
            
        return None
