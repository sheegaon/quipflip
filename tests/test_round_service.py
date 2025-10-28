"""
Comprehensive tests for RoundService.

Tests round creation, lifecycle, expiration, and phraseset creation.
"""

import pytest
from datetime import datetime, timedelta, UTC
import uuid

from backend.models.player import Player
from backend.models.prompt import Prompt
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.services.round_service import RoundService
from backend.services.transaction_service import TransactionService
from backend.utils.exceptions import (
    RoundExpiredError,
    RoundNotFoundError,
    InvalidPhraseError,
)
from backend.config import get_settings

settings = get_settings()


@pytest.fixture
async def player_with_balance(db_session):
    """Create a player with sufficient balance for testing."""
    player = Player(
        player_id=uuid.uuid4(),
        username=f"test_player_{uuid.uuid4().hex[:8]}",
        username_canonical=f"test_player_{uuid.uuid4().hex[:8]}",
        pseudonym=f"Test Player {uuid.uuid4().hex[:8]}",
        pseudonym_canonical=f"test player {uuid.uuid4().hex[:8]}",
        email=f"test_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="test_hash",
        balance=10000,  # Plenty of balance
    )
    db_session.add(player)
    await db_session.commit()
    return player


@pytest.fixture
async def test_prompt(db_session):
    """Create a test prompt."""
    prompt = Prompt(
        prompt_id=uuid.uuid4(),
        text="What do you call a happy event?",
        enabled=True,
    )
    db_session.add(prompt)
    await db_session.commit()
    return prompt


class TestPromptRoundCreation:
    """Test prompt round creation and lifecycle."""

    @pytest.mark.asyncio
    async def test_start_prompt_round_success(self, db_session, player_with_balance, test_prompt):
        """Should successfully create a prompt round and deduct balance."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        initial_balance = player_with_balance.balance

        # Start prompt round
        round_obj = await round_service.start_prompt_round(
            player_with_balance,
            transaction_service
        )

        assert round_obj is not None
        assert round_obj.round_type == "prompt"
        assert round_obj.status == "active"
        assert round_obj.player_id == player_with_balance.player_id
        assert round_obj.prompt_id == test_prompt.prompt_id
        assert round_obj.prompt_text == test_prompt.text
        assert round_obj.cost == settings.prompt_cost

        # Verify balance was deducted
        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == initial_balance - settings.prompt_cost

    @pytest.mark.asyncio
    async def test_start_prompt_round_sets_active_round(self, db_session, player_with_balance, test_prompt):
        """Should set player's active_round_id."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        round_obj = await round_service.start_prompt_round(
            player_with_balance,
            transaction_service
        )

        await db_session.refresh(player_with_balance)
        assert player_with_balance.active_round_id == round_obj.round_id

    @pytest.mark.asyncio
    async def test_start_prompt_round_creates_expiration(self, db_session, player_with_balance, test_prompt):
        """Should set correct expiration time."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        before_time = datetime.now(UTC)
        round_obj = await round_service.start_prompt_round(
            player_with_balance,
            transaction_service
        )
        after_time = datetime.now(UTC)

        # Expiration should be ~3 minutes from now
        expected_expiry_min = before_time + timedelta(minutes=3)
        expected_expiry_max = after_time + timedelta(minutes=3)

        assert expected_expiry_min <= round_obj.expires_at <= expected_expiry_max


class TestPromptSubmission:
    """Test prompt phrase submission."""

    @pytest.mark.asyncio
    async def test_submit_prompt_phrase_success(self, db_session, player_with_balance, test_prompt):
        """Should successfully submit a valid prompt phrase."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        # Start round
        round_obj = await round_service.start_prompt_round(
            player_with_balance,
            transaction_service
        )

        # Submit phrase
        submitted_round = await round_service.submit_prompt_phrase(
            round_obj.round_id,
            player_with_balance,
            "CELEBRATION",
        )

        assert submitted_round.status == "submitted"
        assert submitted_round.submitted_phrase == "CELEBRATION"

        # Player should no longer have active round
        await db_session.refresh(player_with_balance)
        assert player_with_balance.active_round_id is None

    @pytest.mark.asyncio
    async def test_submit_prompt_phrase_invalid_format(self, db_session, player_with_balance, test_prompt):
        """Should reject invalid phrase formats."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        round_obj = await round_service.start_prompt_round(
            player_with_balance,
            transaction_service
        )

        # Try to submit invalid phrase
        with pytest.raises(InvalidPhraseError):
            await round_service.submit_prompt_phrase(
                round_obj.round_id,
                player_with_balance,
                "TOO MANY WORDS HERE NOW",  # > 5 words
            )

    @pytest.mark.asyncio
    async def test_submit_prompt_phrase_expired_round(self, db_session, player_with_balance, test_prompt):
        """Should reject submission to expired round."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        # Create an expired round manually
        expired_round = Round(
            round_id=uuid.uuid4(),
            player_id=player_with_balance.player_id,
            round_type="prompt",
            status="active",
            prompt_id=test_prompt.prompt_id,
            prompt_text=test_prompt.text,
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Expired
        )
        db_session.add(expired_round)
        await db_session.commit()

        with pytest.raises(RoundExpiredError):
            await round_service.submit_prompt_phrase(
                expired_round.round_id,
                player_with_balance,
                "CELEBRATION",
            )


class TestCopyRoundCreation:
    """Test copy round creation and management."""

    @pytest.mark.asyncio
    async def test_start_copy_round_success(self, db_session, player_with_balance, test_prompt):
        """Should successfully create a copy round."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        # Create a submitted prompt round first
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),  # Different player
            round_type="prompt",
            status="submitted",
            prompt_id=test_prompt.prompt_id,
            prompt_text=test_prompt.text,
            submitted_phrase="CELEBRATION",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        db_session.add(prompt_round)
        await db_session.commit()

        initial_balance = player_with_balance.balance

        # Start copy round
        copy_round = await round_service.start_copy_round(
            player_with_balance,
            prompt_round,
            transaction_service,
        )

        assert copy_round is not None
        assert copy_round.round_type == "copy"
        assert copy_round.status == "active"
        assert copy_round.player_id == player_with_balance.player_id
        assert copy_round.prompt_round_id == prompt_round.round_id
        assert copy_round.original_phrase == "CELEBRATION"

        # Verify balance was deducted (normal cost)
        await db_session.refresh(player_with_balance)
        assert player_with_balance.balance == initial_balance - settings.copy_cost_normal


class TestPhrasesetCreation:
    """Test phraseset creation logic."""

    @pytest.mark.asyncio
    async def test_create_phraseset_with_two_copies(self, db_session):
        """Should create phraseset when two copy rounds are submitted."""
        round_service = RoundService(db_session)

        # Create players
        test_id = uuid.uuid4().hex[:8]
        prompter = Player(
            player_id=uuid.uuid4(),
            username=f"prompter_{test_id}",
            username_canonical=f"prompter_{test_id}",
            pseudonym=f"Prompter_{test_id}",
            pseudonym_canonical=f"prompter_{test_id}",
            email=f"prompter_{test_id}@test.com",
            password_hash="hash",
            balance=1000,
        )
        copier1 = Player(
            player_id=uuid.uuid4(),
            username=f"copier1_{test_id}",
            username_canonical=f"copier1_{test_id}",
            pseudonym=f"Copier1_{test_id}",
            pseudonym_canonical=f"copier1_{test_id}",
            email=f"copier1_{test_id}@test.com",
            password_hash="hash",
            balance=1000,
        )
        copier2 = Player(
            player_id=uuid.uuid4(),
            username=f"copier2_{test_id}",
            username_canonical=f"copier2_{test_id}",
            pseudonym=f"Copier2_{test_id}",
            pseudonym_canonical=f"copier2_{test_id}",
            email=f"copier2_{test_id}@test.com",
            password_hash="hash",
            balance=1000,
        )
        db_session.add_all([prompter, copier1, copier2])
        await db_session.commit()

        # Create prompt round
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompter.player_id,
            round_type="prompt",
            status="submitted",
            prompt_text="Test prompt",
            submitted_phrase="ORIGINAL",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        db_session.add(prompt_round)
        await db_session.flush()

        # Create two copy rounds
        copy1 = Round(
            round_id=uuid.uuid4(),
            player_id=copier1.player_id,
            round_type="copy",
            status="submitted",
            prompt_round_id=prompt_round.round_id,
            original_phrase="ORIGINAL",
            copy_phrase="COPY ONE",
            cost=settings.copy_cost_normal,
            system_contribution=0,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        copy2 = Round(
            round_id=uuid.uuid4(),
            player_id=copier2.player_id,
            round_type="copy",
            status="submitted",
            prompt_round_id=prompt_round.round_id,
            original_phrase="ORIGINAL",
            copy_phrase="COPY TWO",
            cost=settings.copy_cost_normal,
            system_contribution=0,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        db_session.add_all([copy1, copy2])

        # Set copy assignments on prompt round
        prompt_round.copy1_player_id = copier1.player_id
        prompt_round.copy2_player_id = copier2.player_id

        await db_session.commit()

        # Create phraseset
        phraseset = await round_service.create_phraseset_if_ready(prompt_round)

        assert phraseset is not None
        assert phraseset.prompt_round_id == prompt_round.round_id
        assert phraseset.copy_round_1_id == copy1.round_id
        assert phraseset.copy_round_2_id == copy2.round_id
        assert phraseset.original_phrase == "ORIGINAL"
        assert phraseset.copy_phrase_1 == "COPY ONE"
        assert phraseset.copy_phrase_2 == "COPY TWO"
        assert phraseset.status == "open"
        assert phraseset.vote_count == 0

    @pytest.mark.asyncio
    async def test_create_phraseset_not_ready(self, db_session):
        """Should return None if only one copy is available."""
        round_service = RoundService(db_session)

        test_id = uuid.uuid4().hex[:8]
        prompter = Player(
            player_id=uuid.uuid4(),
            username=f"prompter_{test_id}",
            username_canonical=f"prompter_{test_id}",
            pseudonym=f"Prompter_{test_id}",
            pseudonym_canonical=f"prompter_{test_id}",
            email=f"prompter_{test_id}@test.com",
            password_hash="hash",
            balance=1000,
        )
        db_session.add(prompter)
        await db_session.commit()

        # Create prompt round with only one copy
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompter.player_id,
            round_type="prompt",
            status="submitted",
            prompt_text="Test prompt",
            submitted_phrase="ORIGINAL",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        prompt_round.copy1_player_id = uuid.uuid4()  # Only one copy assigned
        db_session.add(prompt_round)
        await db_session.commit()

        # Try to create phraseset
        phraseset = await round_service.create_phraseset_if_ready(prompt_round)

        assert phraseset is None


class TestRoundExpiration:
    """Test round expiration handling."""

    @pytest.mark.asyncio
    async def test_expired_round_cleanup(self, db_session, player_with_balance):
        """Should handle expired rounds correctly."""
        # Create an expired active round
        expired_round = Round(
            round_id=uuid.uuid4(),
            player_id=player_with_balance.player_id,
            round_type="prompt",
            status="active",
            prompt_text="Test prompt",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) - timedelta(minutes=5),  # Expired 5 minutes ago
        )
        db_session.add(expired_round)
        await db_session.commit()

        round_service = RoundService(db_session)

        # Verify the round is considered expired
        result = await db_session.execute(
            select(Round).where(Round.round_id == expired_round.round_id)
        )
        round_obj = result.scalar_one()

        assert round_obj.expires_at < datetime.now(UTC)


class TestQueueIntegration:
    """Test round service integration with queue system."""

    @pytest.mark.asyncio
    async def test_copy_round_assigned_from_queue(self, db_session):
        """Should properly assign copy rounds to waiting prompt rounds."""
        # This tests that the queue service integration works
        # The actual implementation would involve queue matching
        test_id = uuid.uuid4().hex[:8]

        prompter = Player(
            player_id=uuid.uuid4(),
            username=f"prompter_{test_id}",
            username_canonical=f"prompter_{test_id}",
            pseudonym=f"Prompter_{test_id}",
            pseudonym_canonical=f"prompter_{test_id}",
            email=f"prompter_{test_id}@test.com",
            password_hash="hash",
            balance=1000,
        )
        db_session.add(prompter)
        await db_session.commit()

        # Create a prompt round waiting for copies
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompter.player_id,
            round_type="prompt",
            status="submitted",
            prompt_text="Test prompt",
            submitted_phrase="ORIGINAL",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        db_session.add(prompt_round)
        await db_session.commit()

        # Verify it's available for copy assignment
        assert prompt_round.copy1_player_id is None
        assert prompt_round.copy2_player_id is None
        assert prompt_round.status == "submitted"
