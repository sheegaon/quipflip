"""ThinkLink clustering service.

Manages semantic cluster assignment, maintenance, and pruning.
"""
import logging
import math
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, bindparam
from sqlalchemy.orm import load_only
from backend.models.tl import TLCluster, TLAnswer
from backend.services.tl.matching_service import TLMatchingService

logger = logging.getLogger(__name__)

# Configuration
CLUSTER_JOIN_THRESHOLD = 0.75
CLUSTER_DUPLICATE_THRESHOLD = 0.90


class TLClusteringService:
    """Service for semantic clustering of answers."""

    def __init__(self, matching_service: TLMatchingService | None = None):
        """Initialize clustering service.

        Args:
            matching_service: MatchingService instance for similarity calculations
        """
        self.matching = matching_service or TLMatchingService()

    async def assign_cluster(
        self,
        db: AsyncSession,
        prompt_id: str,
        answer_embedding: List[float],
        answer_id: str,
    ) -> str:
        """Assign an answer to a cluster (create new if needed).

        Algorithm:
        1. Find all cluster centroids for the prompt
        2. Calculate similarity to each centroid
        3. If max_sim >= 0.75: join that cluster, update centroid
        4. Else: create new cluster

        Args:
            db: Database session
            prompt_id: Prompt ID
            answer_embedding: Answer embedding vector
            answer_id: Answer ID for tracking

        Returns:
            cluster_id of assigned cluster
        """
        try:
            logger.info(f"🔄 Assigning cluster for answer: {answer_id}")

            # Use raw SQL to get clusters with centroids (avoids pgvector deserialization bug)
            # Cast vector to text, then parse as array
            result = await db.execute(
                text("""
                    SELECT cluster_id::text, size,
                           centroid_embedding::text
                    FROM tl_cluster
                    WHERE prompt_id = :prompt_id
                """),
                {"prompt_id": prompt_id}
            )
            rows = result.fetchall()

            if not rows:
                # Create new cluster
                logger.info(f"📝 Creating new cluster for prompt {prompt_id}")
                new_cluster = TLCluster(
                    prompt_id=prompt_id,
                    centroid_embedding=answer_embedding,
                    size=1,
                    example_answer_id=answer_id,
                )
                db.add(new_cluster)
                await db.flush()
                logger.info(f"✅ Created cluster {new_cluster.cluster_id}")
                return str(new_cluster.cluster_id)

            # Find best matching cluster
            best_cluster_id = None
            best_cluster_size = 0
            best_similarity = -1.0

            for row in rows:
                cluster_id, size, centroid_text = row
                # Parse centroid from pgvector text format: "[0.1,0.2,...]"
                centroid = self._parse_vector_text(centroid_text)

                similarity = self.matching.cosine_similarity(
                    answer_embedding,
                    centroid
                )
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_cluster_id = cluster_id
                    best_cluster_size = size

            # Decide action based on similarity threshold
            if best_similarity >= CLUSTER_JOIN_THRESHOLD:
                # Join existing cluster - update via raw SQL to avoid pgvector issues
                logger.debug(
                    f"🔗 Joining cluster {best_cluster_id} "
                    f"(similarity={best_similarity:.3f})"
                )
                await self._update_centroid_raw(
                    db, best_cluster_id, best_cluster_size, answer_embedding
                )
                return best_cluster_id
            else:
                # Create new cluster
                logger.debug(
                    f"📝 Creating new cluster (best_sim={best_similarity:.3f} < threshold)"
                )
                new_cluster = TLCluster(
                    prompt_id=prompt_id,
                    centroid_embedding=answer_embedding,
                    size=1,
                    example_answer_id=answer_id,
                )
                db.add(new_cluster)
                await db.flush()
                logger.debug(f"✅ Created cluster {new_cluster.cluster_id}")
                return str(new_cluster.cluster_id)
        except Exception as e:
            logger.error(f"❌ Cluster assignment failed: {e}")
            raise

    def _parse_vector_text(self, vector_text: str) -> List[float]:
        """Parse pgvector text format to list of floats.

        pgvector returns vectors as "[0.1,0.2,0.3,...]"

        Args:
            vector_text: Vector as text string

        Returns:
            List of floats
        """
        # Remove brackets and split by comma
        cleaned = vector_text.strip("[]")
        return [float(x) for x in cleaned.split(",")]

    async def _update_centroid_raw(
        self,
        db: AsyncSession,
        cluster_id: str,
        old_size: int,
        new_embedding: List[float]
    ) -> None:
        """Update cluster centroid using raw SQL (avoids pgvector deserialization).

        Formula: new_centroid = (old_centroid * n + new_embedding) / (n + 1)

        Args:
            db: Database session
            cluster_id: Cluster ID to update
            old_size: Current cluster size
            new_embedding: New answer embedding
        """
        try:
            # First get the old centroid via raw SQL
            result = await db.execute(
                text("SELECT centroid_embedding::text FROM tl_cluster WHERE cluster_id = :cluster_id"),
                {"cluster_id": cluster_id}
            )
            row = result.fetchone()
            if not row:
                logger.error(f"❌ Cluster {cluster_id} not found for centroid update")
                return

            old_centroid = self._parse_vector_text(row[0])

            # Calculate new centroid using running mean
            new_centroid = [
                (old * old_size + new) / (old_size + 1)
                for old, new in zip(old_centroid, new_embedding)
            ]

            # Update via raw SQL
            centroid_str = "[" + ",".join(str(x) for x in new_centroid) + "]"
            update_stmt = text("""
                    UPDATE tl_cluster
                    SET centroid_embedding = CAST(:centroid AS vector),
                        size = :new_size,
                        updated_at = NOW()
                    WHERE cluster_id = :cluster_id
                """)

            # Explicitly bind params to ensure asyncpg compiles placeholders correctly
            update_stmt = update_stmt.bindparams(
                bindparam("centroid"),
                bindparam("new_size"),
                bindparam("cluster_id"),
            )

            await db.execute(
                update_stmt,
                {
                    "centroid": centroid_str,
                    "new_size": old_size + 1,
                    "cluster_id": cluster_id
                }
            )
            logger.debug(f"🔄 Updated centroid for cluster {cluster_id}, size={old_size + 1}")
        except Exception as e:
            logger.error(f"❌ Centroid update failed: {e}")
            raise

    async def _update_centroid(
        self,
        db: AsyncSession,
        cluster: TLCluster,
        new_embedding: List[float]
    ) -> None:
        """Update cluster centroid using running mean (legacy ORM method).

        Note: May fail with pgvector deserialization bug. Use _update_centroid_raw instead.

        Formula: new_centroid = (old_centroid * n + new_embedding) / (n + 1)

        Args:
            db: Database session
            cluster: TLCluster to update
            new_embedding: New answer embedding
        """
        try:
            old_size = cluster.size
            old_centroid = cluster.centroid_embedding

            # Calculate new centroid using running mean
            if isinstance(old_centroid, list):
                old_array = old_centroid
            else:
                old_array = old_centroid.tolist() if hasattr(old_centroid, 'tolist') else list(old_centroid)

            new_centroid = [
                (old * old_size + new) / (old_size + 1)
                for old, new in zip(old_array, new_embedding)
            ]

            cluster.centroid_embedding = new_centroid
            cluster.size = old_size + 1
            logger.debug(f"🔄 Updated centroid for cluster {cluster.cluster_id}, size={cluster.size}")
        except Exception as e:
            logger.error(f"❌ Centroid update failed: {e}")
            raise

    async def calculate_cluster_weight(
        self,
        db: AsyncSession,
        cluster_id: str,
    ) -> float:
        """Calculate weight of a cluster.

        Weight = sum of answer weights in cluster
        Answer weight = 1 + log(1 + min(answer_players_count, 20))

        Args:
            db: Database session
            cluster_id: Cluster ID

        Returns:
            Cluster weight
        """
        try:
            # Get all answers in cluster
            result = await db.execute(
                select(TLAnswer).where(TLAnswer.cluster_id == cluster_id)
            )
            answers = result.scalars().all()

            if not answers:
                return 0.0

            total_weight = 0.0
            for answer in answers:
                # Cap at 20, then apply logarithmic scaling
                capped_count = min(answer.answer_players_count or 0, 20)
                answer_weight = 1.0 + math.log(1.0 + float(capped_count))
                total_weight += answer_weight

            logger.debug(f"⚖️  Cluster {cluster_id}: weight={total_weight:.2f} from {len(answers)} answers")
            return total_weight
        except Exception as e:
            logger.error(f"❌ Cluster weight calculation failed: {e}")
            return 0.0

    async def calculate_usefulness(
        self,
        answer: TLAnswer,
        smoothing: float = 1.0
    ) -> float:
        """Calculate usefulness metric for an answer.

        Usefulness = contributed_matches / (shows + smoothing)

        Args:
            answer: TLAnswer model
            smoothing: Smoothing factor to avoid division by zero

        Returns:
            Usefulness score (0-1)
        """
        try:
            shows = answer.shows or 0
            contributed_matches = answer.contributed_matches or 0

            if shows + smoothing == 0:
                return 0.0

            usefulness = float(contributed_matches) / float(shows + smoothing)
            return min(1.0, max(0.0, usefulness))
        except Exception as e:
            logger.error(f"❌ Usefulness calculation failed: {e}")
            return 0.0

    async def prune_corpus(
        self,
        db: AsyncSession,
        prompt_id: str,
        keep_count: int = 1000,
    ) -> Tuple[int, int]:
        """Prune inactive answers to maintain corpus cap.

        Strategy:
        1. Mark answers with lowest usefulness * weight as inactive
        2. Preserve cluster diversity (don't remove all members of a cluster)

        Args:
            db: Database session
            prompt_id: Prompt ID
            keep_count: Maximum active answers to keep

        Returns:
            (removed_count, current_active_count)
        """
        try:
            logger.debug(f"🧹 Pruning corpus for prompt {prompt_id}, target={keep_count}")

            # Get all active answers
            result = await db.execute(
                select(TLAnswer).where(
                    TLAnswer.prompt_id == prompt_id,
                    TLAnswer.is_active == True
                )
            )
            active_answers = result.scalars().all()

            if len(active_answers) <= keep_count:
                logger.debug(f"✅ Corpus within cap ({len(active_answers)} <= {keep_count})")
                return 0, len(active_answers)

            # Group answers by cluster to preserve diversity
            clusters_map = {}
            unclustered = []
            for answer in active_answers:
                if answer.cluster_id:
                    if answer.cluster_id not in clusters_map:
                        clusters_map[answer.cluster_id] = []
                    clusters_map[answer.cluster_id].append(answer)
                else:
                    unclustered.append(answer)

            # Score each answer by usefulness (lower = better candidate for removal)
            scored_answers = []
            for answer in active_answers:
                usefulness = await self.calculate_usefulness(answer)
                scored_answers.append((answer, usefulness))

            # Sort by score (ascending - remove lowest usefulness first)
            scored_answers.sort(key=lambda x: x[1])

            # Mark lowest-scoring answers as inactive, preserving cluster diversity
            to_remove_count = len(active_answers) - keep_count
            removed = 0
            marked_for_removal = set()

            for answer, score in scored_answers:
                if removed >= to_remove_count:
                    break

                # Check if this is the last answer in its cluster
                if answer.cluster_id and answer.cluster_id in clusters_map:
                    cluster_answers = clusters_map[answer.cluster_id]
                    active_count = sum(1 for a in cluster_answers if a.answer_id not in marked_for_removal)

                    # Preserve at least one answer per cluster
                    if active_count <= 1:
                        continue

                # Safe to remove
                answer.is_active = False
                marked_for_removal.add(answer.answer_id)
                removed += 1
                logger.debug(
                    f"🗑️  Marked answer {answer.answer_id} inactive "
                    f"(usefulness={score:.3f})"
                )

            await db.flush()
            logger.debug(f"✅ Pruned {removed} answers, remaining={len(active_answers) - removed}")
            return removed, len(active_answers) - removed
        except Exception as e:
            logger.error(f"❌ Corpus pruning failed: {e}")
            return 0, 0
