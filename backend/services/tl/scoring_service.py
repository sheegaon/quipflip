"""ThinkLink scoring service.

Calculates coverage, payouts, and manages round finalization.
"""
import logging
import math
from typing import List, Tuple, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func
from backend.models.tl import TLRound, TLAnswer, TLCluster
from backend.config import get_settings

logger = logging.getLogger(__name__)


class ScoringService:
    """Service for ThinkLink scoring and payouts."""

    def __init__(self):
        """Initialize scoring service."""
        settings = get_settings()
        self.match_threshold = settings.tl_match_threshold
        self.max_payout = settings.tl_max_payout
        self.payout_exponent = settings.tl_payout_exponent
        self.vault_split_rate = settings.tl_vault_rake_percent / 100.0

    async def calculate_coverage(
        self,
        db: AsyncSession,
        matched_cluster_ids: List[str],
        snapshot_cluster_ids: List[str],
        prompt_id: str,
    ) -> float:
        """Calculate weighted coverage percentage.

        Coverage p = Σ(weight of matched clusters) / Σ(weight of all snapshot clusters)

        Args:
            db: Database session
            matched_cluster_ids: List of cluster IDs matched during round
            snapshot_cluster_ids: List of all cluster IDs in snapshot
            prompt_id: Prompt ID (for context/logging)

        Returns:
            Coverage percentage (0-1)
        """
        try:
            if not snapshot_cluster_ids:
                logger.debug("🎯 No snapshot clusters - coverage = 0%")
                return 0.0

            # Calculate total weight of snapshot
            total_weight = await self._calculate_total_weight(db, snapshot_cluster_ids)

            if total_weight == 0:
                logger.debug("🎯 Total weight = 0 - coverage = 0%")
                return 0.0

            # Calculate weight of matched clusters
            matched_weight = await self._calculate_total_weight(db, matched_cluster_ids)

            coverage = float(matched_weight) / float(total_weight)
            coverage = max(0.0, min(1.0, coverage))  # Clamp to [0, 1]

            logger.debug(
                f"📊 Coverage: {coverage:.1%} "
                f"(matched_weight={matched_weight:.2f} / total={total_weight:.2f})"
            )
            return coverage
        except Exception as e:
            logger.error(f"❌ Coverage calculation failed: {e}")
            return 0.0

    async def _calculate_total_weight(
        self,
        db: AsyncSession,
        cluster_ids: List[str],
    ) -> float:
        """Calculate total weight for a set of clusters.

        Fetches all answers for all clusters in a single query to avoid N+1.

        Args:
            db: Database session
            cluster_ids: List of cluster IDs

        Returns:
            Total weight
        """
        try:
            if not cluster_ids:
                return 0.0

            # Single query: fetch all active answers in any of the clusters
            result = await db.execute(
                select(TLAnswer).where(
                    TLAnswer.cluster_id.in_(cluster_ids),
                    TLAnswer.is_active == True
                )
            )
            answers = result.scalars().all()

            # Calculate weights in Python
            total_weight = 0.0
            for answer in answers:
                # Cap player count at 20, apply log scaling
                capped_count = min(answer.answer_players_count or 0, 20)
                answer_weight = 1.0 + math.log(1.0 + float(capped_count))
                total_weight += answer_weight

            return total_weight
        except Exception as e:
            logger.error(f"❌ Total weight calculation failed: {e}")
            return 0.0

    def calculate_payout(
        self,
        coverage: float,
    ) -> Tuple[int, int, int]:
        """Calculate payout from coverage percentage.

        Uses convex payout curve: gross = round(300 * (p ** 1.5))

        Vault split:
        - If gross <= 100: wallet_award = gross, vault_award = 0
        - Else: vault_award = int((gross - 100) * 0.30), wallet_award = remaining

        Args:
            coverage: Coverage (0-1)

        Returns:
            (wallet_award, vault_award, gross_payout)
        """
        try:
            # Convex payout curve
            gross = round(self.max_payout * (coverage ** self.payout_exponent))
            gross = max(0, min(self.max_payout, gross))

            # Vault split
            if gross <= 100:
                wallet_award = gross
                vault_award = 0
            else:
                extra = gross - 100
                vault_award = int(extra * self.vault_split_rate)
                wallet_award = gross - vault_award

            # Net wallet change
            net_wallet = wallet_award - 100  # Minus entry cost

            logger.debug(
                f"💰 Payout: coverage={coverage:.1%} → "
                f"gross={gross}, wallet={wallet_award}, vault={vault_award}, net={net_wallet}"
            )
            return wallet_award, vault_award, gross
        except Exception as e:
            logger.error(f"❌ Payout calculation failed: {e}")
            return 0, 0, 0

    async def update_answer_stats(
        self,
        db: AsyncSession,
        round: TLRound,
    ) -> None:
        """Update answer stats after round completion.

        For all snapshot answers: increment shows
        For matched answers: increment contributed_matches

        Args:
            db: Database session
            round: Completed TLRound
        """
        try:
            if not round.snapshot_answer_ids or not round.matched_clusters:
                return

            # Get all snapshot answers
            result = await db.execute(
                select(TLAnswer).where(
                    TLAnswer.answer_id.in_(round.snapshot_answer_ids)
                )
            )
            all_answers = {a.answer_id: a for a in result.scalars().all()}

            # Increment shows for all snapshot answers
            for answer in all_answers.values():
                answer.shows = (answer.shows or 0) + 1

            # Increment contributed_matches for matched answers
            if round.matched_clusters:
                result = await db.execute(
                    select(TLAnswer).where(
                        TLAnswer.cluster_id.in_(round.matched_clusters),
                        TLAnswer.answer_id.in_(round.snapshot_answer_ids)
                    )
                )
                matched_answers = result.scalars().all()
                for answer in matched_answers:
                    answer.contributed_matches = (answer.contributed_matches or 0) + 1

            await db.flush()
            logger.debug(
                f"✅ Updated stats: shows +1 for {len(all_answers)} answers, "
                f"contributed_matches +1 for {len(matched_answers)} matched"
            )
        except Exception as e:
            logger.error(f"❌ Answer stats update failed: {e}")

    async def finalize_round(
        self,
        db: AsyncSession,
        round: TLRound,
        wallet_award: int,
        vault_award: int,
        gross_payout: int,
        coverage: float,
    ) -> None:
        """Finalize round with final scores and statistics.

        Args:
            db: Database session
            round: TLRound to finalize
            wallet_award: Amount to add to wallet
            vault_award: Amount to add to vault
            gross_payout: Gross payout amount
            coverage: Final coverage (0-1)
        """
        try:
            round.status = 'completed'
            round.final_coverage = coverage
            round.gross_payout = gross_payout
            round.ended_at = func.now()  # Server timestamp

            # Update answer stats
            await self.update_answer_stats(db, round)

            await db.flush()
            logger.debug(
                f"✅ Finalized round {round.round_id}: "
                f"coverage={coverage:.1%}, gross={gross_payout}, "
                f"wallet={wallet_award}, vault={vault_award}"
            )
        except Exception as e:
            logger.error(f"❌ Round finalization failed: {e}")
            raise
