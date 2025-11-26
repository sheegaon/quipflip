"""Test riff caption similarity validation."""
import pytest
from uuid import uuid4
from datetime import datetime, UTC

from backend.services.mm.caption_service import MMCaptionService
from backend.models.mm.caption import MMCaption


@pytest.fixture
def parent_caption():
    """Create a mock parent caption for testing."""
    return MMCaption(
        caption_id=uuid4(),
        image_id=uuid4(),
        author_player_id=uuid4(),
        kind='original',
        parent_caption_id=None,
        text="When you finally understand the assignment",
        status='active',
        created_at=datetime.now(UTC),
        shows=5,
        picks=2,
        first_vote_awarded=False,
        quality_score=0.4,
        lifetime_earnings_gross=0,
        lifetime_to_wallet=0,
        lifetime_to_vault=0,
    )


@pytest.mark.asyncio
async def test_riff_exact_duplicate_rejected(parent_caption):
    """Test that exact duplicate riffs are rejected."""
    # Mock database session
    class MockDB:
        pass

    service = MMCaptionService(MockDB())

    # Test exact duplicate
    is_valid, error = await service._validate_riff_caption(
        "When you finally understand the assignment",
        parent_caption
    )

    assert not is_valid
    assert "identical" in error.lower()


@pytest.mark.asyncio
async def test_riff_too_similar_rejected(parent_caption):
    """Test that very similar riffs are rejected."""
    class MockDB:
        pass

    class MockConfigService:
        async def get_config_value(self, key, default):
            return default  # Return 0.7 threshold

    service = MMCaptionService(MockDB())
    service.config_service = MockConfigService()

    # Test very similar text (just changing one word)
    is_valid, error = await service._validate_riff_caption(
        "When you finally understand the homework",
        parent_caption
    )

    # This should be rejected as too similar
    assert not is_valid
    assert "too similar" in error.lower()


@pytest.mark.asyncio
async def test_riff_different_enough_accepted(parent_caption):
    """Test that sufficiently different riffs are accepted."""
    class MockDB:
        pass

    class MockConfigService:
        async def get_config_value(self, key, default):
            return default  # Return 0.7 threshold

    service = MMCaptionService(MockDB())
    service.config_service = MockConfigService()

    # Test different text
    is_valid, error = await service._validate_riff_caption(
        "This is actually me in meetings",
        parent_caption
    )

    # This should be accepted
    assert is_valid
    assert error == ""


@pytest.mark.asyncio
async def test_riff_empty_text_rejected(parent_caption):
    """Test that empty riff text is rejected."""
    class MockDB:
        pass

    service = MMCaptionService(MockDB())

    # Test empty text
    is_valid, error = await service._validate_riff_caption(
        "",
        parent_caption
    )

    assert not is_valid
    assert "empty" in error.lower()


@pytest.mark.asyncio
async def test_riff_too_long_rejected(parent_caption):
    """Test that overly long riff text is rejected."""
    class MockDB:
        pass

    service = MMCaptionService(MockDB())

    # Test text over 240 characters
    long_text = "a" * 241
    is_valid, error = await service._validate_riff_caption(
        long_text,
        parent_caption
    )

    assert not is_valid
    assert "240 characters" in error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
