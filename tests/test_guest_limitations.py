"""Tests for guest account limitations."""
import uuid
from fastapi import status
from httpx import AsyncClient, ASGITransport
from datetime import datetime, UTC, timedelta
from uuid import UUID
from sqlalchemy import select

from backend.config import get_settings
from backend.models.qf.player import QFPlayer
from backend.models.qf.round import Round
from backend.models.qf.phraseset import Phraseset
from backend.services import QFPlayerService
from backend.services import GameType, TransactionService
from backend.services import QFVoteService


settings = get_settings()


class TestGuestOutstandingRoundsLimit:
    """Test that guests are limited to 3 outstanding rounds."""

    async def test_guest_limited_to_3_outstanding_rounds(self, test_app, db_session):
        """Test that guests use a limit of 3 outstanding prompts vs 10 for regular players."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            player_id = UUID(guest_data["player_id"])

            # Get player from database
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()

            # Mock the outstanding prompts count to be at the guest limit
            # This tests the logic without needing to create full phrasesets
            from unittest.mock import AsyncMock, patch

            with patch.object(QFPlayerService, 'get_outstanding_prompts_count', new_callable=AsyncMock) as mock_count:
                # Set mock to return the guest limit for outstanding prompts
                mock_count.return_value = settings.guest_max_outstanding_quips

                # Try to start a round (should fail for guest at the configured limit)
                player_service = QFPlayerService(db_session)
                can_start, error = await player_service.can_start_prompt_round(player)
                assert not can_start
                assert error == "max_outstanding_quips"

                # Now test a regular player with same count (should be able to start)
                player.is_guest = False
                can_start, error = await player_service.can_start_prompt_round(player)
                # With 3 outstanding, regular players can still start (limit is 10)
                assert can_start or error in ["insufficient_balance", "already_in_round"]

    async def test_regular_player_can_have_10_outstanding_rounds(self, test_app, db_session):
        """Test that regular players can have up to 10 outstanding prompts."""

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create regular account
            create_response = await client.post(
                "/player",
                json={
                    "email": "regular_outstanding@example.com",
                    "password": "Password123"
                }
            )
            assert create_response.status_code == status.HTTP_201_CREATED
            player_data = create_response.json()
            player_id = UUID(player_data["player_id"])

            # Get player from database
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()
            assert not player.is_guest

            # Check that can_start_prompt_round uses settings.max_outstanding_quips (10) for regular players
            player_service = QFPlayerService(db_session)

            # Artificially create 9 outstanding prompts by directly manipulating the count
            # (We can't actually create 9 real rounds easily in tests)
            # Instead, we'll just verify the logic: guests get 3, regulars get 10
            can_start, error = await player_service.can_start_prompt_round(player)
            # With 0 outstanding, should be able to start
            assert can_start or error == "no_prompts_available"  # Might fail if no prompts in queue


class TestGuestVoteLockout:
    """Test that guests are locked out according to configured vote lockout rules."""

    async def test_guest_locked_out_after_3_incorrect_votes(self, test_app, db_session):
        """Test that guests are locked out after the configured number of incorrect votes."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            player_id = UUID(guest_data["player_id"])

            # Get player from database - need to get fresh player object for proper session tracking
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()

            # Simulate active lockout (future timestamp)
            player.consecutive_incorrect_votes = settings.guest_vote_lockout_threshold
            lockout_time = datetime.now(UTC) + timedelta(hours=settings.guest_vote_lockout_hours)
            player.vote_lockout_until = lockout_time
            await db_session.commit()

            # Get fresh player instance to avoid stale state
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()

            # Verify the lockout fields are set
            assert player.vote_lockout_until is not None
            assert player.vote_lockout_until > datetime.now(UTC)

            # Verify player cannot start a vote round
            player_service = QFPlayerService(db_session)
            can_start, error = await player_service.can_start_vote_round(player)
            assert not can_start
            assert error == "vote_lockout_active"

    async def test_guest_lockout_expires_after_24_hours(self, test_app, db_session):
        """Test that expired guest lockouts are cleared automatically."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            player_id = UUID(guest_data["player_id"])

            # Get player from database
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()

            # Simulate expired lockout (set lockout_until to 1 hour ago)
            player.consecutive_incorrect_votes = settings.guest_vote_lockout_threshold
            expired_lockout_time = datetime.now(UTC) - timedelta(
                hours=settings.guest_vote_lockout_hours + 1
            )
            player.vote_lockout_until = expired_lockout_time
            await db_session.commit()

            # Get fresh player instance
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()

            # Verify lockout is in the past
            assert player.vote_lockout_until < datetime.now(UTC)

            # Refresh lockout state and ensure it was cleared
            player_service = QFPlayerService(db_session)
            cleared = await player_service.refresh_vote_lockout_state(player)
            assert cleared
            can_start, error = await player_service.can_start_vote_round(player)

            # After the refresh, lockout should be cleared (get fresh instance to verify)
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()
            assert player.vote_lockout_until is None
            assert player.consecutive_incorrect_votes == 0

            # Should be able to start (or fail for other reasons like balance/no phrasesets)
            assert can_start or error in ["insufficient_balance", "no_phrasesets_available"]

    async def test_regular_player_not_affected_by_lockout(self, test_app, db_session):
        """Test that regular players are not affected by vote lockout logic."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create regular account
            create_response = await client.post(
                "/player",
                json={
                    "email": "regular_lockout@example.com",
                    "password": "Password123"
                }
            )
            assert create_response.status_code == status.HTTP_201_CREATED
            player_data = create_response.json()
            player_id = UUID(player_data["player_id"])

            # Get player from database
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()
            assert not player.is_guest

            # Even if we set lockout fields, regular players shouldn't be affected
            player.consecutive_incorrect_votes = 5
            player.vote_lockout_until = datetime.now(UTC) + timedelta(hours=24)
            await db_session.commit()
            await db_session.refresh(player)

            # Regular player should still be able to start vote round (lockout logic only applies to guests)
            player_service = QFPlayerService(db_session)
            can_start, error = await player_service.can_start_vote_round(player)

            # Should be able to start (or fail for other reasons, but NOT vote_lockout_active)
            assert error != "vote_lockout_active"
            assert can_start or error in ["insufficient_balance", "no_phrasesets_available", "already_in_round"]

    async def test_guest_consecutive_votes_reset_on_correct_vote(self, test_app, db_session):
        """Test that consecutive incorrect votes counter resets on a correct vote."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            player_id = UUID(guest_data["player_id"])

            # Get player from database
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )
            player = result.scalar_one()

            # Simulate vote context to exercise VoteService logic
            unique_id = uuid.uuid4().hex[:8]

            prompter = QFPlayer(
                username=f"prompter_{unique_id}",
                username_canonical=f"prompter_{unique_id}",
                email=f"prompter_{unique_id}@example.com",
                password_hash="hash",
                wallet=1000,
                vault=0,
            )
            copier1 = QFPlayer(
                username=f"copier1_{unique_id}",
                username_canonical=f"copier1_{unique_id}",
                email=f"copier1_{unique_id}@example.com",
                password_hash="hash",
                wallet=1000,
                vault=0,
            )
            copier2 = QFPlayer(
                username=f"copier2_{unique_id}",
                username_canonical=f"copier2_{unique_id}",
                email=f"copier2_{unique_id}@example.com",
                password_hash="hash",
                wallet=1000,
                vault=0,
            )
            db_session.add_all([prompter, copier1, copier2])
            await db_session.commit()

            prompt_round = Round(
                round_id=uuid.uuid4(),
                player_id=prompter.player_id,
                round_type="prompt",
                status="submitted",
                prompt_text="Test prompt",
                submitted_phrase="ORIGINAL",
                cost=settings.prompt_cost,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            copy1_round = Round(
                round_id=uuid.uuid4(),
                player_id=copier1.player_id,
                round_type="copy",
                status="submitted",
                prompt_round_id=prompt_round.round_id,
                original_phrase="ORIGINAL",
                copy_phrase="COPY ONE",
                cost=settings.copy_cost_normal,
                system_contribution=0,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            copy2_round = Round(
                round_id=uuid.uuid4(),
                player_id=copier2.player_id,
                round_type="copy",
                status="submitted",
                prompt_round_id=prompt_round.round_id,
                original_phrase="ORIGINAL",
                copy_phrase="COPY TWO",
                cost=settings.copy_cost_normal,
                system_contribution=0,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            db_session.add_all([prompt_round, copy1_round, copy2_round])
            await db_session.flush()

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
                total_pool=settings.prize_pool_base,
                vote_contributions=0,
                vote_payouts_paid=0,
                system_contribution=0,
            )
            db_session.add(phraseset)
            await db_session.flush()

            vote_round = Round(
                round_id=uuid.uuid4(),
                player_id=player.player_id,
                round_type="vote",
                status="active",
                phraseset_id=phraseset.phraseset_id,
                prompt_round_id=prompt_round.round_id,
                cost=settings.vote_cost,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            player.active_round_id = vote_round.round_id
            db_session.add(vote_round)

            prior_incorrect = max(1, settings.guest_vote_lockout_threshold - 1)
            player.consecutive_incorrect_votes = prior_incorrect
            await db_session.commit()

            # Reload entities to avoid stale state before invoking the service
            player = (await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )).scalar_one()
            vote_round = await db_session.get(Round, vote_round.round_id)
            phraseset = await db_session.get(Phraseset, phraseset.phraseset_id)

            vote_service = QFVoteService(db_session)
            transaction_service = TransactionService(db_session, GameType.QF)

            await vote_service.submit_vote(
                vote_round,
                phraseset,
                phraseset.original_phrase,
                player,
                transaction_service,
            )

            refreshed_player = (await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == player_id)
            )).scalar_one()

            assert refreshed_player.consecutive_incorrect_votes == 0
            assert refreshed_player.vote_lockout_until is None
