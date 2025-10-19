"""Statistics service for player performance metrics."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_, distinct
from uuid import UUID
from datetime import datetime, UTC
import logging

from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import PhraseSet
from backend.models.transaction import Transaction
from backend.models.vote import Vote
from backend.schemas.player import (
    RoleStatistics,
    EarningsBreakdown,
    PlayFrequency,
    BestPerformingPhrase,
    PlayerStatistics,
)

logger = logging.getLogger(__name__)


class StatisticsService:
    """Service for calculating comprehensive player statistics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_player_statistics(self, player_id: UUID) -> PlayerStatistics:
        """
        Get comprehensive player statistics.

        Args:
            player_id: Player UUID

        Returns:
            PlayerStatistics with all metrics
        """
        # Get player info
        result = await self.db.execute(
            select(Player).where(Player.player_id == player_id)
        )
        player = result.scalar_one_or_none()
        if not player:
            raise ValueError(f"Player not found: {player_id}")

        # Calculate all statistics in parallel where possible
        prompt_stats = await self._calculate_role_stats(player_id, "prompt")
        copy_stats = await self._calculate_role_stats(player_id, "copy")
        voter_stats = await self._calculate_role_stats(player_id, "voter")
        earnings = await self._calculate_earnings_breakdown(player_id)
        frequency = await self._calculate_play_frequency(player_id, player.created_at)
        favorite_prompts = await self._get_favorite_prompts(player_id)
        best_phrases = await self._get_best_phrases(player_id)

        return PlayerStatistics(
            player_id=player_id,
            username=player.username,
            overall_balance=player.balance,
            prompt_stats=prompt_stats,
            copy_stats=copy_stats,
            voter_stats=voter_stats,
            earnings=earnings,
            frequency=frequency,
            favorite_prompts=favorite_prompts,
            best_performing_phrases=best_phrases,
        )

    async def _calculate_role_stats(self, player_id: UUID, role: str) -> RoleStatistics:
        """
        Calculate statistics for a specific role.

        Args:
            player_id: Player UUID
            role: "prompt", "copy", or "voter"

        Returns:
            RoleStatistics for the role
        """
        # Get all rounds for this role
        round_type = "vote" if role == "voter" else role

        result = await self.db.execute(
            select(Round)
            .where(
                and_(
                    Round.player_id == player_id,
                    Round.round_type == round_type,
                    Round.status == "submitted"  # Only count completed rounds
                )
            )
        )
        rounds = list(result.scalars().all())

        total_rounds = len(rounds)

        if total_rounds == 0:
            return RoleStatistics(
                role=role,
                total_rounds=0,
                total_earnings=0,
                average_earnings=0.0,
                win_rate=0.0,
                total_phrasesets=0 if role != "voter" else None,
                average_votes_received=0.0 if role != "voter" else None,
                correct_votes=0 if role == "voter" else None,
                vote_accuracy=0.0 if role == "voter" else None,
            )

        # Get transaction earnings for this role
        trans_type_map = {
            "prompt": "prize_payout",
            "copy": "prize_payout",
            "voter": "vote_payout",
        }
        trans_type = trans_type_map[role]

        # Get all transactions for this role
        trans_result = await self.db.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.player_id == player_id,
                    Transaction.type == trans_type
                )
            )
        )
        transactions = list(trans_result.scalars().all())

        total_earnings = sum(t.amount for t in transactions if t.amount > 0)
        wins = sum(1 for t in transactions if t.amount > 0)
        win_rate = (wins / total_rounds * 100) if total_rounds > 0 else 0.0
        average_earnings = total_earnings / total_rounds if total_rounds > 0 else 0.0

        # Role-specific metrics
        total_phrasesets = None
        average_votes_received = None
        correct_votes = None
        vote_accuracy = None

        if role in ["prompt", "copy"]:
            # Count phrasesets this player participated in
            if role == "prompt":
                phraseset_result = await self.db.execute(
                    select(func.count(PhraseSet.phraseset_id))
                    .join(Round, PhraseSet.prompt_round_id == Round.round_id)
                    .where(
                        and_(
                            Round.player_id == player_id,
                            PhraseSet.status == "finalized"
                        )
                    )
                )
            else:  # copy
                phraseset_result = await self.db.execute(
                    select(func.count(PhraseSet.phraseset_id))
                    .where(
                        and_(
                            (PhraseSet.copy_round_1_id.in_(
                                select(Round.round_id).where(Round.player_id == player_id)
                            )) |
                            (PhraseSet.copy_round_2_id.in_(
                                select(Round.round_id).where(Round.player_id == player_id)
                            )),
                            PhraseSet.status == "finalized"
                        )
                    )
                )
            total_phrasesets = phraseset_result.scalar() or 0

            # Calculate average votes received
            if role == "prompt":
                # For prompts, count votes for the original phrase
                # Need to count how many votes were for the original phrase in each phraseset
                total_votes = 0
                phrasesets_result = await self.db.execute(
                    select(PhraseSet)
                    .join(Round, PhraseSet.prompt_round_id == Round.round_id)
                    .where(
                        and_(
                            Round.player_id == player_id,
                            PhraseSet.status == "finalized"
                        )
                    )
                )
                phrasesets = list(phrasesets_result.scalars().all())

                for ps in phrasesets:
                    # Count votes for original phrase
                    vote_count_result = await self.db.execute(
                        select(func.count(Vote.vote_id))
                        .where(
                            and_(
                                Vote.phraseset_id == ps.phraseset_id,
                                Vote.voted_phrase == ps.original_phrase
                            )
                        )
                    )
                    total_votes += vote_count_result.scalar() or 0

                average_votes_received = total_votes / len(phrasesets) if phrasesets else 0.0

            else:  # copy
                # For copies, count votes for their copy phrases
                total_votes = 0
                count = 0

                # Get all phrasesets where this player was a copier
                phrasesets_result = await self.db.execute(
                    select(PhraseSet, Round.copy_phrase)
                    .join(
                        Round,
                        (PhraseSet.copy_round_1_id == Round.round_id) |
                        (PhraseSet.copy_round_2_id == Round.round_id)
                    )
                    .where(
                        and_(
                            Round.player_id == player_id,
                            Round.round_type == "copy",
                            PhraseSet.status == "finalized"
                        )
                    )
                )
                phraseset_rows = list(phrasesets_result.all())

                for ps, copy_phrase in phraseset_rows:
                    if copy_phrase:
                        # Count votes for this copy phrase
                        vote_count_result = await self.db.execute(
                            select(func.count(Vote.vote_id))
                            .where(
                                and_(
                                    Vote.phraseset_id == ps.phraseset_id,
                                    Vote.voted_phrase == copy_phrase
                                )
                            )
                        )
                        total_votes += vote_count_result.scalar() or 0
                        count += 1

                average_votes_received = total_votes / count if count > 0 else 0.0

        elif role == "voter":
            # Count correct votes using the Vote.correct field
            vote_result = await self.db.execute(
                select(
                    func.count(Vote.vote_id).label("total"),
                    func.sum(case((Vote.correct == True, 1), else_=0)).label("correct_count")
                )
                .where(Vote.player_id == player_id)
            )
            vote_stats = vote_result.one()

            correct_votes = vote_stats.correct_count or 0
            total_votes = vote_stats.total or 0
            vote_accuracy = (correct_votes / total_votes * 100) if total_votes > 0 else 0.0

        return RoleStatistics(
            role=role,
            total_rounds=total_rounds,
            total_earnings=total_earnings,
            average_earnings=average_earnings,
            win_rate=win_rate,
            total_phrasesets=total_phrasesets,
            average_votes_received=average_votes_received,
            correct_votes=correct_votes,
            vote_accuracy=vote_accuracy,
        )

    async def _calculate_earnings_breakdown(self, player_id: UUID) -> EarningsBreakdown:
        """
        Calculate earnings breakdown by source.

        Args:
            player_id: Player UUID

        Returns:
            EarningsBreakdown with all sources
        """
        # Get all positive transactions (earnings)
        result = await self.db.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.player_id == player_id,
                    Transaction.amount > 0
                )
            )
        )
        transactions = list(result.scalars().all())

        prompt_earnings = 0
        copy_earnings = 0
        vote_earnings = 0
        daily_bonuses = 0

        for trans in transactions:
            if trans.type == "daily_bonus":
                daily_bonuses += trans.amount
            elif trans.type == "vote_payout":
                vote_earnings += trans.amount
            elif trans.type == "prize_payout":
                # Need to determine if this was a prompt or copy payout
                # Check the reference_id (phraseset_id)
                if trans.reference_id:
                    ps_result = await self.db.execute(
                        select(PhraseSet).where(PhraseSet.phraseset_id == trans.reference_id)
                    )
                    phraseset = ps_result.scalar_one_or_none()
                    if phraseset:
                        # Check if player was prompt or copy
                        prompt_result = await self.db.execute(
                            select(Round).where(Round.round_id == phraseset.prompt_round_id)
                        )
                        prompt_round = prompt_result.scalar_one_or_none()

                        if prompt_round and prompt_round.player_id == player_id:
                            prompt_earnings += trans.amount
                        else:
                            copy_earnings += trans.amount

        total_earnings = prompt_earnings + copy_earnings + vote_earnings + daily_bonuses

        return EarningsBreakdown(
            prompt_earnings=prompt_earnings,
            copy_earnings=copy_earnings,
            vote_earnings=vote_earnings,
            daily_bonuses=daily_bonuses,
            total_earnings=total_earnings,
        )

    async def _calculate_play_frequency(
        self, player_id: UUID, member_since: datetime
    ) -> PlayFrequency:
        """
        Calculate play frequency metrics.

        Args:
            player_id: Player UUID
            member_since: When player joined

        Returns:
            PlayFrequency metrics
        """
        # Get all rounds
        result = await self.db.execute(
            select(Round)
            .where(
                and_(
                    Round.player_id == player_id,
                    Round.status == "submitted"
                )
            )
        )
        rounds = list(result.scalars().all())

        total_rounds_played = len(rounds)

        if total_rounds_played == 0:
            return PlayFrequency(
                total_rounds_played=0,
                days_active=0,
                rounds_per_day=0.0,
                last_active=member_since,
                member_since=member_since,
            )

        # Get distinct days active
        distinct_days_result = await self.db.execute(
            select(func.count(distinct(func.date(Round.created_at))))
            .where(
                and_(
                    Round.player_id == player_id,
                    Round.status == "submitted"
                )
            )
        )
        days_active = distinct_days_result.scalar() or 0

        # Get last active time using SQL to avoid timezone comparison issues
        last_active_result = await self.db.execute(
            select(func.max(Round.created_at))
            .where(
                and_(
                    Round.player_id == player_id,
                    Round.status == "submitted"
                )
            )
        )
        last_active = last_active_result.scalar() or member_since

        # Calculate rounds per day
        rounds_per_day = total_rounds_played / days_active if days_active > 0 else 0.0

        return PlayFrequency(
            total_rounds_played=total_rounds_played,
            days_active=days_active,
            rounds_per_day=rounds_per_day,
            last_active=last_active,
            member_since=member_since,
        )

    async def _get_favorite_prompts(self, player_id: UUID, limit: int = 5) -> list[str]:
        """
        Get top prompts by earnings.

        Args:
            player_id: Player UUID
            limit: Number of prompts to return

        Returns:
            List of prompt texts
        """
        # Get prompt rounds with their earnings
        result = await self.db.execute(
            select(
                Round.prompt_text,
                func.coalesce(func.sum(Transaction.amount), 0).label("earnings")
            )
            .outerjoin(
                Transaction,
                and_(
                    Transaction.player_id == player_id,
                    Transaction.type == "prize_payout",
                    Transaction.reference_id == Round.phraseset_id
                )
            )
            .where(
                and_(
                    Round.player_id == player_id,
                    Round.round_type == "prompt",
                    Round.status == "submitted",
                    Round.prompt_text.isnot(None)
                )
            )
            .group_by(Round.prompt_text)
            .order_by(func.coalesce(func.sum(Transaction.amount), 0).desc())
            .limit(limit)
        )

        rows = result.all()
        return [row.prompt_text for row in rows if row.prompt_text]

    async def _get_best_phrases(
        self, player_id: UUID, limit: int = 5
    ) -> list[BestPerformingPhrase]:
        """
        Get top performing phrases by votes and earnings.

        Args:
            player_id: Player UUID
            limit: Number of phrases to return

        Returns:
            List of BestPerformingPhrase
        """
        # Get phrases from prompt and copy rounds with vote counts
        phrases = []

        # Get prompt phrases
        prompt_result = await self.db.execute(
            select(
                Round.submitted_phrase,
                PhraseSet.phraseset_id,
                PhraseSet.vote_count
            )
            .join(PhraseSet, PhraseSet.prompt_round_id == Round.round_id)
            .where(
                and_(
                    Round.player_id == player_id,
                    Round.round_type == "prompt",
                    Round.status == "submitted",
                    Round.submitted_phrase.isnot(None),
                    PhraseSet.status == "finalized"
                )
            )
        )

        for row in prompt_result.all():
            # Get earnings for this phraseset
            trans_result = await self.db.execute(
                select(func.sum(Transaction.amount))
                .where(
                    and_(
                        Transaction.player_id == player_id,
                        Transaction.reference_id == row.phraseset_id,
                        Transaction.type == "prize_payout"
                    )
                )
            )
            earnings = trans_result.scalar() or 0

            # Count votes for original phrase
            vote_result = await self.db.execute(
                select(func.count(Vote.vote_id))
                .where(
                    and_(
                        Vote.phraseset_id == row.phraseset_id,
                        Vote.voted_phrase == row.submitted_phrase
                    )
                )
            )
            votes = vote_result.scalar() or 0

            phrases.append({
                "phrase": row.submitted_phrase,
                "votes": votes,
                "earnings": earnings,
            })

        # Get copy phrases
        copy_result = await self.db.execute(
            select(
                Round.copy_phrase,
                PhraseSet.phraseset_id,
                PhraseSet.vote_count
            )
            .join(
                PhraseSet,
                (PhraseSet.copy_round_1_id == Round.round_id) |
                (PhraseSet.copy_round_2_id == Round.round_id)
            )
            .where(
                and_(
                    Round.player_id == player_id,
                    Round.round_type == "copy",
                    Round.status == "submitted",
                    Round.copy_phrase.isnot(None),
                    PhraseSet.status == "finalized"
                )
            )
        )

        for row in copy_result.all():
            # Get earnings for this phraseset
            trans_result = await self.db.execute(
                select(func.sum(Transaction.amount))
                .where(
                    and_(
                        Transaction.player_id == player_id,
                        Transaction.reference_id == row.phraseset_id,
                        Transaction.type == "prize_payout"
                    )
                )
            )
            earnings = trans_result.scalar() or 0

            # Count votes for this copy phrase
            vote_result = await self.db.execute(
                select(func.count(Vote.vote_id))
                .where(
                    and_(
                        Vote.phraseset_id == row.phraseset_id,
                        Vote.voted_phrase == row.copy_phrase
                    )
                )
            )
            votes = vote_result.scalar() or 0

            phrases.append({
                "phrase": row.copy_phrase,
                "votes": votes,
                "earnings": earnings,
            })

        # Sort by votes first, then earnings
        phrases.sort(key=lambda p: (p["votes"], p["earnings"]), reverse=True)

        return [
            BestPerformingPhrase(**phrase)
            for phrase in phrases[:limit]
        ]
