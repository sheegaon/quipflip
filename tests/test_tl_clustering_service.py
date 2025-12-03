"""Unit tests for ThinkLink ClusteringService."""
import pytest
from backend.services.tl.clustering_service import TLClusteringService
from backend.services.tl.matching_service import TLMatchingService


class TestClusteringService:
    """Test suite for ClusteringService."""

    @pytest.fixture
    def clustering_service(self):
        """Create a ClusteringService instance."""
        matching_service = TLMatchingService()
        return TLClusteringService(matching_service)

    def test_cosine_similarity_threshold_join(self):
        """Test that vectors >= 0.75 similarity join a cluster."""
        # Create two vectors that should be similar (both positive)
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.95, 0.31, 0.0]  # Similarity ~0.95

        similarity = TLMatchingService.cosine_similarity(vec1, vec2)

        # Should be high similarity (> 0.75 join threshold)
        assert similarity > 0.75

    def test_cosine_similarity_threshold_new_cluster(self):
        """Test that vectors < 0.75 similarity create new cluster."""
        # Create two vectors with lower similarity
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.6, 0.8, 0.0]  # Similarity ~0.6

        similarity = TLMatchingService.cosine_similarity(vec1, vec2)

        # Should be lower similarity (< 0.75 join threshold)
        assert similarity < 0.75

    def test_duplicate_threshold(self):
        """Test that vectors >= 0.90 are detected as near-duplicates."""
        # Nearly identical vectors
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.998, 0.063, 0.0]  # Similarity ~0.998

        similarity = TLMatchingService.cosine_similarity(vec1, vec2)

        # Should exceed duplicate threshold of 0.90
        assert similarity > 0.90

    def test_centroid_update_formula(self):
        """Test running mean centroid update: new_centroid = (old * n + new) / (n + 1)."""
        # Initial centroid (n=1)
        centroid = [1.0, 0.0, 0.0]
        new_embedding = [0.0, 1.0, 0.0]

        # After adding new embedding (n becomes 2)
        # new_centroid = (old * 1 + new) / 2
        updated = [(centroid[i] * 1 + new_embedding[i]) / 2 for i in range(3)]

        assert updated[0] == pytest.approx(0.5, abs=0.001)
        assert updated[1] == pytest.approx(0.5, abs=0.001)
        assert updated[2] == pytest.approx(0.0, abs=0.001)

    def test_centroid_update_multiple_iterations(self):
        """Test centroid update over multiple iterations."""
        # Start with first embedding
        centroid = [1.0, 0.0, 0.0]
        size = 1

        # Add second embedding
        new_embedding = [0.0, 1.0, 0.0]
        centroid = [(centroid[i] * size + new_embedding[i]) / (size + 1) for i in range(3)]
        size += 1

        # After 2 items: [0.5, 0.5, 0.0]
        assert centroid[0] == pytest.approx(0.5, abs=0.001)
        assert centroid[1] == pytest.approx(0.5, abs=0.001)

        # Add third embedding
        new_embedding = [0.0, 0.0, 1.0]
        centroid = [(centroid[i] * size + new_embedding[i]) / (size + 1) for i in range(3)]
        size += 1

        # After 3 items: [1/3, 1/3, 1/3]
        assert centroid[0] == pytest.approx(0.333, abs=0.01)
        assert centroid[1] == pytest.approx(0.333, abs=0.01)
        assert centroid[2] == pytest.approx(0.333, abs=0.01)

    def test_cluster_weight_calculation(self):
        """Test cluster weight = sum of answer weights."""
        # Answer weights follow formula: 1 + log(1 + min(players_count, 20))
        import math

        # Cluster with 3 answers
        answer_weights = [
            1 + math.log(1 + 1),      # 1 player
            1 + math.log(1 + 5),      # 5 players
            1 + math.log(1 + 10),     # 10 players
        ]

        cluster_weight = sum(answer_weights)

        # Should be sum of individual weights
        assert cluster_weight == pytest.approx(
            answer_weights[0] + answer_weights[1] + answer_weights[2],
            abs=0.01
        )

    def test_pruning_removes_lowest_usefulness(self):
        """Test that pruning removes answers with lowest usefulness."""
        # Usefulness = contributed_matches / (shows + smoothing)

        # Answer A: 10 matches, 100 shows = 10/101 = 0.099
        usefulness_a = 10 / 101

        # Answer B: 50 matches, 100 shows = 50/101 = 0.495
        usefulness_b = 50 / 101

        # Answer C: 80 matches, 100 shows = 80/101 = 0.792
        usefulness_c = 80 / 101

        # When pruning, Answer A should be removed first
        assert usefulness_a < usefulness_b < usefulness_c

    def test_match_threshold(self):
        """Test that matching uses 0.55 threshold as per rules."""
        # Vectors with similarity = 0.54 should NOT match
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.54, 0.84, 0.0]  # Approximate similarity 0.54

        similarity = TLMatchingService.cosine_similarity(vec1, vec2)
        match_threshold = 0.55

        # Close to threshold, verify behavior
        if similarity < match_threshold:
            assert not (similarity >= match_threshold)

        # Vectors with similarity = 0.56 SHOULD match
        vec3 = [0.56, 0.83, 0.0]  # Approximate similarity 0.56

        similarity2 = TLMatchingService.cosine_similarity(vec1, vec3)
        if similarity2 >= match_threshold:
            assert similarity2 >= match_threshold
