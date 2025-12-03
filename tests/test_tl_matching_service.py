"""Unit tests for ThinkLink MatchingService."""
import pytest
import os
from backend.services.tl.matching_service import TLMatchingService
from unittest.mock import Mock, AsyncMock


class TestMatchingService:
    """Test suite for MatchingService."""

    @pytest.fixture
    def matching_service(self):
        """Create a MatchingService instance.

        Skips tests if OPENAI_API_KEY is not configured.
        """
        if not os.getenv('OPENAI_API_KEY'):
            pytest.skip("OPENAI_API_KEY not configured - skipping live API tests")
        return TLMatchingService()

    @pytest.fixture
    def matching_service_mock(self):
        """Create a mock MatchingService for tests that don't need real API calls."""
        service = Mock(spec=TLMatchingService)
        service.embedding_cache = {}
        return service

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_vector(self, matching_service):
        """Test that generate_embedding returns a 1536-dim vector."""
        text = "Name something people forget at home"
        embedding = await matching_service.generate_embedding(text)

        assert embedding is not None
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_generate_embedding_caching(self, matching_service):
        """Test that embeddings are cached (same text returns same embedding)."""
        text = "Keys"
        embedding1 = await matching_service.generate_embedding(text)
        embedding2 = await matching_service.generate_embedding(text)

        # Should be the exact same embedding due to caching
        assert embedding1 == embedding2

    @pytest.mark.asyncio
    async def test_generate_embedding_different_text(self, matching_service):
        """Test that different texts produce different embeddings."""
        embedding1 = await matching_service.generate_embedding("Keys")
        embedding2 = await matching_service.generate_embedding("Door")

        # Different texts should produce different embeddings
        assert embedding1 != embedding2

    def test_cosine_similarity_identical_vectors(self, matching_service_mock):
        """Test cosine similarity of identical vectors is 1.0."""
        vec = [1.0, 0.0, 0.0]
        similarity = TLMatchingService.cosine_similarity(vec, vec)

        assert similarity == pytest.approx(1.0, abs=0.001)

    def test_cosine_similarity_orthogonal_vectors(self, matching_service_mock):
        """Test cosine similarity of orthogonal vectors is ~0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        similarity = TLMatchingService.cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(0.0, abs=0.001)

    def test_cosine_similarity_opposite_vectors(self, matching_service_mock):
        """Test cosine similarity of opposite vectors is clamped to 0.0.

        The implementation clamps to [0, 1] to avoid penalizing opposite meanings
        in semantic matching - we just care if vectors are similar or not.
        """
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        similarity = TLMatchingService.cosine_similarity(vec1, vec2)

        # Opposite vectors have dot product of -1, clamped to 0
        assert similarity == pytest.approx(0.0, abs=0.001)

    def test_batch_cosine_similarity_single_candidate(self, matching_service_mock):
        """Test batch similarity with one candidate."""
        query_vec = [1.0, 0.0, 0.0]
        candidate_vecs = [[1.0, 0.0, 0.0]]
        similarities = TLMatchingService.batch_cosine_similarity(
            query_vec, candidate_vecs
        )

        assert len(similarities) == 1
        assert similarities[0] == pytest.approx(1.0, abs=0.001)

    def test_batch_cosine_similarity_multiple_candidates(self, matching_service_mock):
        """Test batch similarity with multiple candidates.

        Note: Values are clamped to [0, 1], so opposite vectors return 0.
        """
        query_vec = [1.0, 0.0, 0.0]
        candidate_vecs = [
            [1.0, 0.0, 0.0],   # identical
            [0.0, 1.0, 0.0],   # orthogonal
            [-1.0, 0.0, 0.0],  # opposite (clamped to 0)
        ]
        similarities = TLMatchingService.batch_cosine_similarity(
            query_vec, candidate_vecs
        )

        assert len(similarities) == 3
        assert similarities[0] == pytest.approx(1.0, abs=0.001)
        assert similarities[1] == pytest.approx(0.0, abs=0.001)
        assert similarities[2] == pytest.approx(0.0, abs=0.001)  # Clamped from -1.0

    @pytest.mark.asyncio
    async def test_check_on_topic_with_low_threshold(self, matching_service):
        """Test on-topic check returns consistent results with threshold."""
        prompt = "Name something people forget at home"
        guess = "Wallet"

        # Check with very low threshold - should be on topic
        is_on_topic, similarity = await matching_service.check_on_topic(
            prompt, guess, threshold=0.01
        )

        # With a low threshold, even semantic relationship should pass
        assert is_on_topic is True
        assert similarity >= 0.01

    @pytest.mark.asyncio
    async def test_check_on_topic_with_high_threshold(self, matching_service):
        """Test on-topic check with very high threshold."""
        prompt = "Name something people forget at home"
        guess = "Quantum entanglement physics experiment"

        # Check with high threshold - should be off topic
        is_on_topic, similarity = await matching_service.check_on_topic(
            prompt, guess, threshold=0.95
        )

        # Quantum physics is unrelated to forgetting things
        assert is_on_topic is False
        assert similarity < 0.95

    @pytest.mark.asyncio
    async def test_check_self_similarity_identical_guess(self, matching_service):
        """Test self-similarity rejects identical prior guess."""
        guess_text = "Keys"
        prior_guesses = ["Keys", "Door", "Phone"]

        is_too_similar, max_sim = await matching_service.check_self_similarity(
            guess_text, prior_guesses, threshold=0.80
        )

        # Identical text should definitely be flagged as too similar
        assert is_too_similar is True
        assert max_sim == pytest.approx(1.0, abs=0.001)

    @pytest.mark.asyncio
    async def test_check_self_similarity_different_guess(self, matching_service):
        """Test self-similarity allows different prior guesses."""
        guess_text = "Keys"
        prior_guesses = ["Phone", "Wallet", "Door"]

        is_too_similar, max_sim = await matching_service.check_self_similarity(
            guess_text, prior_guesses, threshold=0.80
        )

        # "Keys" is different from the prior guesses
        assert is_too_similar is False
        # But some similarity due to semantic similarity
        assert max_sim is not None
        assert max_sim < 0.80

    @pytest.mark.asyncio
    async def test_find_matches_with_similar_answers(self, matching_service):
        """Test finding matches in snapshot answers."""
        guess_text = "Keys"
        guess_embedding = await matching_service.generate_embedding(guess_text)

        # Create mock snapshot answers with embeddings
        keys_embedding = await matching_service.generate_embedding("Keys")
        wallet_embedding = await matching_service.generate_embedding("Wallet")
        door_embedding = await matching_service.generate_embedding("Door")

        snapshot_answers = [
            {
                "answer_id": "1",
                "text": "Keys",
                "embedding": keys_embedding,
                "cluster_id": "cluster1",
            },
            {
                "answer_id": "2",
                "text": "Wallet",
                "embedding": wallet_embedding,
                "cluster_id": "cluster2",
            },
            {
                "answer_id": "3",
                "text": "Door",
                "embedding": door_embedding,
                "cluster_id": "cluster3",
            },
        ]

        matches = await matching_service.find_matches(
            guess_text, guess_embedding, snapshot_answers, threshold=0.55
        )

        # Should match "Keys" at minimum
        assert len(matches) > 0
        # First match should be "Keys" (highest similarity)
        assert matches[0]["answer_id"] == "1"
        assert matches[0]["text"] == "Keys"

    @pytest.mark.asyncio
    async def test_find_matches_no_matches(self, matching_service):
        """Test finding matches when none exist."""
        guess_text = "Quantum entanglement"
        guess_embedding = await matching_service.generate_embedding(guess_text)

        keys_embedding = await matching_service.generate_embedding("Keys")
        wallet_embedding = await matching_service.generate_embedding("Wallet")

        snapshot_answers = [
            {
                "answer_id": "1",
                "text": "Keys",
                "embedding": keys_embedding,
                "cluster_id": "cluster1",
            },
            {
                "answer_id": "2",
                "text": "Wallet",
                "embedding": wallet_embedding,
                "cluster_id": "cluster2",
            },
        ]

        matches = await matching_service.find_matches(
            guess_text, guess_embedding, snapshot_answers, threshold=0.55
        )

        # Should find no matches for unrelated text
        assert len(matches) == 0
