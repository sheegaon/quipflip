"""Test variable prize pool implementation."""
import pytest
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.vote import Vote
from backend.services.round_service import RoundService
from backend.services.vote_service import VoteService
from backend.services.transaction_service import TransactionService
from backend.services.scoring_service import ScoringService
from backend.config import get_settings
import uuid
from datetime import datetime, timedelta, UTC

settings = get_settings()


@pytest.mark.asyncio
async def test_prize_pool_initialization(db_session):
    """Test that prize pool is initialized correctly when phraseset is created."""
    # Create test players
    player1 = Player(
        player_id=uuid.uuid4(),
        username="prompter",
        username_canonical="prompter",
        pseudonym="Prompter",
        pseudonym_canonical="prompter",
        email="prompter@test.com",
        password_hash="hash",
        balance=5000,
    )
    player2 = Player(
        player_id=uuid.uuid4(),
        username="copier1",
        username_canonical="copier1",
        pseudonym="Copier1",
        pseudonym_canonical="copier1",
        email="copier1@test.com",
        password_hash="hash",
        balance=5000,
    )
    player3 = Player(
        player_id=uuid.uuid4(),
        username="copier2",
        username_canonical="copier2",
        pseudonym="Copier2",
        pseudonym_canonical="copier2",
        email="copier2@test.com",
        password_hash="hash",
        balance=5000,
    )
    db_session.add_all([player1, player2, player3])
    await db_session.commit()

    # Create prompt round
    prompt_round = Round(
        round_id=uuid.uuid4(),
        player_id=player1.player_id,
        round_type="prompt",
        status="submitted",
        prompt_text="Test prompt",
        submitted_phrase="ORIGINAL",
        cost=settings.prompt_cost,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add(prompt_round)
    await db_session.commit()

    # Create two copy rounds
    copy1 = Round(
        round_id=uuid.uuid4(),
        player_id=player2.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        copy_phrase="COPY ONE",
        cost=settings.copy_cost_normal,
        system_contribution=0,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    copy2 = Round(
        round_id=uuid.uuid4(),
        player_id=player3.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        copy_phrase="COPY TWO",
        cost=settings.copy_cost_discount,
        system_contribution=10,  # Got discount
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add_all([copy1, copy2])
    await db_session.commit()

    # Create phraseset using round service
    round_service = RoundService(db_session)
    phraseset = await round_service.create_phraseset_if_ready(prompt_round)

    assert phraseset is not None, "Phraseset should be created"

    # Verify initial prize pool = base + system contribution
    expected_initial_pool = settings.prize_pool_base
    assert phraseset.total_pool == expected_initial_pool, \
        f"Initial pool should be {expected_initial_pool} (base={settings.prize_pool_base})"
    assert phraseset.vote_contributions == 0, "No votes yet"
    assert phraseset.vote_payouts_paid == 0, "No payouts yet"
    assert phraseset.system_contribution == 10, "System contribution should be 10"


@pytest.mark.asyncio
async def test_prize_pool_updates_with_votes(db_session):
    """Test that prize pool updates correctly as votes come in."""
    # Create test players with unique IDs to avoid conflicts
    test_id = uuid.uuid4().hex[:8]
    player1 = Player(
        player_id=uuid.uuid4(),
        username=f"prompter_{test_id}",
        username_canonical=f"prompter_{test_id}",
        pseudonym=f"Prompter_{test_id}",
        pseudonym_canonical=f"prompter_{test_id}",
        email=f"prompter_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    player2 = Player(
        player_id=uuid.uuid4(),
        username=f"copier1_{test_id}",
        username_canonical=f"copier1_{test_id}",
        pseudonym=f"Copier1_{test_id}",
        pseudonym_canonical=f"copier1_{test_id}",
        email=f"copier1_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    player3 = Player(
        player_id=uuid.uuid4(),
        username=f"copier2_{test_id}",
        username_canonical=f"copier2_{test_id}",
        pseudonym=f"Copier2_{test_id}",
        pseudonym_canonical=f"copier2_{test_id}",
        email=f"copier2_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    voter1 = Player(
        player_id=uuid.uuid4(),
        username=f"voter1_{test_id}",
        username_canonical=f"voter1_{test_id}",
        pseudonym=f"Voter1_{test_id}",
        pseudonym_canonical=f"voter1_{test_id}",
        email=f"voter1_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    voter2 = Player(
        player_id=uuid.uuid4(),
        username=f"voter2_{test_id}",
        username_canonical=f"voter2_{test_id}",
        pseudonym=f"Voter2_{test_id}",
        pseudonym_canonical=f"voter2_{test_id}",
        email=f"voter2_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    db_session.add_all([player1, player2, player3, voter1, voter2])
    await db_session.commit()

    # Create rounds and phraseset
    prompt_round = Round(
        round_id=uuid.uuid4(),
        player_id=player1.player_id,
        round_type="prompt",
        status="submitted",
        prompt_text="Test prompt",
        submitted_phrase="ORIGINAL",
        cost=settings.prompt_cost,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add(prompt_round)
    await db_session.commit()

    copy1 = Round(
        round_id=uuid.uuid4(),
        player_id=player2.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        copy_phrase="COPY ONE",
        cost=settings.copy_cost_normal,
        system_contribution=0,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    copy2 = Round(
        round_id=uuid.uuid4(),
        player_id=player3.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        copy_phrase="COPY TWO",
        cost=settings.copy_cost_normal,
        system_contribution=0,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add_all([copy1, copy2])
    await db_session.commit()

    phraseset = Phraseset(
        phraseset_id=uuid.uuid4(),
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy1.round_id,
        copy_round_2_id=copy2.round_id,
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
    await db_session.commit()

    vote_service = VoteService(db_session)
    transaction_service = TransactionService(db_session)

    initial_pool = phraseset.total_pool

    # Voter 1 votes correctly
    await vote_service.submit_system_vote(
        phraseset=phraseset,
        player=voter1,
        chosen_phrase="ORIGINAL",
        transaction_service=transaction_service,
    )
    await db_session.refresh(phraseset)

    # Check: pool should increase by vote_cost, decrease by vote_payout_correct
    expected_pool = initial_pool + settings.vote_cost - settings.vote_payout_correct
    assert phraseset.total_pool == expected_pool, \
        f"After correct vote, pool should be {expected_pool} (initial={initial_pool} + vote_cost={settings.vote_cost} - payout={settings.vote_payout_correct})"
    assert phraseset.vote_contributions == settings.vote_cost, "Should track vote contribution"
    assert phraseset.vote_payouts_paid == settings.vote_payout_correct, "Should track payout"

    # Voter 2 votes incorrectly
    await vote_service.submit_system_vote(
        phraseset=phraseset,
        player=voter2,
        chosen_phrase="COPY ONE",
        transaction_service=transaction_service,
    )
    await db_session.refresh(phraseset)

    # Check: pool should only increase by vote_cost (no payout for wrong answer)
    expected_pool = expected_pool + settings.vote_cost
    assert phraseset.total_pool == expected_pool, \
        f"After incorrect vote, pool should be {expected_pool}"
    assert phraseset.vote_contributions == settings.vote_cost * 2, "Should track both vote contributions"
    assert phraseset.vote_payouts_paid == settings.vote_payout_correct, "Payout only for correct vote"


@pytest.mark.asyncio
async def test_scoring_uses_dynamic_prize_pool(db_session):
    """Test that scoring service uses the dynamically updated prize pool."""
    # Create test players with unique IDs to avoid conflicts
    test_id = uuid.uuid4().hex[:8]
    player1 = Player(
        player_id=uuid.uuid4(),
        username=f"prompter_{test_id}",
        username_canonical=f"prompter_{test_id}",
        pseudonym=f"Prompter_{test_id}",
        pseudonym_canonical=f"prompter_{test_id}",
        email=f"prompter_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    player2 = Player(
        player_id=uuid.uuid4(),
        username=f"copier1_{test_id}",
        username_canonical=f"copier1_{test_id}",
        pseudonym=f"Copier1_{test_id}",
        pseudonym_canonical=f"copier1_{test_id}",
        email=f"copier1_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    player3 = Player(
        player_id=uuid.uuid4(),
        username=f"copier2_{test_id}",
        username_canonical=f"copier2_{test_id}",
        pseudonym=f"Copier2_{test_id}",
        pseudonym_canonical=f"copier2_{test_id}",
        email=f"copier2_{test_id}@test.com",
        password_hash="hash",
        balance=1000,
    )
    db_session.add_all([player1, player2, player3])
    await db_session.commit()

    # Create rounds
    prompt_round = Round(
        round_id=uuid.uuid4(),
        player_id=player1.player_id,
        round_type="prompt",
        status="submitted",
        prompt_text="Test prompt",
        submitted_phrase="ORIGINAL",
        cost=settings.prompt_cost,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    copy1 = Round(
        round_id=uuid.uuid4(),
        player_id=player2.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        copy_phrase="COPY ONE",
        cost=settings.copy_cost_normal,
        system_contribution=0,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    copy2 = Round(
        round_id=uuid.uuid4(),
        player_id=player3.player_id,
        round_type="copy",
        status="submitted",
        prompt_round_id=prompt_round.round_id,
        copy_phrase="COPY TWO",
        cost=settings.copy_cost_normal,
        system_contribution=0,
        expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    db_session.add_all([prompt_round, copy1, copy2])
    await db_session.commit()

    # Create phraseset with simulated voting
    phraseset = Phraseset(
        phraseset_id=uuid.uuid4(),
        prompt_round_id=prompt_round.round_id,
        copy_round_1_id=copy1.round_id,
        copy_round_2_id=copy2.round_id,
        prompt_text="Test prompt",
        original_phrase="ORIGINAL",
        copy_phrase_1="COPY ONE",
        copy_phrase_2="COPY TWO",
        status="finalized",
        vote_count=5,
        # Simulate: 5 votes at 10 each = 50 added, 2 correct at 20 each = 40 paid out
        total_pool=settings.prize_pool_base + 50 - 40,  # 210
        vote_contributions=50,
        vote_payouts_paid=40,
        system_contribution=0,
    )
    db_session.add(phraseset)

    # Add sample votes
    votes = [
        Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=uuid.uuid4(),
            voted_phrase="ORIGINAL",
            correct=True,
            payout=settings.vote_payout_correct,
        ),
        Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=uuid.uuid4(),
            voted_phrase="ORIGINAL",
            correct=True,
            payout=settings.vote_payout_correct,
        ),
        Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=uuid.uuid4(),
            voted_phrase="COPY ONE",
            correct=False,
            payout=0,
        ),
        Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=uuid.uuid4(),
            voted_phrase="COPY ONE",
            correct=False,
            payout=0,
        ),
        Vote(
            vote_id=uuid.uuid4(),
            phraseset_id=phraseset.phraseset_id,
            player_id=uuid.uuid4(),
            voted_phrase="COPY TWO",
            correct=False,
            payout=0,
        ),
    ]
    db_session.add_all(votes)
    await db_session.commit()

    # Calculate payouts
    scoring_service = ScoringService(db_session)
    payouts = await scoring_service.calculate_payouts(phraseset)

    # Verify payouts are calculated from dynamic pool
    expected_pool = 210  # base=200 + votes=50 - payouts=40
    total_payout = payouts["original"]["payout"] + payouts["copy1"]["payout"] + payouts["copy2"]["payout"]

    # Total payouts should be close to the prize pool (some rounding may occur)
    assert abs(total_payout - expected_pool) <= 2, \
        f"Total payouts ({total_payout}) should be close to prize pool ({expected_pool})"

    # Points: ORIGINAL=2*1=2, COPY ONE=2*2=4, COPY TWO=1*2=2, total=8
    # ORIGINAL gets 2/8 of pool, COPY ONE gets 4/8, COPY TWO gets 2/8
    expected_original = (2 * expected_pool) // 8
    expected_copy1 = (4 * expected_pool) // 8
    expected_copy2 = (2 * expected_pool) // 8

    assert payouts["original"]["payout"] == expected_original, \
        f"Original payout should be {expected_original}"
    assert payouts["copy1"]["payout"] == expected_copy1, \
        f"Copy1 payout should be {expected_copy1}"
    assert payouts["copy2"]["payout"] == expected_copy2, \
        f"Copy2 payout should be {expected_copy2}"
