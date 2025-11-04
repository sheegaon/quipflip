"""Comprehensive tests for stale AI service."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, UTC, timedelta
import uuid

from backend.services.ai.stale_ai_service import StaleAIService
from backend.services.ai.ai_service import AIService
from backend.services.phrase_validator import PhraseValidator
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.vote import Vote
from backend.config import get_settings


@pytest.fixture(autouse=True)
def mock_validator():
    """Mock phrase validator for all tests."""
    settings = get_settings()
    original_openai_api_key = settings.openai_api_key
    original_use_validator = settings.use_phrase_validator_api

    if not settings.openai_api_key:
        settings.openai_api_key = "sk-test"
    settings.use_phrase_validator_api = False

    with patch("backend.services.phrase_validator.get_phrase_validator") as mock_get_validator:
        validator = MagicMock(spec=PhraseValidator)
        validator.validate.return_value = (True, "")
        mock_get_validator.return_value = validator
        yield validator

    settings.openai_api_key = original_openai_api_key
    settings.use_phrase_validator_api = original_use_validator


@pytest.fixture
def stale_ai_service(db_session):
    """Create stale AI service instance."""
    return StaleAIService(db_session)


class TestStaleAIPlayerCreation:
    """Test stale AI player creation and management."""

    @pytest.mark.asyncio
    async def test_create_stale_handler_player(self, db_session, stale_ai_service):
        """Should create stale handler player if it doesn't exist."""
        player = await stale_ai_service._get_or_create_stale_player("ai_stale_handler_0@quipflip.internal")

        assert player is not None
        assert player.email == "ai_stale_handler_0@quipflip.internal"
        # Username is randomly generated, so we just check it exists
        assert player.username is not None
        assert player.pseudonym is not None

    @pytest.mark.asyncio
    async def test_reuse_existing_stale_handler_player(self, db_session, stale_ai_service):
        """Should reuse existing stale handler player if it exists."""
        # Create player first time
        player1 = await stale_ai_service._get_or_create_stale_player("ai_stale_handler_0@quipflip.internal")
        await db_session.commit()

        # Get player second time
        player2 = await stale_ai_service._get_or_create_stale_player("ai_stale_handler_0@quipflip.internal")

        assert player1.player_id == player2.player_id

    @pytest.mark.asyncio
    async def test_create_stale_voter_player(self, db_session, stale_ai_service):
        """Should create stale voter player if it doesn't exist."""
        player = await stale_ai_service._get_or_create_stale_player("ai_stale_voter_0@quipflip.internal")

        assert player is not None
        assert player.email == "ai_stale_voter_0@quipflip.internal"
        # Username is randomly generated, so we just check it exists
        assert player.username is not None
        assert player.pseudonym is not None

    @pytest.mark.asyncio
    async def test_separate_handler_and_voter_players(self, db_session, stale_ai_service):
        """Handler and voter should be separate players."""
        handler = await stale_ai_service._get_or_create_stale_player("ai_stale_handler_0@quipflip.internal")
        voter = await stale_ai_service._get_or_create_stale_player("ai_stale_voter_0@quipflip.internal")

        assert handler.player_id != voter.player_id
        assert handler.email != voter.email


class TestFindStalePrompts:
    """Test finding stale prompts logic."""

    @pytest.mark.asyncio
    async def test_find_prompts_older_than_threshold(self, db_session, stale_ai_service):
        """Should find prompts older than the stale threshold."""
        settings = get_settings()

        # Create a player for the prompt
        from backend.services.player_service import PlayerService
        player_service = PlayerService(db_session)
        player = await player_service.create_player(
            username="test_user",
            email="test@example.com",
            password_hash="dummy",
            pseudonym="TestUser",
            pseudonym_canonical="testuser",
        )

        # Create a stale prompt (4 days old)
        old_time = datetime.now(UTC) - timedelta(days=4)
        stale_prompt = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=old_time,
            expires_at=old_time + timedelta(minutes=3),
            cost=100,
            submitted_phrase="TEST PHRASE",
        )
        db_session.add(stale_prompt)
        await db_session.commit()

        # Find stale prompts
        stale_prompts = await stale_ai_service._find_stale_prompts()

        assert len(stale_prompts) >= 1
        assert any(p.round_id == stale_prompt.round_id for p in stale_prompts)

    @pytest.mark.asyncio
    async def test_exclude_recent_prompts(self, db_session, stale_ai_service):
        """Should exclude prompts newer than the stale threshold."""
        # Create a player
        from backend.services.player_service import PlayerService
        player_service = PlayerService(db_session)
        player = await player_service.create_player(
            username="test_user2",
            email="test2@example.com",
            password_hash="dummy",
            pseudonym="TestUser2",
            pseudonym_canonical="testuser2",
        )

        # Create a recent prompt (1 day old)
        recent_time = datetime.now(UTC) - timedelta(days=1)
        recent_prompt = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=recent_time,
            expires_at=recent_time + timedelta(minutes=3),
            cost=100,
            submitted_phrase="RECENT PHRASE",
        )
        db_session.add(recent_prompt)
        await db_session.commit()

        # Find stale prompts
        stale_prompts = await stale_ai_service._find_stale_prompts()

        # Recent prompt should not be in the list
        assert not any(p.round_id == recent_prompt.round_id for p in stale_prompts)

    @pytest.mark.asyncio
    async def test_exclude_prompts_with_phraseset(self, db_session, stale_ai_service):
        """Should exclude prompts that already have a phraseset."""
        from backend.services.player_service import PlayerService
        player_service = PlayerService(db_session)
        player = await player_service.create_player(
            username="test_user3",
            email="test3@example.com",
            password_hash="dummy",
            pseudonym="TestUser3",
            pseudonym_canonical="testuser3",
        )

        # Create stale prompt
        old_time = datetime.now(UTC) - timedelta(days=4)
        prompt_with_phraseset = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=old_time,
            expires_at=old_time + timedelta(minutes=3),
            cost=100,
            submitted_phrase="PROMPT WITH PHRASESET",
        )
        db_session.add(prompt_with_phraseset)
        await db_session.flush()

        # Create phraseset for this prompt
        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_with_phraseset.round_id,
            copy_round_1_id=uuid.uuid4(),
            copy_round_2_id=uuid.uuid4(),
            prompt_text="test prompt",
            original_phrase="PROMPT WITH PHRASESET",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            created_at=old_time,
        )
        db_session.add(phraseset)
        await db_session.commit()

        # Find stale prompts
        stale_prompts = await stale_ai_service._find_stale_prompts()

        # Prompt with phraseset should not be in the list
        assert not any(p.round_id == prompt_with_phraseset.round_id for p in stale_prompts)

    @pytest.mark.asyncio
    async def test_exclude_prompts_already_copied_by_stale_ai(self, db_session, stale_ai_service):
        """Should exclude prompts already copied by stale AI (no N+1 query)."""
        from backend.services.player_service import PlayerService
        player_service = PlayerService(db_session)
        player = await player_service.create_player(
            username="test_user4",
            email="test4@example.com",
            password_hash="dummy",
            pseudonym="TestUser4",
            pseudonym_canonical="testuser4",
        )

        # Get stale handler
        handler = await stale_ai_service._get_or_create_stale_player("ai_stale_handler_0@quipflip.internal")

        # Create stale prompt
        old_time = datetime.now(UTC) - timedelta(days=4)
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=old_time,
            expires_at=old_time + timedelta(minutes=3),
            cost=100,
            submitted_phrase="ALREADY COPIED",
        )
        db_session.add(prompt_round)
        await db_session.flush()

        # Assign copy1_player_id to mark it as having a copy
        prompt_round.copy1_player_id = handler.player_id

        # Create copy by stale AI
        copy_round = Round(
            round_id=uuid.uuid4(),
            player_id=handler.player_id,
            round_type="copy",
            status="submitted",
            created_at=old_time,
            expires_at=old_time + timedelta(minutes=3),
            cost=0,
            prompt_round_id=prompt_round.round_id,
            original_phrase="ALREADY COPIED",
            copy_phrase="AI COPY",
        )
        db_session.add(copy_round)
        await db_session.commit()

        # Find stale prompts
        stale_prompts = await stale_ai_service._find_stale_prompts()

        # Prompt that has copy slot filled should not be in the list (unless both slots are empty)
        # Since we only filled copy1, it could still show up if copy2 is empty
        # Let's also fill copy2 to ensure it's excluded
        prompt_round.copy2_player_id = handler.player_id
        await db_session.commit()

        stale_prompts = await stale_ai_service._find_stale_prompts()
        assert not any(p.round_id == prompt_round.round_id for p in stale_prompts)


class TestFindStalePhrasesets:
    """Test finding stale phrasesets logic."""

    @pytest.mark.asyncio
    async def test_find_phrasesets_older_than_threshold(self, db_session, stale_ai_service):
        """Should find phrasesets older than the stale threshold."""
        # Create stale phraseset (4 days old)
        old_time = datetime.now(UTC) - timedelta(days=4)
        stale_phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=uuid.uuid4(),
            copy_round_1_id=uuid.uuid4(),
            copy_round_2_id=uuid.uuid4(),
            prompt_text="test prompt",
            original_phrase="ORIGINAL",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="open",
            created_at=old_time,
        )
        db_session.add(stale_phraseset)
        await db_session.commit()

        # Find stale phrasesets
        stale_phrasesets = await stale_ai_service._find_stale_phrasesets()

        assert len(stale_phrasesets) >= 1
        assert any(p.phraseset_id == stale_phraseset.phraseset_id for p in stale_phrasesets)

    @pytest.mark.asyncio
    async def test_exclude_recent_phrasesets(self, db_session, stale_ai_service):
        """Should exclude phrasesets newer than the stale threshold."""
        # Create recent phraseset (1 day old)
        recent_time = datetime.now(UTC) - timedelta(days=1)
        recent_phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=uuid.uuid4(),
            copy_round_1_id=uuid.uuid4(),
            copy_round_2_id=uuid.uuid4(),
            prompt_text="test prompt",
            original_phrase="RECENT",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="open",
            created_at=recent_time,
        )
        db_session.add(recent_phraseset)
        await db_session.commit()

        # Find stale phrasesets
        stale_phrasesets = await stale_ai_service._find_stale_phrasesets()

        # Recent phraseset should not be in the list
        assert not any(p.phraseset_id == recent_phraseset.phraseset_id for p in stale_phrasesets)

    @pytest.mark.asyncio
    async def test_exclude_closed_phrasesets(self, db_session, stale_ai_service):
        """Should exclude phrasesets that are closed or finalized."""
        # Create closed phraseset
        old_time = datetime.now(UTC) - timedelta(days=4)
        closed_phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=uuid.uuid4(),
            copy_round_1_id=uuid.uuid4(),
            copy_round_2_id=uuid.uuid4(),
            prompt_text="test prompt",
            original_phrase="CLOSED",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="finalized",
            created_at=old_time,
        )
        db_session.add(closed_phraseset)
        await db_session.commit()

        # Find stale phrasesets
        stale_phrasesets = await stale_ai_service._find_stale_phrasesets()

        # Closed phraseset should not be in the list
        assert not any(p.phraseset_id == closed_phraseset.phraseset_id for p in stale_phrasesets)

    @pytest.mark.asyncio
    async def test_exclude_phrasesets_already_voted_by_stale_ai(self, db_session, stale_ai_service):
        """Should exclude phrasesets that have enough votes."""
        # Get stale voter
        voter = await stale_ai_service._get_or_create_stale_player("ai_stale_voter_0@quipflip.internal")

        # Create stale phraseset
        old_time = datetime.now(UTC) - timedelta(days=4)
        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=uuid.uuid4(),
            copy_round_1_id=uuid.uuid4(),
            copy_round_2_id=uuid.uuid4(),
            prompt_text="test prompt",
            original_phrase="ALREADY VOTED",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="open",
            created_at=old_time,
            vote_count=3,  # Set to threshold so it's excluded
        )
        db_session.add(phraseset)
        await db_session.flush()

        # Create vote by stale AI
        vote = Vote(
            vote_id=uuid.uuid4(),
            player_id=voter.player_id,
            phraseset_id=phraseset.phraseset_id,
            voted_phrase="ALREADY VOTED",
            correct=True,
            payout=20,
            created_at=old_time,
        )
        db_session.add(vote)
        await db_session.commit()

        # Find stale phrasesets
        stale_phrasesets = await stale_ai_service._find_stale_phrasesets()

        # Phraseset with enough votes should not be in the list
        assert not any(p.phraseset_id == phraseset.phraseset_id for p in stale_phrasesets)


class TestStaleAICycleIntegration:
    """Test full stale AI cycle execution."""

    @pytest.mark.asyncio
    async def test_cycle_processes_stale_prompts(self, db_session, stale_ai_service):
        """Should process stale prompts and generate copies."""
        from backend.services.player_service import PlayerService
        player_service = PlayerService(db_session)
        player = await player_service.create_player(
            username="cycle_test_user",
            email="cycle_test@example.com",
            password_hash="dummy",
            pseudonym="CycleTestUser",
            pseudonym_canonical="cycletestuser",
        )

        # Create stale prompt
        old_time = datetime.now(UTC) - timedelta(days=4)
        stale_prompt = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=old_time,
            expires_at=old_time + timedelta(minutes=3),
            cost=100,
            submitted_phrase="TEST PHRASE",
            prompt_text="Test prompt text",
        )
        db_session.add(stale_prompt)
        await db_session.commit()

        # Mock AI copy generation
        with patch.object(stale_ai_service.ai_service, 'generate_copy_phrase', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "generated copy"

            # Run stale cycle
            await stale_ai_service.run_stale_cycle()

        # Verify copy was generated
        assert mock_gen.called

    @pytest.mark.asyncio
    async def test_cycle_handles_errors_gracefully(self, db_session, stale_ai_service):
        """Should handle errors without crashing the cycle."""
        from backend.services.player_service import PlayerService
        player_service = PlayerService(db_session)
        player = await player_service.create_player(
            username="error_test_user",
            email="error_test@example.com",
            password_hash="dummy",
            pseudonym="ErrorTestUser",
            pseudonym_canonical="errortestuser",
        )

        # Create stale prompt
        old_time = datetime.now(UTC) - timedelta(days=4)
        stale_prompt = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=old_time,
            expires_at=old_time + timedelta(minutes=3),
            cost=100,
            submitted_phrase="ERROR PHRASE",
            prompt_text="Test prompt",
        )
        db_session.add(stale_prompt)
        await db_session.commit()

        # Mock AI copy generation to fail
        with patch.object(stale_ai_service.ai_service, 'generate_copy_phrase', new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = Exception("AI generation failed")

            # Run stale cycle - should not crash
            await stale_ai_service.run_stale_cycle()

        # Cycle should complete despite error
        assert mock_gen.called


class TestMetricsTracking:
    """Test metrics tracking for stale AI operations."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self, db_session, stale_ai_service):
        """Should record metrics when copy generation succeeds."""
        from backend.services.player_service import PlayerService
        player_service = PlayerService(db_session)
        player = await player_service.create_player(
            username="metrics_test_user",
            email="metrics_test@example.com",
            password_hash="dummy",
            pseudonym="MetricsTestUser",
            pseudonym_canonical="metricstestuser",
        )

        # Create stale prompt
        old_time = datetime.now(UTC) - timedelta(days=4)
        stale_prompt = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=old_time,
            expires_at=old_time + timedelta(minutes=3),
            cost=100,
            submitted_phrase="METRICS TEST",
            prompt_text="Test prompt",
        )
        db_session.add(stale_prompt)
        await db_session.commit()

        # Mock AI copy generation
        with patch.object(stale_ai_service.ai_service, 'generate_copy_phrase', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = "generated copy"

            # Mock metrics service
            with patch.object(stale_ai_service.ai_service.metrics_service, 'record_operation', new_callable=AsyncMock) as mock_metrics:
                # Run stale cycle
                await stale_ai_service.run_stale_cycle()

                # Verify metrics were recorded with stale_copy operation type
                assert mock_metrics.called
                # Check all calls to find the stale_copy one
                copy_calls = [call for call in mock_metrics.call_args_list if call.kwargs.get('operation_type') == "stale_copy"]
                assert len(copy_calls) > 0, "Expected at least one stale_copy metric call"
                # Check the first stale_copy call
                assert copy_calls[0].kwargs['success'] is True
                assert copy_calls[0].kwargs['operation_type'] == "stale_copy"

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_failure(self, db_session, stale_ai_service):
        """Should record metrics when copy generation fails."""
        from backend.services.player_service import PlayerService
        player_service = PlayerService(db_session)
        player = await player_service.create_player(
            username="fail_metrics_user",
            email="fail_metrics@example.com",
            password_hash="dummy",
            pseudonym="FailMetricsUser",
            pseudonym_canonical="failmetricsuser",
        )

        # Create stale prompt
        old_time = datetime.now(UTC) - timedelta(days=4)
        stale_prompt = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            created_at=old_time,
            expires_at=old_time + timedelta(minutes=3),
            cost=100,
            submitted_phrase="FAIL METRICS",
            prompt_text="Test prompt",
        )
        db_session.add(stale_prompt)
        await db_session.commit()

        # Mock AI copy generation to fail
        with patch.object(stale_ai_service.ai_service, 'generate_copy_phrase', new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = Exception("Generation failed")

            # Mock metrics service
            with patch.object(stale_ai_service.ai_service.metrics_service, 'record_operation', new_callable=AsyncMock) as mock_metrics:
                # Run stale cycle
                await stale_ai_service.run_stale_cycle()

                # Verify failure metrics were recorded
                assert mock_metrics.called
                # Check all calls to find the stale_copy failure
                copy_calls = [call for call in mock_metrics.call_args_list if call.kwargs.get('operation_type') == "stale_copy"]
                assert len(copy_calls) > 0, "Expected at least one stale_copy metric call"
                # Check the first stale_copy call
                assert copy_calls[0].kwargs['success'] is False
                assert copy_calls[0].kwargs['operation_type'] == "stale_copy"
                assert "Generation failed" in copy_calls[0].kwargs['error_message']
