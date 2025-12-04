"""Test script for ThinkLink similarity calculations.

Run with: python -m tests.test_tl_similarity_debug
Or: pytest tests/test_tl_similarity_debug.py -v -s
"""

import asyncio
import logging

try:
    import pytest
    PYTEST_AVAILABLE = True
except ImportError:
    PYTEST_AVAILABLE = False
    # Create a dummy decorator
    class pytest:
        @staticmethod
        def mark():
            pass
        class mark:
            @staticmethod
            def asyncio(func):
                return func

from backend.services.tl.matching_service import TLMatchingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test pairs: (text1, text2, should_match_at_055_threshold)
# NOTE: OpenAI embeddings measure LITERAL semantic similarity, not metaphorical relationships
# "watching paint dry" and "endless dental work" are thematically related (both boring)
# but semantically different words, so their similarity is low (~0.28)
#
# The 0.55 threshold works well for:
# - Near-synonyms ("endless cycle" vs "never ending")
# - Identical phrases
# - Same topic expressed similarly
#
# It does NOT work for:
# - Metaphorical relationships
# - Thematically related but semantically different phrases
TEST_PAIRS = [
    # These WILL match at 0.55 threshold (semantically similar)
    ("endless cycle", "never ending", True),  # Near-synonyms: ~0.66
    ("watching paint dry", "watching paint dry", True),  # Identical: 1.0
    ("morning coffee", "coffee in the morning", True),  # Same meaning
    ("very boring", "extremely dull", True),  # Synonymous

    # These will NOT match at 0.55 threshold (thematically related but different words)
    ("watching paint dry", "endless dental work", False),  # Both boring but different: ~0.28
    ("death by powerpoint", "purgatory with slides", False),  # Related metaphors: ~0.42
    ("liquid motivation", "morning necessity", False),  # Both about coffee need: ~0.33

    # These will NOT match (unrelated)
    ("watching paint dry", "tropical vacation", False),
    ("watching paint dry", "delicious pizza", False),
    ("liquid motivation", "swimming pool", False),
    ("endless cycle", "tropical beach", False),
]


@pytest.mark.asyncio
async def test_similarity_calculations():
    """Test similarity calculation between phrases."""
    logger.info("=" * 60)
    logger.info("ThinkLink Similarity Test")
    logger.info("=" * 60)

    matching = TLMatchingService()

    results = []

    for text1, text2, expected_match in TEST_PAIRS:
        print(f"\nTesting: '{text1}' vs '{text2}'")

        # Generate embeddings
        emb1 = await matching.generate_embedding(text1)
        emb2 = await matching.generate_embedding(text2)

        # Calculate similarity
        similarity = matching.cosine_similarity(emb1, emb2)

        # Determine if it would match
        threshold = 0.55  # Default match threshold
        would_match = similarity >= threshold

        status = "PASS" if would_match == expected_match else "FAIL"
        results.append((text1, text2, similarity, would_match, expected_match, status))

        print(f"  Similarity: {similarity:.4f}")
        print(f"  Would match (>={threshold}): {would_match}")
        print(f"  Expected match: {expected_match}")
        print(f"  Status: {status}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passes = sum(1 for r in results if r[5] == "PASS")
    fails = sum(1 for r in results if r[5] == "FAIL")

    print(f"Passed: {passes}/{len(results)}")
    print(f"Failed: {fails}/{len(results)}")

    if fails > 0:
        print("\nFailed tests:")
        for t1, t2, sim, matched, expected, status in results:
            if status == "FAIL":
                print(f"  '{t1}' vs '{t2}': sim={sim:.4f}, matched={matched}, expected={expected}")

    # Assert all tests passed
    assert fails == 0, f"{fails} similarity tests failed"


@pytest.mark.asyncio
async def test_embedding_types():
    """Test that embeddings have correct types and dimensions."""
    logger.info("\n" + "=" * 60)
    logger.info("VECTOR TYPE TEST")
    logger.info("=" * 60)

    matching = TLMatchingService()
    test_phrase = "watching paint dry"
    embedding = await matching.generate_embedding(test_phrase)

    logger.info(f"Embedding type: {type(embedding).__name__}")
    logger.info(f"Embedding length: {len(embedding)}")
    logger.info(f"First 5 values: {embedding[:5]}")
    logger.info(f"Value types: {type(embedding[0]).__name__}")

    assert len(embedding) == 1536, f"Expected 1536 dimensions, got {len(embedding)}"
    assert isinstance(embedding[0], float), f"Expected float values, got {type(embedding[0])}"


@pytest.mark.asyncio
async def test_batch_similarity():
    """Test batch similarity calculation."""
    logger.info("\n" + "=" * 60)
    logger.info("BATCH SIMILARITY TEST")
    logger.info("=" * 60)

    matching = TLMatchingService()

    candidates = [
        "watching paint dry",  # Identical theme
        "endless dental work",  # Similar theme
        "tropical vacation",  # Unrelated
    ]

    query_emb = await matching.generate_embedding("a long meeting feels like")
    candidate_embs = [await matching.generate_embedding(c) for c in candidates]

    similarities = matching.batch_cosine_similarity(query_emb, candidate_embs)

    for candidate, sim in zip(candidates, similarities):
        logger.info(f"  '{candidate}': {sim:.4f}")

    # The first two should be more similar than the third
    assert similarities[0] > similarities[2], "Related phrases should have higher similarity"
    assert similarities[1] > similarities[2], "Related phrases should have higher similarity"


async def run_manual_test():
    """Run tests manually without pytest."""
    await test_similarity_calculations()
    await test_embedding_types()
    await test_batch_similarity()


if __name__ == "__main__":
    asyncio.run(run_manual_test())
