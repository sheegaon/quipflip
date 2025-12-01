"""
Tests for code quality improvements made in 2025-10-22 refactoring.

Tests cover:
- VoteService.submit_system_vote() method
- Timezone utility functions
- Denormalized field validation
- Game balance settings
"""

import pytest
from datetime import datetime, UTC, timedelta
import uuid

from backend.services import QFVoteService
from backend.services import QFRoundService
from backend.services import TransactionService
from backend.utils.datetime_helpers import ensure_utc
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
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

    @pytest.mark.asyncio
    async def test_submit_system_vote_correct(self, db_session, player_factory):
        """Should create correct vote and give payout."""
        # Create players
        prompt_player = await player_factory()
        copy1_player = await player_factory()
        copy2_player = await player_factory()
        ai_player = await player_factory()

        # Create rounds
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompt_player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test prompt",
            submitted_phrase="ORIGINAL",
        )
        copy1_round = Round(
            round_id=uuid.uuid4(),
            player_id=copy1_player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase="COPY ONE",
        )
        copy2_round = Round(
            round_id=uuid.uuid4(),
            player_id=copy2_player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase="COPY TWO",
        )
        db_session.add_all([prompt_round, copy1_round, copy2_round])
        await db_session.flush()

        # Create phraseset
        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=copy1_round.round_id,
            copy_round_2_id=copy2_round.round_id,
            prompt_text="Test prompt",
            original_phrase="ORIGINAL",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="open",
            vote_count=0,
            total_pool=300,
            system_contribution=0,
        )
        db_session.add(phraseset)
        await db_session.commit()

        # Submit correct vote
        vote_service = QFVoteService(db_session)
        transaction_service = TransactionService(db_session)

        initial_balance = ai_player.balance
        vote = await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=ai_player,
            chosen_phrase="ORIGINAL",
            transaction_service=transaction_service,
        )

        assert vote.voted_phrase == "ORIGINAL"
        assert vote.correct is True
        assert vote.payout == 20

        # Verify balance change (net = payout - vote_cost = 20 - 10 = +10)
        await db_session.refresh(ai_player)
        assert ai_player.balance == initial_balance + 10

    @pytest.mark.asyncio
    async def test_submit_system_vote_incorrect(self, db_session, player_factory):
        """Should create incorrect vote with no payout."""
        # Create players
        prompt_player = await player_factory()
        copy1_player = await player_factory()
        copy2_player = await player_factory()
        ai_player = await player_factory()

        # Create rounds
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompt_player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test",
            submitted_phrase="ORIGINAL",
        )
        copy1_round = Round(
            round_id=uuid.uuid4(),
            player_id=copy1_player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase="COPY ONE",
        )
        copy2_round = Round(
            round_id=uuid.uuid4(),
            player_id=copy2_player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase="COPY TWO",
        )
        db_session.add_all([prompt_round, copy1_round, copy2_round])
        await db_session.flush()

        # Create phraseset
        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=copy1_round.round_id,
            copy_round_2_id=copy2_round.round_id,
            prompt_text="Test",
            original_phrase="ORIGINAL",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="open",
            vote_count=0,
            total_pool=300,
            system_contribution=0,
        )
        db_session.add(phraseset)
        await db_session.commit()

        # Submit incorrect vote
        vote_service = QFVoteService(db_session)
        transaction_service = TransactionService(db_session)

        initial_balance = ai_player.balance
        vote = await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=ai_player,
            chosen_phrase="COPY ONE",
            transaction_service=transaction_service,
        )

        assert vote.voted_phrase == "COPY ONE"
        assert vote.correct is False
        assert vote.payout == 0

        # Verify balance decreased by vote_cost (no payout for incorrect)
        await db_session.refresh(ai_player)
        assert ai_player.balance == initial_balance - 10

    @pytest.mark.asyncio
    async def test_submit_system_vote_prevents_duplicate(self, db_session, player_factory):
        """Should prevent duplicate votes from same player."""
        # Create players
        prompt_player = await player_factory()
        copy1_player = await player_factory()
        copy2_player = await player_factory()
        ai_player = await player_factory()

        # Create rounds
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompt_player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test",
            submitted_phrase="ORIGINAL",
        )
        copy1_round = Round(
            round_id=uuid.uuid4(),
            player_id=copy1_player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase="COPY ONE",
        )
        copy2_round = Round(
            round_id=uuid.uuid4(),
            player_id=copy2_player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase="COPY TWO",
        )
        db_session.add_all([prompt_round, copy1_round, copy2_round])
        await db_session.flush()

        # Create phraseset
        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=copy1_round.round_id,
            copy_round_2_id=copy2_round.round_id,
            prompt_text="Test",
            original_phrase="ORIGINAL",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="open",
            vote_count=0,
            total_pool=300,
            system_contribution=0,
        )
        db_session.add(phraseset)
        await db_session.commit()

        vote_service = QFVoteService(db_session)
        transaction_service = TransactionService(db_session)

        # First vote succeeds
        await vote_service.submit_system_vote(
            phraseset=phraseset,
            player=ai_player,
            chosen_phrase="ORIGINAL",
            transaction_service=transaction_service,
        )

        # Second vote should fail
        with pytest.raises(AlreadyVotedError):
            await vote_service.submit_system_vote(
                phraseset=phraseset,
                player=ai_player,
                chosen_phrase="COPY ONE",
                transaction_service=transaction_service,
            )


class TestDenormalizedFieldValidation:
    """Test denormalized field validation in RoundService."""

    @pytest.mark.asyncio
    async def test_create_phraseset_validates_prompt_text(self, db_session, player_factory):
        """Should reject phraseset creation if prompt_text missing."""
        round_service = QFRoundService(db_session)
        player = await player_factory()

        # Create prompt round without prompt_text
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text=None,  # Missing!
            submitted_phrase="TEST",
        )
        db_session.add(prompt_round)

        # Create copy rounds
        for i in range(2):
            copy_round = Round(
                round_id=uuid.uuid4(),
                player_id=player.player_id,
                round_type="copy",
                status="submitted",
                cost=100,
                expires_at=datetime.now(UTC) + timedelta(minutes=3),
                prompt_round_id=prompt_round.round_id,
                copy_phrase=f"COPY{i}",
            )
            db_session.add(copy_round)

        await db_session.commit()

        # Should return None (validation failed)
        result = await round_service.create_phraseset_if_ready(prompt_round)
        assert result is None

    @pytest.mark.asyncio
    async def test_create_phraseset_validates_copy_phrases(self, db_session, player_factory):
        """Should reject phraseset creation if copy_phrase missing."""
        round_service = QFRoundService(db_session)
        player = await player_factory()

        # Create prompt round
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_text="Test",
            submitted_phrase="TEST",
        )
        db_session.add(prompt_round)

        # Create copy round with missing copy_phrase
        copy_round1 = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase=None,  # Missing!
        )
        db_session.add(copy_round1)

        # Create second copy round (valid)
        copy_round2 = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="copy",
            status="submitted",
            cost=100,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
            prompt_round_id=prompt_round.round_id,
            copy_phrase="COPY",
        )
        db_session.add(copy_round2)

        await db_session.commit()

        # Should return None (validation failed)
        result = await round_service.create_phraseset_if_ready(prompt_round)
        assert result is None
class TestGameBalanceSettings:
    """Test centralized game balance settings."""

    def test_vote_finalization_settings_exist(self):
        """Should have vote finalization threshold settings."""
        settings = get_settings()

        assert hasattr(settings, 'vote_max_votes')
        assert hasattr(settings, 'vote_closing_threshold')
        assert hasattr(settings, 'vote_closing_window_minutes')
        assert hasattr(settings, 'vote_minimum_threshold')
        assert hasattr(settings, 'vote_minimum_window_minutes')

    def test_vote_finalization_defaults(self):
        """Should have sensible default values."""
        settings = get_settings()

        assert settings.vote_max_votes == 20
        assert settings.vote_closing_threshold == 5
        assert settings.vote_closing_window_minutes == 5
        assert settings.vote_minimum_threshold == 3
        assert settings.vote_minimum_window_minutes == 60

    def test_settings_are_integers(self):
        """Should all be integer values."""
        settings = get_settings()

        assert isinstance(settings.vote_max_votes, int)
        assert isinstance(settings.vote_closing_threshold, int)
        assert isinstance(settings.vote_closing_window_minutes, int)
        assert isinstance(settings.vote_minimum_threshold, int)
        assert isinstance(settings.vote_minimum_window_minutes, int)
