"""Statistics service for player performance metrics."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, and_, distinct
from uuid import UUID
from datetime import datetime, UTC
import logging
import asyncio

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

        # Calculate all statistics concurrently for better performance
        (
            prompt_stats,
            copy_stats,
            voter_stats,
            earnings,
            frequency,
            favorite_prompts,
            best_phrases,
        ) = await asyncio.gather(
            self._calculate_role_stats(player_id, "prompt"),
            self._calculate_role_stats(player_id, "copy"),
            self._calculate_role_stats(player_id, "voter"),
            self._calculate_earnings_breakdown(player_id),
            self._calculate_play_frequency(player_id, player.created_at),
            self._get_favorite_prompts(player_id),
            self._get_best_phrases(player_id),
        )

        return PlayerStatistics(
            player_id=player_id,
            username=player.username,
            email=player.email,
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

        count_result = await self.db.execute(
            select(func.count(Round.round_id)).where(
                and_(
                    Round.player_id == player_id,
                    Round.round_type == round_type,
                    Round.status == "submitted"  # Only count completed rounds
                )
            )
        )
        total_rounds = count_result.scalar_one()

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

        # Get transaction earnings scoped to this specific role
        if role == "voter":
            # For voters, get vote payouts
            trans_result = await self.db.execute(
                select(
                    func.coalesce(func.sum(Transaction.amount), 0).label("total_earnings"),
                    func.count(Transaction.transaction_id).label("win_count")
                )
                .where(
                    and_(
                        Transaction.player_id == player_id,
                        Transaction.type == "vote_payout",
                        Transaction.amount > 0
                    )
                )
            )
        elif role == "prompt":
            # For prompts, get prize payouts from phrasesets where this player was the prompter
            trans_result = await self.db.execute(
                select(
                    func.coalesce(func.sum(Transaction.amount), 0).label("total_earnings"),
                    func.count(Transaction.transaction_id).label("win_count")
                )
                .select_from(Transaction)
                .join(PhraseSet, Transaction.reference_id == PhraseSet.phraseset_id)
                .join(Round, PhraseSet.prompt_round_id == Round.round_id)
                .where(
                    and_(
                        Transaction.player_id == player_id,
                        Transaction.type == "prize_payout",
                        Transaction.amount > 0,
                        Round.player_id == player_id,
                        Round.round_type == "prompt"
                    )
                )
            )
        else:  # copy
            # For copies, get prize payouts from phrasesets where this player was a copier
            trans_result = await self.db.execute(
                select(
                    func.coalesce(func.sum(Transaction.amount), 0).label("total_earnings"),
                    func.count(Transaction.transaction_id).label("win_count")
                )
                .select_from(Transaction)
                .join(PhraseSet, Transaction.reference_id == PhraseSet.phraseset_id)
                .join(
                    Round,
                    (PhraseSet.copy_round_1_id == Round.round_id) |
                    (PhraseSet.copy_round_2_id == Round.round_id)
                )
                .where(
                    and_(
                        Transaction.player_id == player_id,
                        Transaction.type == "prize_payout",
                        Transaction.amount > 0,
                        Round.player_id == player_id,
                        Round.round_type == "copy"
                    )
                )
            )

        earnings_stats = trans_result.one()
        total_earnings = earnings_stats.total_earnings or 0
        wins = earnings_stats.win_count or 0
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
                # For prompts, count votes for the original phrase using aggregated query
                votes_result = await self.db.execute(
                    select(
                        func.count(distinct(PhraseSet.phraseset_id)).label("phraseset_count"),
                        func.count(Vote.vote_id).label("total_votes")
                    )
                    .select_from(PhraseSet)
                    .join(Round, PhraseSet.prompt_round_id == Round.round_id)
                    .outerjoin(
                        Vote,
                        and_(
                            Vote.phraseset_id == PhraseSet.phraseset_id,
                            Vote.voted_phrase == PhraseSet.original_phrase
                        )
                    )
                    .where(
                        and_(
                            Round.player_id == player_id,
                            PhraseSet.status == "finalized"
                        )
                    )
                )
                votes_stats = votes_result.one()
                phraseset_count = votes_stats.phraseset_count or 0
                total_votes = votes_stats.total_votes or 0
                average_votes_received = total_votes / phraseset_count if phraseset_count > 0 else 0.0

            else:  # copy
                # For copies, count votes for their copy phrases using aggregated query
                votes_result = await self.db.execute(
                    select(
                        func.count(distinct(PhraseSet.phraseset_id)).label("phraseset_count"),
                        func.count(Vote.vote_id).label("total_votes")
                    )
                    .select_from(PhraseSet)
                    .join(
                        Round,
                        and_(
                            (PhraseSet.copy_round_1_id == Round.round_id) |
                            (PhraseSet.copy_round_2_id == Round.round_id),
                            Round.player_id == player_id,
                            Round.round_type == "copy",
                            Round.copy_phrase.isnot(None)
                        )
                    )
                    .outerjoin(
                        Vote,
                        and_(
                            Vote.phraseset_id == PhraseSet.phraseset_id,
                            Vote.voted_phrase == Round.copy_phrase
                        )
                    )
                    .where(PhraseSet.status == "finalized")
                )
                votes_stats = votes_result.one()
                phraseset_count = votes_stats.phraseset_count or 0
                total_votes = votes_stats.total_votes or 0
                average_votes_received = total_votes / phraseset_count if phraseset_count > 0 else 0.0

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
        # Use a single aggregated query to categorize and sum all earnings
        result = await self.db.execute(
            select(
                func.sum(case(
                    (Transaction.type == "daily_bonus", Transaction.amount),
                    else_=0
                )).label("daily_bonuses"),
                func.sum(case(
                    (Transaction.type == "vote_payout", Transaction.amount),
                    else_=0
                )).label("vote_earnings"),
                func.sum(case(
                    (
                        and_(
                            Transaction.type == "prize_payout",
                            Round.round_type == "prompt"
                        ),
                        Transaction.amount
                    ),
                    else_=0
                )).label("prompt_earnings"),
                func.sum(case(
                    (
                        and_(
                            Transaction.type == "prize_payout",
                            Round.round_type == "copy"
                        ),
                        Transaction.amount
                    ),
                    else_=0
                )).label("copy_earnings")
            )
            .select_from(Transaction)
            .outerjoin(
                PhraseSet,
                and_(
                    Transaction.reference_id == PhraseSet.phraseset_id,
                    Transaction.type == "prize_payout"
                )
            )
            .outerjoin(
                Round,
                (PhraseSet.prompt_round_id == Round.round_id) |
                (PhraseSet.copy_round_1_id == Round.round_id) |
                (PhraseSet.copy_round_2_id == Round.round_id)
            )
            .where(
                and_(
                    Transaction.player_id == player_id,
                    Transaction.amount > 0,
                    # Filter Round to only include rows where this player is involved
                    (Round.player_id == player_id) | (Round.round_id.is_(None))
                )
            )
        )

        earnings_stats = result.one()

        daily_bonuses = earnings_stats.daily_bonuses or 0
        vote_earnings = earnings_stats.vote_earnings or 0
        prompt_earnings = earnings_stats.prompt_earnings or 0
        copy_earnings = earnings_stats.copy_earnings or 0
        total_earnings = daily_bonuses + vote_earnings + prompt_earnings + copy_earnings

        # Calculate costs (negative transactions)
        costs_result = await self.db.execute(
            select(
                func.sum(case(
                    (Transaction.type == "prompt_entry", func.abs(Transaction.amount)),
                    else_=0
                )).label("prompt_costs"),
                func.sum(case(
                    (Transaction.type == "copy_entry", func.abs(Transaction.amount)),
                    else_=0
                )).label("copy_costs"),
                func.sum(case(
                    (Transaction.type == "vote_entry", func.abs(Transaction.amount)),
                    else_=0
                )).label("vote_costs")
            )
            .where(
                and_(
                    Transaction.player_id == player_id,
                    Transaction.amount < 0
                )
            )
        )

        costs_stats = costs_result.one()

        prompt_costs = costs_stats.prompt_costs or 0
        copy_costs = costs_stats.copy_costs or 0
        vote_costs = costs_stats.vote_costs or 0
        total_costs = prompt_costs + copy_costs + vote_costs

        return EarningsBreakdown(
            prompt_earnings=prompt_earnings,
            copy_earnings=copy_earnings,
            vote_earnings=vote_earnings,
            daily_bonuses=daily_bonuses,
            total_earnings=total_earnings,
            prompt_costs=prompt_costs,
            copy_costs=copy_costs,
            vote_costs=vote_costs,
            total_costs=total_costs,
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
        count_result = await self.db.execute(
            select(func.count(Round.round_id)).where(
                and_(
                    Round.player_id == player_id,
                    Round.status == "submitted"
                )
            )
        )
        total_rounds_played = count_result.scalar_one()

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
        # Get prompt phrases with votes and earnings aggregated by phrase text
        prompt_result = await self.db.execute(
            select(
                Round.submitted_phrase.label("phrase"),
                func.count(Vote.vote_id).label("votes"),
                func.coalesce(func.sum(Transaction.amount), 0).label("earnings")
            )
            .select_from(Round)
            .join(PhraseSet, PhraseSet.prompt_round_id == Round.round_id)
            .outerjoin(
                Vote,
                and_(
                    Vote.phraseset_id == PhraseSet.phraseset_id,
                    Vote.voted_phrase == Round.submitted_phrase
                )
            )
            .outerjoin(
                Transaction,
                and_(
                    Transaction.player_id == player_id,
                    Transaction.reference_id == PhraseSet.phraseset_id,
                    Transaction.type == "prize_payout"
                )
            )
            .where(
                and_(
                    Round.player_id == player_id,
                    Round.round_type == "prompt",
                    Round.status == "submitted",
                    Round.submitted_phrase.isnot(None),
                    PhraseSet.status == "finalized"
                )
            )
            .group_by(Round.submitted_phrase)
        )

        # Get copy phrases with votes and earnings aggregated by phrase text
        copy_result = await self.db.execute(
            select(
                Round.copy_phrase.label("phrase"),
                func.count(Vote.vote_id).label("votes"),
                func.coalesce(func.sum(Transaction.amount), 0).label("earnings")
            )
            .select_from(Round)
            .join(
                PhraseSet,
                (PhraseSet.copy_round_1_id == Round.round_id) |
                (PhraseSet.copy_round_2_id == Round.round_id)
            )
            .outerjoin(
                Vote,
                and_(
                    Vote.phraseset_id == PhraseSet.phraseset_id,
                    Vote.voted_phrase == Round.copy_phrase
                )
            )
            .outerjoin(
                Transaction,
                and_(
                    Transaction.player_id == player_id,
                    Transaction.reference_id == PhraseSet.phraseset_id,
                    Transaction.type == "prize_payout"
                )
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
            .group_by(Round.copy_phrase)
        )

        # Combine results
        phrases = []
        for row in prompt_result.all():
            phrases.append({
                "phrase": row.phrase,
                "votes": row.votes,
                "earnings": row.earnings,
            })

        for row in copy_result.all():
            phrases.append({
                "phrase": row.phrase,
                "votes": row.votes,
                "earnings": row.earnings,
            })

        # Sort by votes first, then earnings
        phrases.sort(key=lambda p: (p["votes"], p["earnings"]), reverse=True)

        return [
            BestPerformingPhrase(**phrase)
            for phrase in phrases[:limit]
        ]
