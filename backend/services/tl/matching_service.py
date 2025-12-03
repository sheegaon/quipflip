"""ThinkLink semantic matching service.

Handles embedding generation, cosine similarity calculations, and answer matching.
"""
import logging
import numpy as np
from typing import List, Optional, Dict, Tuple
from openai import AsyncOpenAI
from backend.config import get_settings

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
        self.embedding_cache: Dict[str, List[float]] = {}

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI.

        Caches embeddings to avoid duplicate API calls for the same text.

        Args:
            text: Text to embed

        Returns:
            1536-dimensional embedding vector
        """
        # Check cache first
        if text in self.embedding_cache:
            logger.debug(f"🔄 Using cached embedding for: {text[:50]}...")
            return self.embedding_cache[text]

        try:
            logger.debug(f"📞 Generating embedding for: {text[:50]}...")
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=1536,
            )
            embedding = response.data[0].embedding
            # Cache for this session
            self.embedding_cache[text] = embedding
            logger.debug(f"✅ Embedding generated (cache size: {len(self.embedding_cache)})")
            return embedding
        except Exception as e:
            logger.error(f"❌ Failed to generate embedding: {e}")
            raise

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

            query = np.array(query_vec, dtype=np.float32)
            candidates = np.array(candidate_vecs, dtype=np.float32)

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
            logger.debug(
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
            logger.debug(
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
                logger.debug("🎯 No snapshot answers to match against")
                return []

            # Extract embeddings from snapshot answers
            snapshot_embeddings = [a["embedding"] for a in snapshot_answers]

            # Batch similarity calculation
            similarities = self.batch_cosine_similarity(guess_embedding, snapshot_embeddings)

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
            logger.debug(
                f"🎯 Found {len(matches)} matches for '{guess_text[:30]}...' "
                f"(threshold={threshold})"
            )
            return matches
        except Exception as e:
            logger.error(f"❌ Find matches failed: {e}")
            return []
