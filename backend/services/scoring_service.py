"""Scoring and payout calculation service."""

from collections import defaultdict
import logging
from typing import Iterable
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.phraseset import Phraseset
from backend.models.vote import Vote
from backend.models.round import Round
from backend.config import get_settings

logger = logging.getLogger(__name__)


settings = get_settings()


PLACEHOLDER_PLAYER_NAMESPACE = UUID("6c057f58-7199-43ff-b4fc-17b77df5e6a2")


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
            "Calculated payouts for phraseset %s: original=%s, copy1=%s, copy2=%s",
            phraseset.phraseset_id,
            original_payout,
            copy1_payout,
            copy2_payout,
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
