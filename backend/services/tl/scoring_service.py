"""ThinkLink scoring service.

Calculates coverage, payouts, and manages round finalization.
"""
import logging
import math
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import func

from backend.models.tl import TLRound, TLAnswer
from backend.config import get_settings

logger = logging.getLogger(__name__)


class TLScoringService:
    """Service for ThinkLink scoring and payouts."""

    def __init__(self):
        """Initialize scoring service."""
        settings = get_settings()
        self.max_payout = settings.tl_max_payout
        self.payout_exponent = settings.tl_payout_exponent
        self.vault_split_rate = settings.tl_vault_rake_percent / 100.0

    async def calculate_coverage(self, db: AsyncSession, tl_round: TLRound) -> float:
        """Calculate weighted coverage percentage from round data.

        Coverage p = Σ(weight of matched clusters) / Σ(weight of all snapshot clusters)

        Args:
            db: Database session
            tl_round: TLRound with matched_clusters and snapshot data

        Returns:
            Coverage percentage (0-1)
        """
        try:
            snapshot_cluster_ids = list(set(tl_round.snapshot_cluster_ids or []))
            snapshot_answer_ids = tl_round.snapshot_answer_ids or []

            if not snapshot_cluster_ids or not snapshot_answer_ids:
                logger.info("🎯 No snapshot clusters - coverage = 0%")
                return 0.0

            # Calculate total weight of snapshot clusters
            total_weight = float(tl_round.snapshot_total_weight or 0.0)
            if total_weight <= 0.0:
                total_weight = await self.calculate_total_weight(
                    db,
                    snapshot_cluster_ids,
                    snapshot_answer_ids=snapshot_answer_ids,
                )

            if total_weight == 0:
                logger.info("🎯 Total weight = 0 - coverage = 0%")
                return 0.0

            # Calculate weight of matched clusters
            matched_cluster_ids = list(set(tl_round.matched_clusters or []))
            matched_weight = await self.calculate_cluster_weights_total(
                db,
                matched_cluster_ids,
                snapshot_answer_ids=snapshot_answer_ids,
            )

            coverage = float(matched_weight) / float(total_weight)
            coverage = max(0.0, min(1.0, coverage))  # Clamp to [0, 1]

            logger.info(
                f"📊 Coverage: {coverage:.1%} "
                f"(matched_weight={matched_weight:.2f} / total={total_weight:.2f})"
            )
            return coverage
        except Exception as e:
            logger.error(f"❌ Coverage calculation failed: {e}")
            return 0.0

    async def calculate_total_weight(
        self,
        db: AsyncSession,
        cluster_ids: List[str],
        snapshot_answer_ids: List[str] | None = None,
    ) -> float:
        """Calculate total weight for the snapshot (or active corpus).

        Args:
            db: Database session
            cluster_ids: Cluster IDs to include
            snapshot_answer_ids: Optional snapshot answer IDs to freeze weights

        Returns:
            Total weight across provided clusters
        """
        weights = await self._compute_cluster_weights(
            db,
            cluster_ids,
            answer_ids=snapshot_answer_ids,
            active_only=snapshot_answer_ids is None,
        )
        return sum(weights.values())

    async def calculate_cluster_weights_total(
        self,
        db: AsyncSession,
        cluster_ids: List[str],
        snapshot_answer_ids: List[str] | None = None,
    ) -> float:
        """Calculate total weight for a set of clusters using pre-calculated cluster weights.

        Args:
            db: Database session
            cluster_ids: List of cluster IDs
            snapshot_answer_ids: Optional snapshot answer IDs to freeze weights

        Returns:
            Total weight across all clusters
        """
        try:
            if not cluster_ids:
                return 0.0

            weights = await self._compute_cluster_weights(
                db,
                cluster_ids,
                answer_ids=snapshot_answer_ids,
                active_only=snapshot_answer_ids is None,
            )
            return sum(weights.values())
        except Exception as e:
            logger.error(f"❌ Cluster weights calculation failed: {e}")
            return 0.0

    async def get_cluster_weight(
        self,
        db: AsyncSession,
        cluster_id: str,
        snapshot_answer_ids: List[str] | None = None,
    ) -> float:
        """Get weight for a single cluster by summing its answer weights.

        Args:
            db: Database session
            cluster_id: Cluster ID
            snapshot_answer_ids: Optional snapshot answer IDs to freeze weights

        Returns:
            Cluster weight (sum of answer weights in cluster)
        """
        try:
            weights = await self._compute_cluster_weights(
                db,
                [cluster_id],
                answer_ids=snapshot_answer_ids,
                active_only=snapshot_answer_ids is None,
            )
            return weights.get(str(cluster_id), 0.0)
        except Exception as e:
            logger.error(f"❌ Cluster weight calculation failed for {cluster_id}: {e}")
            return 0.0

    async def _compute_cluster_weights(
        self,
        db: AsyncSession,
        cluster_ids: List[str],
        answer_ids: List[str] | None = None,
        active_only: bool = True,
    ) -> dict[str, float]:
        """Compute weights for clusters in a single query."""
        if not cluster_ids:
            return {}

        query = select(TLAnswer.cluster_id, TLAnswer.answer_players_count).where(
            TLAnswer.cluster_id.in_(cluster_ids)
        )

        if answer_ids:
            query = query.where(TLAnswer.answer_id.in_(answer_ids))
        elif active_only:
            query = query.where(TLAnswer.is_active == True)

        result = await db.execute(query)
        rows = result.fetchall()

        cluster_weights: dict[str, float] = {}
        for cluster_id, answer_players_count in rows:
            # Cap player count at 20, apply log scaling per spec
            capped_count = min(answer_players_count or 0, 20)
            answer_weight = 1.0 + math.log(1.0 + float(capped_count))
            key = str(cluster_id)
            cluster_weights[key] = cluster_weights.get(key, 0.0) + answer_weight

        return cluster_weights

    def calculate_payout(self, coverage: float) -> Tuple[int, int, int]:
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

            logger.info(
                f"💰 Payout: coverage={coverage:.1%} → "
                f"gross={gross}, wallet={wallet_award}, vault={vault_award}, net={net_wallet}"
            )
            return wallet_award, vault_award, gross
        except Exception as e:
            logger.error(f"❌ Payout calculation failed: {e}")
            return 0, 0, 0

    @staticmethod
    async def update_answer_stats(db: AsyncSession, tl_round: TLRound) -> None:
        """Update answer stats after round completion.

        For all snapshot answers: increment shows
        For matched answers: increment contributed_matches

        Args:
            db: Database session
            tl_round: Completed TLRound
        """
        try:
            if not tl_round.snapshot_answer_ids:
                return

            # Increment shows for all snapshot answers
            await db.execute(
                update(TLAnswer)
                .where(TLAnswer.answer_id.in_(tl_round.snapshot_answer_ids))
                .values(shows=TLAnswer.shows + 1)
            )

            # Increment contributed_matches for matched answers
            if tl_round.matched_clusters:
                await db.execute(
                    update(TLAnswer)
                    .where(
                        TLAnswer.cluster_id.in_(tl_round.matched_clusters),
                        TLAnswer.answer_id.in_(tl_round.snapshot_answer_ids)
                    )
                    .values(contributed_matches=TLAnswer.contributed_matches + 1)
                )

            await db.flush()
            logger.info(
                f"✅ Updated stats: shows +1 for {len(tl_round.snapshot_answer_ids)} answers, "
                f"contributed_matches +1 for matched answers in {len(tl_round.matched_clusters or [])} clusters"
            )
        except Exception as e:
            logger.error(f"❌ Answer stats update failed: {e}")

    async def finalize_round(
            self,
            db: AsyncSession,
            tl_round: TLRound,
            wallet_award: int,
            vault_award: int,
            gross_payout: int,
            coverage: float,
    ) -> None:
        """Finalize round with final scores, statistics, and player updates.

        Args:
            db: Database session
            tl_round: TLRound to finalize
            wallet_award: Amount to add to wallet
            vault_award: Amount to add to vault
            gross_payout: Gross payout amount
            coverage: Final coverage (0-1)
        """
        try:
            # Update round status and final scores
            tl_round.status = 'completed'
            tl_round.final_coverage = coverage
            tl_round.gross_payout = gross_payout
            tl_round.ended_at = func.now()  # Server timestamp

            # Update answer stats
            await self.update_answer_stats(db, tl_round)

            # Update player wallet and vault using transaction service
            if wallet_award > 0 or vault_award > 0:
                await self._update_player_balances(db, tl_round.player_id, wallet_award, vault_award, tl_round.round_id)

            await db.flush()
            logger.info(
                f"✅ Finalized round {tl_round.round_id}: "
                f"coverage={coverage:.1%}, gross={gross_payout}, "
                f"wallet={wallet_award}, vault={vault_award}"
            )
        except Exception as e:
            logger.error(f"❌ Round finalization failed: {e}")
            raise

    async def _update_player_balances(
        self, 
        db: AsyncSession, 
        player_id: str, 
        wallet_award: int, 
        vault_award: int, 
        round_id: str
    ) -> None:
        """Update player wallet and vault balances with transactions."""
        try:
            # Import here to avoid circular imports
            from backend.services.tl.transaction_service import TLTransactionService
            
            transaction_service = TLTransactionService(db)

            # Create wallet payout transaction
            if wallet_award > 0:
                await transaction_service.create_transaction(
                    player_id=player_id,
                    amount=wallet_award,
                    transaction_type="round_payout_wallet",
                    round_id=round_id,
                    description=f"Round payout (wallet): {wallet_award} coins"
                )

            # Create vault award transaction  
            if vault_award > 0:
                await transaction_service.create_transaction(
                    player_id=player_id,
                    amount=vault_award,
                    transaction_type="round_payout_vault",
                    round_id=round_id,
                    description=f"Round payout (vault): {vault_award} coins",
                    target_wallet="vault"
                )

            logger.info(f"✅ Updated balances for player {player_id}: wallet +{wallet_award}, vault +{vault_award}")

        except Exception as e:
            logger.error(f"❌ Failed to update player balances: {e}")
            raise
