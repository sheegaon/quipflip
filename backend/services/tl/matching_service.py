"""ThinkLink semantic matching service.

Handles embedding generation, cosine similarity calculations, and answer matching.
"""
import logging
import numpy as np
from typing import List, Optional, Dict, Tuple
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import get_settings
from backend.database import AsyncSessionLocal
from backend.models.phrase_embedding import PhraseEmbedding

logger = logging.getLogger(__name__)


class TLMatchingService:
    """Service for semantic matching using OpenAI embeddings."""

    def __init__(self):
        """Initialize the matching service."""
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for ThinkLink")

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.embedding_model = settings.embedding_model
        # In-memory cache for session performance (supplements DB cache)
        self.embedding_cache: Dict[str, List[float]] = {}
        # Track how many embeddings we've generated to checkpoint DB cache
        self._generated_count = 0

    async def generate_embedding(
        self,
        text: str,
        db: Optional[AsyncSession] = None
    ) -> List[float]:
        """Generate embedding for text using OpenAI with DB caching.

        Cache lookup order (enforced close to the API call):
        1. In-memory cache (session performance)
        2. Database cache (persists across restarts)
        3. OpenAI API (stores result in both caches)

        Args:
            text: Text to embed
            db: Optional database session (for transaction control during seeding)

        Returns:
            1536-dimensional embedding vector
        """
        normalized_text = text.strip().lower()

        # 1. Check in-memory cache first (fastest)
        if normalized_text in self.embedding_cache:
            logger.debug(f"🔄 In-memory cache hit: {text[:50]}...")
            return self.embedding_cache[normalized_text]

        # 2. Check DB cache right before calling the API
        embedding = await self._safe_get_cached_embedding(normalized_text, text, db)
        if embedding is not None:
            return embedding

        # 3. Generate via OpenAI API through the single root method
        embedding = await self._request_openai_embedding(text)

        # Store in both caches
        self.embedding_cache[normalized_text] = embedding
        await self._store_embedding(normalized_text, embedding, db)

        # Checkpoint DB cache every 100 new embeddings
        self._generated_count += 1
        await self._maybe_checkpoint_cache(db)

        logger.info(f"✅ Embedding generated (memory cache: {len(self.embedding_cache)})")
        return embedding

    async def _safe_get_cached_embedding(
        self,
        normalized_text: str,
        original_text: str,
        db: Optional[AsyncSession]
    ) -> Optional[List[float]]:
        """Check DB cache before invoking OpenAI, close to the API call."""
        try:
            embedding = await self._get_cached_embedding(normalized_text, db)
            if embedding is not None:
                self.embedding_cache[normalized_text] = embedding
                logger.info(f"💾 DB cache hit: {original_text[:50]}...")
                return embedding
        except Exception as e:
            logger.warning(f"⚠️ DB cache lookup failed: {e}")

        return None

    async def _request_openai_embedding(self, text: str) -> List[float]:
        """Root method that contacts OpenAI for embeddings."""
        try:
            logger.info(f"📞 Generating embedding for: {text[:50]}...")
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=1536,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"❌ Failed to generate embedding: {e}")
            raise

    async def _get_cached_embedding(
        self,
        text: str,
        db: Optional[AsyncSession] = None
    ) -> Optional[List[float]]:
        """Check DB for cached embedding."""
        async def _query(session: AsyncSession) -> Optional[List[float]]:
            result = await session.execute(
                select(PhraseEmbedding).where(
                    PhraseEmbedding.phrase == text,
                    PhraseEmbedding.model == self.embedding_model,
                )
            )
            cached = result.scalar_one_or_none()
            return cached.embedding if cached else None

        if db:
            return await _query(db)
        else:
            async with AsyncSessionLocal() as session:
                return await _query(session)

    async def _store_embedding(
        self,
        text: str,
        embedding: List[float],
        db: Optional[AsyncSession] = None
    ) -> None:
        """Store embedding in DB cache."""
        async def _store(session: AsyncSession, commit: bool = True) -> None:
            record = PhraseEmbedding(
                phrase=text,
                model=self.embedding_model,
                provider="openai",
                embedding=embedding,
            )
            session.add(record)
            if commit:
                try:
                    await session.commit()
                except IntegrityError:
                    # Already exists (race condition)
                    await session.rollback()

        if db:
            # External session - don't commit (caller controls transaction)
            record = PhraseEmbedding(
                phrase=text,
                model=self.embedding_model,
                provider="openai",
                embedding=embedding,
            )
            db.add(record)
            try:
                await db.flush()
            except IntegrityError:
                # Already exists
                pass
        else:
            async with AsyncSessionLocal() as session:
                await _store(session, commit=True)

    async def _maybe_checkpoint_cache(self, db: Optional[AsyncSession]) -> None:
        """Commit embedding cache progress every 100 new generations."""

        if self._generated_count % 100 != 0:
            return

        logger.info(f"💾 Embedding cache checkpoint reached: {self._generated_count} generated")

        if not db:
            # Each embedding is individually committed when using internal sessions
            return

        try:
            await db.commit()
            logger.info("✅ Cached embeddings committed (checkpoint)")
        except Exception as e:
            await db.rollback()
            logger.warning(f"⚠️ Failed to commit embedding cache checkpoint: {e}")

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec_a: First vector
            vec_b: Second vector

        Returns:
            Cosine similarity score (0-1, where 1 is identical)
        """
        try:
            a = np.array(vec_a, dtype=np.float32)
            b = np.array(vec_b, dtype=np.float32)

            # Compute cosine similarity: dot(a,b) / (||a|| * ||b||)
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            similarity = float(dot_product / (norm_a * norm_b))
            return max(0.0, min(1.0, similarity))  # Clamp to [0, 1]
        except Exception as e:
            logger.error(f"❌ Failed to calculate cosine similarity: {e}")
            return 0.0

    @staticmethod
    def batch_cosine_similarity(
        query_vec: List[float],
        candidate_vecs: List[List[float]]
    ) -> List[float]:
        """Calculate cosine similarity between query and multiple candidates (vectorized).

        Args:
            query_vec: Query embedding vector
            candidate_vecs: List of candidate embedding vectors

        Returns:
            List of similarity scores
        """
        try:
            if not candidate_vecs:
                return []

            # Debug: Log types and sample values to diagnose conversion issues
            logger.info(
                f"🔬 batch_cosine_similarity: query_vec type={type(query_vec).__name__}, "
                f"len={len(query_vec) if hasattr(query_vec, '__len__') else 'N/A'}"
            )
            if candidate_vecs:
                first_candidate = candidate_vecs[0]
                logger.info(
                    f"🔬 First candidate type={type(first_candidate).__name__}, "
                    f"len={len(first_candidate) if hasattr(first_candidate, '__len__') else 'N/A'}"
                )

            # Convert to list if needed (pgvector may return numpy array or special type)
            if hasattr(query_vec, 'tolist'):
                query_vec = query_vec.tolist()
            converted_candidates = []
            for cv in candidate_vecs:
                if hasattr(cv, 'tolist'):
                    converted_candidates.append(cv.tolist())
                else:
                    converted_candidates.append(list(cv) if not isinstance(cv, list) else cv)

            query = np.array(query_vec, dtype=np.float32)
            candidates = np.array(converted_candidates, dtype=np.float32)

            # Vectorized dot products
            dot_products = np.dot(candidates, query)

            # Vectorized norms
            query_norm = np.linalg.norm(query)
            candidate_norms = np.linalg.norm(candidates, axis=1)

            if query_norm == 0:
                return [0.0] * len(candidate_vecs)

            # Vectorized cosine similarity
            similarities = dot_products / (candidate_norms * query_norm)
            # Clamp to [0, 1]
            similarities = np.clip(similarities, 0.0, 1.0)
            return similarities.tolist()
        except Exception as e:
            logger.error(f"❌ Failed batch cosine similarity: {e}")
            return [0.0] * len(candidate_vecs)

    async def check_on_topic(
        self,
        prompt_text: str,
        answer_text: str,
        prompt_embedding: Optional[List[float]] = None,
        threshold: float = 0.40
    ) -> Tuple[bool, float]:
        """Check if answer is semantically related to prompt.

        Args:
            prompt_text: Prompt text
            answer_text: Answer text to validate
            prompt_embedding: Pre-computed prompt embedding (optional)
            threshold: Minimum similarity threshold

        Returns:
            (is_on_topic, similarity_score)
        """
        try:
            # Get or generate prompt embedding
            if prompt_embedding is None:
                prompt_embedding = await self.generate_embedding(prompt_text)

            # Generate answer embedding
            answer_embedding = await self.generate_embedding(answer_text)

            # Calculate similarity
            similarity = self.cosine_similarity(prompt_embedding, answer_embedding)

            is_on_topic = similarity >= threshold
            logger.info(
                f"🎯 On-topic check: '{answer_text[:30]}...' "
                f"similarity={similarity:.3f}, threshold={threshold}, "
                f"on_topic={is_on_topic}"
            )
            return is_on_topic, similarity
        except Exception as e:
            logger.error(f"❌ On-topic check failed: {e}")
            return False, 0.0

    async def check_self_similarity(
        self,
        guess_text: str,
        prior_guesses: List[str],
        threshold: float = 0.80
    ) -> Tuple[bool, Optional[float]]:
        """Check if guess is too similar to player's prior guesses.

        Args:
            guess_text: Current guess
            prior_guesses: List of prior guesses in this round
            threshold: Maximum allowed similarity

        Returns:
            (is_too_similar, max_similarity_to_prior)
        """
        try:
            if not prior_guesses:
                return False, None

            guess_embedding = await self.generate_embedding(guess_text)
            prior_embeddings = [await self.generate_embedding(g) for g in prior_guesses]

            similarities = self.batch_cosine_similarity(guess_embedding, prior_embeddings)
            max_similarity = max(similarities) if similarities else 0.0

            is_too_similar = max_similarity >= threshold
            logger.info(
                f"🔍 Self-similarity check: max={max_similarity:.3f}, "
                f"threshold={threshold}, too_similar={is_too_similar}"
            )
            return is_too_similar, max_similarity
        except Exception as e:
            logger.error(f"❌ Self-similarity check failed: {e}")
            return False, None

    async def find_matches(
        self,
        guess_text: str,
        guess_embedding: List[float],
        snapshot_answers: List[Dict],
        threshold: float = 0.55
    ) -> List[Dict]:
        """Find matching snapshot answers for a guess.

        Args:
            guess_text: Guess text (for logging)
            guess_embedding: Guess embedding
            snapshot_answers: List of snapshot answers with {answer_id, text, embedding, cluster_id}
            threshold: Minimum similarity threshold

        Returns:
            List of matched answers with {answer_id, text, similarity, cluster_id}
        """
        try:
            if not snapshot_answers:
                logger.info("🎯 No snapshot answers to match against")
                return []

            # Extract embeddings from snapshot answers
            snapshot_embeddings = [a["embedding"] for a in snapshot_answers]

            # Batch similarity calculation
            similarities = self.batch_cosine_similarity(guess_embedding, snapshot_embeddings)

            # DEBUG: Always log the highest similarity and corresponding answer
            if similarities:
                max_sim = max(similarities)
                max_idx = similarities.index(max_sim)
                best_answer = snapshot_answers[max_idx]
                logger.info(
                    f"🔍 SIMILARITY DEBUG for '{guess_text}': "
                    f"highest_sim={max_sim:.4f}, threshold={threshold}, "
                    f"best_match='{best_answer['text']}'"
                )
                # Log top 5 similarities for more context
                sorted_sims = sorted(enumerate(similarities), key=lambda x: x[1], reverse=True)[:5]
                for rank, (idx, sim) in enumerate(sorted_sims, 1):
                    logger.info(f"   #{rank}: sim={sim:.4f} - '{snapshot_answers[idx]['text']}'")
            else:
                logger.info(f"🔍 SIMILARITY DEBUG for '{guess_text}': No similarities computed.")

            # Find matches above threshold
            matches = []
            for i, (answer, similarity) in enumerate(zip(snapshot_answers, similarities)):
                if similarity >= threshold:
                    matches.append({
                        "answer_id": answer["answer_id"],
                        "text": answer["text"],
                        "similarity": float(similarity),
                        "cluster_id": answer["cluster_id"],
                    })

            # Sort by similarity descending
            matches.sort(key=lambda x: x["similarity"], reverse=True)
            logger.info(
                f"🎯 Found {len(matches)} matches for '{guess_text[:30]}...' "
                f"(threshold={threshold})"
            )
            return matches
        except Exception as e:
            logger.error(f"❌ Find matches failed: {e}")
            return []
