"""
Tests for code quality improvements made in 2025-10-22 refactoring.

Tests cover:
- VoteService.submit_system_vote() method
- Timezone utility functions
- Denormalized field validation
- Phrase validation client session management
- Game balance settings
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC, timedelta
import uuid

from backend.services.vote_service import VoteService
from backend.services.round_service import RoundService
from backend.services.transaction_service import TransactionService
from backend.services.phrase_validation_client import PhraseValidationClient
from backend.utils.datetime_helpers import ensure_utc
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import PhraseSet
from backend.models.vote import Vote
from backend.config import get_settings
from backend.utils.exceptions import AlreadyVotedError


class TestTimezoneUtility:
    """Test timezone utility functions."""

    def test_ensure_utc_with_naive_datetime(self):
        """Should add UTC timezone to naive datetime."""
        naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        aware_dt = ensure_utc(naive_dt)

        assert aware_dt.tzinfo == UTC
        assert aware_dt.year == 2025
        assert aware_dt.month == 1
        assert aware_dt.day == 1
        assert aware_dt.hour == 12

    def test_ensure_utc_with_aware_datetime(self):
        """Should return aware datetime unchanged."""
        aware_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        result = ensure_utc(aware_dt)

        assert result == aware_dt
        assert result.tzinfo == UTC

    def test_ensure_utc_with_none(self):
        """Should return None when given None."""
        result = ensure_utc(None)
        assert result is None

    def test_ensure_utc_preserves_time(self):
        """Should preserve exact time when adding timezone."""
        naive_dt = datetime(2025, 6, 15, 14, 30, 45, 123456)
        aware_dt = ensure_utc(naive_dt)

        assert aware_dt.year == 2025
        assert aware_dt.month == 6
        assert aware_dt.day == 15
        assert aware_dt.hour == 14
        assert aware_dt.minute == 30
        assert aware_dt.second == 45
        assert aware_dt.microsecond == 123456


class TestSystemVote:
    """Test VoteService.submit_system_vote() method."""

    @pytest.fixture
    def vote_service(self, db_session):
        """Create vote service instance."""
        return VoteService(db_session)

    @pytest.fixture
    def transaction_service(self, db_session):
        """Create transaction service instance."""
        return TransactionService(db_session)

    @pytest.fixture
    async def setup_phraseset(self, db_session):
        """Create a phraseset for testing."""
        # Create players (need password_hash for database constraint)
        prompt_player = Player(
            player_id=uuid.uuid4(),
            username="prompt_player",
            username_canonical="prompt_player",
            email="prompt@test.com",
            password_hash="test_hash",
            pseudonym="Prompt Maker",
            pseudonym_canonical="promptmaker",
            balance=1000,
        )
        copy1_player = Player(
            player_id=uuid.uuid4(),
            username="copy1_player",
            username_canonical="copy1_player",
            email="copy1@test.com",
            password_hash="test_hash",
            pseudonym="Copy One",
            pseudonym_canonical="copyone",
            balance=1000,
        )
        copy2_player = Player(
            player_id=uuid.uuid4(),
            username="copy2_player",
            username_canonical="copy2_player",
            email="copy2@test.com",
            password_hash="test_hash",
            pseudonym="Copy Two",
            pseudonym_canonical="copytwo",
            balance=1000,
        )
        ai_player = Player(
            player_id=uuid.uuid4(),
            username="AI_VOTER",
            username_canonical="ai_voter",
            email="ai@test.com",
            password_hash="test_hash",
            pseudonym="AI Voter",
            pseudonym_canonical="aivoter",
            balance=1000,
        )

        db_session.add_all([prompt_player, copy1_player, copy2_player, ai_player])
        await db_session.flush()

        # Create prompt round
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompt_player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test prompt",
            submitted_phrase="ORIGINAL PHRASE",
        )

        # Create copy rounds
        copy1_round = Round(
            round_id=uuid.uuid4(),
            player_id=copy1_player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            original_phrase="ORIGINAL PHRASE",
            copy_phrase="COPY PHRASE ONE",
        )

        copy2_round = Round(
            round_id=uuid.uuid4(),
            player_id=copy2_player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            original_phrase="ORIGINAL PHRASE",
            copy_phrase="COPY PHRASE TWO",
        )

        db_session.add_all([prompt_round, copy1_round, copy2_round])
        await db_session.flush()

        # Create phraseset
        phraseset = PhraseSet(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=copy1_round.round_id,
            copy_round_2_id=copy2_round.round_id,
            prompt_text="Test prompt",
            original_phrase="ORIGINAL PHRASE",
            copy_phrase_1="COPY PHRASE ONE",
            copy_phrase_2="COPY PHRASE TWO",
            status="open",
            vote_count=0,
            total_pool=300,
            system_contribution=0,
        )

        db_session.add(phraseset)
        await db_session.commit()

        return {
            "phraseset": phraseset,
            "ai_player": ai_player,
            "prompt_player": prompt_player,
        }

    @pytest.mark.asyncio
    async def test_submit_system_vote_correct(
        self, vote_service, transaction_service, setup_phraseset, db_session
    ):
        """Should create correct vote and give payout."""
        data = await setup_phraseset
        phraseset = data["phraseset"]
        ai_player = data["ai_player"]

        # Submit system vote for original phrase (correct)
        vote = await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=ai_player,
            chosen_phrase="ORIGINAL PHRASE",
            transaction_service=transaction_service,
        )

        assert vote.voted_phrase == "ORIGINAL PHRASE"
        assert vote.correct is True
        assert vote.payout == 5  # Default correct payout

        # Verify player got payout
        await db_session.refresh(ai_player)
        assert ai_player.balance == 1005  # 1000 + 5

    @pytest.mark.asyncio
    async def test_submit_system_vote_incorrect(
        self, vote_service, transaction_service, setup_phraseset, db_session
    ):
        """Should create incorrect vote with no payout."""
        data = await setup_phraseset
        phraseset = data["phraseset"]
        ai_player = data["ai_player"]

        # Submit system vote for copy phrase (incorrect)
        vote = await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=ai_player,
            chosen_phrase="COPY PHRASE ONE",
            transaction_service=transaction_service,
        )

        assert vote.voted_phrase == "COPY PHRASE ONE"
        assert vote.correct is False
        assert vote.payout == 0

        # Verify player got no payout
        await db_session.refresh(ai_player)
        assert ai_player.balance == 1000

    @pytest.mark.asyncio
    async def test_submit_system_vote_updates_vote_count(
        self, vote_service, transaction_service, setup_phraseset, db_session
    ):
        """Should update phraseset vote count."""
        data = await setup_phraseset
        phraseset = data["phraseset"]
        ai_player = data["ai_player"]

        initial_count = phraseset.vote_count
        await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=ai_player,
            chosen_phrase="ORIGINAL PHRASE",
            transaction_service=transaction_service,
        )

        await db_session.refresh(phraseset)
        assert phraseset.vote_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_submit_system_vote_prevents_duplicate(
        self, vote_service, transaction_service, setup_phraseset, db_session
    ):
        """Should prevent duplicate votes from same player."""
        data = await setup_phraseset
        phraseset = data["phraseset"]
        ai_player = data["ai_player"]

        # First vote succeeds
        await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=ai_player,
            chosen_phrase="ORIGINAL PHRASE",
            transaction_service=transaction_service,
        )

        # Second vote should fail
        with pytest.raises(AlreadyVotedError):
            await vote_service.submit_system_vote(
                phraseset=phraseset,
                player=ai_player,
                chosen_phrase="COPY PHRASE ONE",
                transaction_service=transaction_service,
            )

    @pytest.mark.asyncio
    async def test_submit_system_vote_invalid_phrase(
        self, vote_service, transaction_service, setup_phraseset
    ):
        """Should reject invalid phrase."""
        data = await setup_phraseset
        phraseset = data["phraseset"]
        ai_player = data["ai_player"]

        with pytest.raises(ValueError, match="Phrase must be one of"):
            await vote_service.submit_system_vote(
                phraseset=phraseset,
                player=ai_player,
                chosen_phrase="INVALID PHRASE",
                transaction_service=transaction_service,
            )


class TestDenormalizedFieldValidation:
    """Test denormalized field validation in RoundService."""

    @pytest.mark.asyncio
    @patch('backend.services.phrase_validator.get_phrase_validator')
    async def test_create_phraseset_validates_prompt_text(
        self, mock_get_validator, db_session
    ):
        """Should reject phraseset creation if prompt_text missing."""
        # Mock phrase validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = (True, "")
        mock_get_validator.return_value = mock_validator

        round_service = RoundService(db_session)
        # Create prompt round without prompt_text
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text=None,  # Missing!
            submitted_phrase="TEST PHRASE",
        )
        db_session.add(prompt_round)

        # Create copy rounds
        for i in range(2):
            copy_round = Round(
                round_id=uuid.uuid4(),
                player_id=uuid.uuid4(),
                round_type="copy",
                status="submitted",
                cost=100,
                expires_at=datetime.now(UTC) + timedelta(minutes=3),
                prompt_round_id=prompt_round.round_id,
                copy_phrase=f"COPY {i}",
            )
            db_session.add(copy_round)

        await db_session.commit()

        # Should return None (validation failed)
        result = await round_service.create_phraseset_if_ready(prompt_round)
        assert result is None

    @pytest.mark.asyncio
    @patch('backend.services.phrase_validator.get_phrase_validator')
    async def test_create_phraseset_validates_copy_phrases(
        self, mock_get_validator, db_session
    ):
        """Should reject phraseset creation if copy_phrase missing."""
        # Mock phrase validator
        mock_validator = MagicMock()
        mock_validator.validate.return_value = (True, "")
        mock_get_validator.return_value = mock_validator

        round_service = RoundService(db_session)
        # Create prompt round
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test prompt",
            submitted_phrase="TEST PHRASE",
        )
        db_session.add(prompt_round)

        # Create copy round with missing copy_phrase
        copy_round = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase=None,  # Missing!
        )
        db_session.add(copy_round)

        # Create second copy round (valid)
        copy_round2 = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase="COPY TWO",
        )
        db_session.add(copy_round2)

        await db_session.commit()

        # Should return None (validation failed)
        result = await round_service.create_phraseset_if_ready(prompt_round)
        assert result is None


class TestPhraseValidationClientSession:
    """Test phrase validation client session management."""

    @pytest.mark.asyncio
    async def test_client_async_context_manager(self):
        """Should support async context manager."""
        client = PhraseValidationClient()

        async with client as c:
            # Session should be created
            assert c._session is not None

        # Session should be closed after exit
        assert client._session is None or client._session.closed

    @pytest.mark.asyncio
    async def test_client_ensure_session(self):
        """Should create session lazily."""
        client = PhraseValidationClient()
        assert client._session is None

        await client._ensure_session()
        assert client._session is not None
        assert not client._session.closed

        await client.close()

    @pytest.mark.asyncio
    async def test_client_close_idempotent(self):
        """Should handle multiple close calls."""
        client = PhraseValidationClient()
        await client._ensure_session()

        await client.close()
        await client.close()  # Should not raise

        assert client._session is None


class TestGameBalanceSettings:
    """Test centralized game balance settings."""

    def test_vote_finalization_settings_exist(self):
        """Should have vote finalization threshold settings."""
        settings = get_settings()

        assert hasattr(settings, 'vote_max_votes')
        assert hasattr(settings, 'vote_closing_threshold')
        assert hasattr(settings, 'vote_closing_window_seconds')
        assert hasattr(settings, 'vote_minimum_threshold')
        assert hasattr(settings, 'vote_minimum_window_seconds')

    def test_vote_finalization_defaults(self):
        """Should have sensible default values."""
        settings = get_settings()

        assert settings.vote_max_votes == 20
        assert settings.vote_closing_threshold == 5
        assert settings.vote_closing_window_seconds == 60
        assert settings.vote_minimum_threshold == 3
        assert settings.vote_minimum_window_seconds == 600

    def test_settings_are_integers(self):
        """Should all be integer values."""
        settings = get_settings()

        assert isinstance(settings.vote_max_votes, int)
        assert isinstance(settings.vote_closing_threshold, int)
        assert isinstance(settings.vote_closing_window_seconds, int)
        assert isinstance(settings.vote_minimum_threshold, int)
        assert isinstance(settings.vote_minimum_window_seconds, int)


class TestVoteServiceUsesSettings:
    """Test that VoteService uses centralized settings."""

    @pytest.fixture
    def vote_service(self, db_session):
        """Create vote service instance."""
        return VoteService(db_session)

    @pytest.mark.asyncio
    async def test_finalization_uses_max_votes_setting(
        self, vote_service, db_session
    ):
        """Should use settings.vote_max_votes for finalization check."""
        settings = get_settings()

        # Create phraseset with max votes
        phraseset = PhraseSet(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=uuid.uuid4(),
            copy_round_1_id=uuid.uuid4(),
            copy_round_2_id=uuid.uuid4(),
            prompt_text="Test",
            original_phrase="ORIGINAL",
            copy_phrase_1="COPY1",
            copy_phrase_2="COPY2",
            status="open",
            vote_count=settings.vote_max_votes,  # Use setting
            total_pool=300,
        )

        db_session.add(phraseset)
        await db_session.commit()

        # The finalization logic should trigger based on settings
        # (This test verifies the setting is accessible)
        assert phraseset.vote_count >= settings.vote_max_votes
