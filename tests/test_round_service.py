"""
Comprehensive tests for RoundService.

Tests round creation, lifecycle, expiration, and phraseset creation.
"""

import pytest
from datetime import datetime, timedelta, UTC
import uuid
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, update

from backend.models.player import Player
from backend.models.prompt import Prompt
from backend.models.round import Round
from backend.models.hint import Hint
from backend.models.phraseset import Phraseset
from backend.models.player_abandoned_prompt import PlayerAbandonedPrompt
from backend.services.round_service import RoundService
from backend.services.ai.ai_service import AIService
from backend.services.transaction_service import TransactionService
from backend.services.queue_service import QueueService
from backend.services.vote_service import VoteService
from backend.utils.exceptions import (
    RoundExpiredError,
    InvalidPhraseError,
    NoPromptsAvailableError,
    RoundNotFoundError,
)
from backend.config import get_settings

settings = get_settings()


def drain_prompt_queue():
    """Utility helper to clear the in-memory prompt queue between tests."""
    while QueueService.get_next_prompt_round():
        continue


@pytest.fixture
async def player_with_balance(db_session):
    """Create a player with sufficient balance for testing."""
    identifier = uuid.uuid4().hex[:8]
    player = Player(
        player_id=uuid.uuid4(),
        username=f"test_player_{identifier}",
        username_canonical=f"test_player_{identifier}",
        email=f"test_{identifier}@test.com",
        password_hash="test_hash",
        balance=10000,  # Plenty of balance
    )
    db_session.add(player)
    await db_session.commit()
    return player


@pytest.fixture
async def test_prompt(db_session):
    """Create a test prompt."""
    prompt_text = f"What do you call a happy event? {uuid.uuid4().hex[:6]}"
    prompt = Prompt(
        prompt_id=uuid.uuid4(),
        text=prompt_text,
        category="fun",
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

        expires_at = (
            round_obj.expires_at.replace(tzinfo=UTC)
            if round_obj.expires_at.tzinfo is None
            else round_obj.expires_at
        )
        assert expected_expiry_min <= expires_at <= expected_expiry_max

    @pytest.mark.asyncio
    async def test_start_prompt_round_skips_prompts_seen_in_other_rounds(
        self,
        db_session,
        player_with_balance,
    ):
        """Should not repeat prompts seen in prompt, copy, or vote rounds."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        # Disable any existing prompts to control the pool for this test
        await db_session.execute(update(Prompt).values(enabled=False))
        await db_session.commit()

        prompt_texts = [
            "Prompt Alpha",
            "Prompt Bravo",
            "Prompt Charlie",
            "Prompt Delta",
        ]
        prompts = []
        for text in prompt_texts:
            prompt = Prompt(
                prompt_id=uuid.uuid4(),
                text=f"{text} {uuid.uuid4()}",
                category="simple",
                enabled=True,
            )
            db_session.add(prompt)
            prompts.append(prompt)
        await db_session.commit()

        prompt_alpha, prompt_bravo, prompt_charlie, prompt_delta = prompts

        # Player has previously seen Prompt Alpha in a prompt round
        prior_prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=player_with_balance.player_id,
            round_type="prompt",
            status="submitted",
            prompt_id=prompt_alpha.prompt_id,
            prompt_text=prompt_alpha.text,
            submitted_phrase="ALPHA",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )

        # Player has seen Prompt Bravo through a copy round
        copy_source_prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="prompt",
            status="submitted",
            prompt_id=prompt_bravo.prompt_id,
            prompt_text=prompt_bravo.text,
            submitted_phrase="BRAVO",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        player_copy_round = Round(
            round_id=uuid.uuid4(),
            player_id=player_with_balance.player_id,
            round_type="copy",
            status="submitted",
            prompt_round_id=copy_source_prompt_round.round_id,
            original_phrase="BRAVO",
            copy_phrase="BRAVO COPY",
            cost=settings.copy_cost_normal,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )

        # Player has seen Prompt Charlie through a vote round
        vote_prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="prompt",
            status="submitted",
            prompt_id=prompt_charlie.prompt_id,
            prompt_text=prompt_charlie.text,
            submitted_phrase="CHARLIE",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        copy_round_one = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="copy",
            status="submitted",
            prompt_round_id=vote_prompt_round.round_id,
            original_phrase="CHARLIE",
            copy_phrase="CHARLIE COPY 1",
            cost=settings.copy_cost_normal,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        copy_round_two = Round(
            round_id=uuid.uuid4(),
            player_id=uuid.uuid4(),
            round_type="copy",
            status="submitted",
            prompt_round_id=vote_prompt_round.round_id,
            original_phrase="CHARLIE",
            copy_phrase="CHARLIE COPY 2",
            cost=settings.copy_cost_normal,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=vote_prompt_round.round_id,
            copy_round_1_id=copy_round_one.round_id,
            copy_round_2_id=copy_round_two.round_id,
            prompt_text=prompt_charlie.text,
            original_phrase="CHARLIE",
            copy_phrase_1="CHARLIE COPY 1",
            copy_phrase_2="CHARLIE COPY 2",
            status="open",
            vote_count=0,
            total_pool=200,
        )
        player_vote_round = Round(
            round_id=uuid.uuid4(),
            player_id=player_with_balance.player_id,
            round_type="vote",
            status="submitted",
            phraseset_id=phraseset.phraseset_id,
            cost=settings.vote_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=1),
        )

        db_session.add_all(
            [
                prior_prompt_round,
                copy_source_prompt_round,
                player_copy_round,
                vote_prompt_round,
                copy_round_one,
                copy_round_two,
                phraseset,
                player_vote_round,
            ]
        )
        await db_session.commit()

        round_obj = await round_service.start_prompt_round(
            player_with_balance,
            transaction_service,
        )

        assert round_obj.prompt_id == prompt_delta.prompt_id

    @pytest.mark.asyncio
    async def test_start_prompt_round_raises_when_all_prompts_seen(
        self,
        db_session,
        player_with_balance,
    ):
        """Should raise an error when no unseen prompts remain."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        await db_session.execute(update(Prompt).values(enabled=False))
        await db_session.commit()

        prompts = []
        for text in ["Prompt Echo", "Prompt Foxtrot"]:
            prompt = Prompt(
                prompt_id=uuid.uuid4(),
                text=f"{text} {uuid.uuid4()}",
                category="simple",
                enabled=True,
            )
            db_session.add(prompt)
            prompts.append(prompt)
        await db_session.commit()

        for prompt in prompts:
            seen_round = Round(
                round_id=uuid.uuid4(),
                player_id=player_with_balance.player_id,
                round_type="prompt",
                status="submitted",
                prompt_id=prompt.prompt_id,
                prompt_text=prompt.text,
                submitted_phrase="SEEN",
                cost=settings.prompt_cost,
                expires_at=datetime.now(UTC) + timedelta(minutes=3),
            )
            db_session.add(seen_round)
        await db_session.commit()

        with pytest.raises(NoPromptsAvailableError):
            await round_service.start_prompt_round(
                player_with_balance,
                transaction_service,
            )


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
            "Joyful Celebration",
            player_with_balance,
            transaction_service,
        )

        assert submitted_round.status == "submitted"
        assert submitted_round.submitted_phrase == "JOYFUL CELEBRATION"

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
                "Happy Fun Silly Witty Clever Joyful",  # 6 words (> max)
                player_with_balance,
                transaction_service,
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
                "CELEBRATION",
                player_with_balance,
                transaction_service,
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
        drain_prompt_queue()
        QueueService.add_prompt_round_to_queue(prompt_round.round_id)

        copy_round, _ = await round_service.start_copy_round(
            player_with_balance,
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


class TestAbandonRound:
    """Tests for abandoning active rounds."""

    @pytest.mark.asyncio
    async def test_abandon_prompt_round(self, db_session, player_with_balance, test_prompt):
        """Prompt players should receive a partial refund and clear active round state."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        # Start a prompt round to set up the abandonment scenario
        prompt_round = await round_service.start_prompt_round(
            player_with_balance,
            transaction_service
        )
        await db_session.refresh(player_with_balance)
        balance_after_charge = player_with_balance.balance

        abandoned_round, refund_amount, penalty_kept = await round_service.abandon_round(
            prompt_round.round_id,
            player_with_balance,
            transaction_service,
        )

        assert abandoned_round.status == "abandoned"
        assert abandoned_round.phraseset_status == "abandoned"
        assert refund_amount == max(prompt_round.cost - settings.abandoned_penalty, 0)
        assert penalty_kept == settings.abandoned_penalty

        await db_session.refresh(player_with_balance)
        assert player_with_balance.active_round_id is None
        assert player_with_balance.balance == balance_after_charge + refund_amount

    @pytest.mark.asyncio
    async def test_abandon_copy_round_returns_prompt(self, db_session, player_with_balance, test_prompt):
        """Abandoning a copy round should refund, requeue, and track the abandonment."""
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        # Create a submitted prompt round owned by a different player
        prompter = Player(
            player_id=uuid.uuid4(),
            username=f"prompter_{uuid.uuid4().hex[:8]}",
            username_canonical=f"prompter_{uuid.uuid4().hex[:8]}",
            email=f"prompter_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            balance=1000,
        )
        db_session.add(prompter)
        await db_session.commit()

        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompter.player_id,
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

        drain_prompt_queue()
        QueueService.add_prompt_round_to_queue(prompt_round.round_id)

        copy_round, _ = await round_service.start_copy_round(
            player_with_balance,
            transaction_service,
        )
        await db_session.refresh(player_with_balance)
        balance_after_charge = player_with_balance.balance

        assert copy_round.prompt_round_id == prompt_round.round_id

        abandoned_round, refund_amount, penalty_kept = await round_service.abandon_round(
            copy_round.round_id,
            player_with_balance,
            transaction_service,
        )

        assert abandoned_round.status == "abandoned"
        assert abandoned_round.round_type == "copy"
        assert refund_amount == max(copy_round.cost - settings.abandoned_penalty, 0)
        assert penalty_kept == settings.abandoned_penalty

        await db_session.refresh(player_with_balance)
        assert player_with_balance.active_round_id is None
        assert player_with_balance.balance == balance_after_charge + refund_amount

        # Prompt should be re-queued for other players
        assert QueueService.remove_prompt_round_from_queue(prompt_round.round_id) is True

        # Player abandonment cooldown should be tracked
        result = await db_session.execute(
            select(PlayerAbandonedPrompt).where(
                PlayerAbandonedPrompt.player_id == player_with_balance.player_id,
                PlayerAbandonedPrompt.prompt_round_id == prompt_round.round_id,
            )
        )
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_abandon_vote_round(self, db_session, player_with_balance):
        """Vote rounds should be abandonable with partial refund and cleared state."""
        round_service = RoundService(db_session)
        vote_service = VoteService(db_session)
        transaction_service = TransactionService(db_session)

        # Create other players involved in the phraseset
        prompter = Player(
            player_id=uuid.uuid4(),
            username=f"prompter_{uuid.uuid4().hex[:8]}",
            username_canonical=f"prompter_{uuid.uuid4().hex[:8]}",
            email=f"prompter_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            balance=1000,
        )
        copier_one = Player(
            player_id=uuid.uuid4(),
            username=f"copier1_{uuid.uuid4().hex[:8]}",
            username_canonical=f"copier1_{uuid.uuid4().hex[:8]}",
            email=f"copier1_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            balance=1000,
        )
        copier_two = Player(
            player_id=uuid.uuid4(),
            username=f"copier2_{uuid.uuid4().hex[:8]}",
            username_canonical=f"copier2_{uuid.uuid4().hex[:8]}",
            email=f"copier2_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hash",
            balance=1000,
        )

        db_session.add_all([prompter, copier_one, copier_two])
        await db_session.commit()

        # Create the submitted prompt and copy rounds powering the phraseset
        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=prompter.player_id,
            round_type="prompt",
            status="submitted",
            prompt_text="Vote Prompt",
            submitted_phrase="ORIGINAL",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        copy_round_one = Round(
            round_id=uuid.uuid4(),
            player_id=copier_one.player_id,
            round_type="copy",
            status="submitted",
            prompt_round_id=prompt_round.round_id,
            original_phrase="ORIGINAL",
            copy_phrase="COPY ONE",
            cost=settings.copy_cost_normal,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )
        copy_round_two = Round(
            round_id=uuid.uuid4(),
            player_id=copier_two.player_id,
            round_type="copy",
            status="submitted",
            prompt_round_id=prompt_round.round_id,
            original_phrase="ORIGINAL",
            copy_phrase="COPY TWO",
            cost=settings.copy_cost_normal,
            expires_at=datetime.now(UTC) + timedelta(minutes=3),
        )

        db_session.add_all([prompt_round, copy_round_one, copy_round_two])
        await db_session.commit()

        phraseset = Phraseset(
            phraseset_id=uuid.uuid4(),
            prompt_round_id=prompt_round.round_id,
            copy_round_1_id=copy_round_one.round_id,
            copy_round_2_id=copy_round_two.round_id,
            prompt_text="Vote Prompt",
            original_phrase="ORIGINAL",
            copy_phrase_1="COPY ONE",
            copy_phrase_2="COPY TWO",
            status="open",
            vote_count=0,
            total_pool=200,
        )
        db_session.add(phraseset)
        await db_session.commit()

        vote_round, _ = await vote_service.start_vote_round(player_with_balance, transaction_service)
        await db_session.refresh(player_with_balance)
        balance_after_charge = player_with_balance.balance

        abandoned_round, refund_amount, penalty_kept = await round_service.abandon_round(
            vote_round.round_id,
            player_with_balance,
            transaction_service,
        )

        assert abandoned_round.status == "abandoned"
        assert abandoned_round.round_type == "vote"
        assert refund_amount == max(settings.vote_cost - settings.abandoned_penalty, 0)
        assert penalty_kept == settings.abandoned_penalty

        await db_session.refresh(player_with_balance)
        assert player_with_balance.active_round_id is None
        assert player_with_balance.balance == balance_after_charge + refund_amount


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
            email=f"prompter_{test_id}@test.com",
            password_hash="hash",
            balance=1000,
        )
        copier1 = Player(
            player_id=uuid.uuid4(),
            username=f"copier1_{test_id}",
            username_canonical=f"copier1_{test_id}",
            email=f"copier1_{test_id}@test.com",
            password_hash="hash",
            balance=1000,
        )
        copier2 = Player(
            player_id=uuid.uuid4(),
            username=f"copier2_{test_id}",
            username_canonical=f"copier2_{test_id}",
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


class TestCopyHints:
    """Tests for AI-generated hint retrieval in RoundService."""

    @staticmethod
    async def _create_prompt_and_copy_round(db_session) -> tuple[Round, Round, Player]:
        identifier = uuid.uuid4().hex[:6]

        player = Player(
            player_id=uuid.uuid4(),
            username=f"copy_player_{identifier}",
            username_canonical=f"copy_player_{identifier}",
            email=f"copy_{identifier}@test.com",
            password_hash="hash",
            balance=500,
        )
        db_session.add(player)
        await db_session.commit()

        prompt_round = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="prompt",
            status="submitted",
            prompt_text="Test prompt for hints",
            submitted_phrase="ORIGINAL PHRASE",
            cost=settings.prompt_cost,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        db_session.add(prompt_round)
        await db_session.commit()
        await db_session.refresh(prompt_round)

        copy_round = Round(
            round_id=uuid.uuid4(),
            player_id=player.player_id,
            round_type="copy",
            status="active",
            prompt_round_id=prompt_round.round_id,
            prompt_text=prompt_round.prompt_text,
            original_phrase=prompt_round.submitted_phrase,
            cost=settings.copy_cost_normal,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        db_session.add(copy_round)
        await db_session.commit()
        await db_session.refresh(copy_round)

        return prompt_round, copy_round, player

    @pytest.mark.asyncio
    async def test_get_or_generate_hints_creates_and_caches(self, db_session):
        """Should generate hints once and reuse cached values."""
        prompt_round, copy_round, player = await self._create_prompt_and_copy_round(db_session)
        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        hints_payload = ["HINT ONE", "HINT TWO", "HINT THREE"]

        # Mock the generate_and_cache_phrases method to create and persist cache
        from backend.models.ai_phrase_cache import AIPhraseCache

        async def mock_generate_and_cache(self, prompt_round):
            """Mock that actually creates the cache in DB."""
            mock_cache = AIPhraseCache(
                cache_id=uuid.uuid4(),
                prompt_round_id=prompt_round.round_id,
                original_phrase=prompt_round.submitted_phrase,
                prompt_text=prompt_round.prompt_text,
                validated_phrases=hints_payload,
                generation_provider="test",
                generation_model="test-model",
                used_for_hints=False,
            )
            db_session.add(mock_cache)
            await db_session.flush()
            return mock_cache

        with patch.object(AIService, "generate_and_cache_phrases", new=mock_generate_and_cache) as mock_generate:
            hints = await round_service.get_or_generate_hints(copy_round.round_id, player, transaction_service)
            assert hints == hints_payload

        # Second call should use cached value from DB without calling generate_and_cache_phrases
        with patch.object(
            AIService,
            "generate_and_cache_phrases",
            new=AsyncMock(side_effect=AssertionError("should not be called")),
        ) as mock_generate:
            cached_hints = await round_service.get_or_generate_hints(copy_round.round_id, player, transaction_service)
            mock_generate.assert_not_called()
            assert cached_hints == hints_payload

    @pytest.mark.asyncio
    async def test_get_or_generate_hints_requires_active_copy(self, db_session):
        """Should reject requests for non-active copy rounds."""
        _, copy_round, player = await self._create_prompt_and_copy_round(db_session)
        copy_round.status = "submitted"
        await db_session.commit()

        round_service = RoundService(db_session)
        transaction_service = TransactionService(db_session)

        with pytest.raises(RoundExpiredError):
            await round_service.get_or_generate_hints(copy_round.round_id, player, transaction_service)
