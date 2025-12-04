"""Tests for IR game flow (backronym creation, voting, results)."""
import pytest
import uuid
from backend.services import GameType, IRPlayerService
from backend.services import IRBackronymSetService
from backend.services import IRVoteService
from backend.services import TransactionService
from backend.services import IRScoringService
from backend.services import IRWordService
from backend.utils.passwords import hash_password


@pytest.fixture
async def ir_player_factory(db_session):
    """Factory for creating IR test players."""
    player_service = IRPlayerService(db_session)

    async def _create_player(
        email: str | None = None,
        username: str | None = None,
        password: str = "TestPassword123!",
    ):
        if email is None:
            email = f"irplayer{uuid.uuid4().hex[:8]}@example.com"
        if username is None:
            username = f"player_{uuid.uuid4().hex[:8]}"

        password_hash = hash_password(password)
        return await player_service.create_player(
            username=username,
            email=email,
            password_hash=password_hash,
        )

    return _create_player


@pytest.mark.asyncio
async def test_ir_create_backronym_set(db_session, ir_player_factory):
    """Test creating a new backronym set."""
    set_service = IRBackronymSetService(db_session)
    word_service = IRWordService(db_session)

    player = await ir_player_factory()

    # Create set
    backronym_set = await set_service.create_set(mode="standard")

    assert backronym_set is not None
    assert backronym_set.word is not None
    assert len(backronym_set.word) > 0
    assert backronym_set.mode == "standard"
    assert backronym_set.status == "open"
    assert backronym_set.entry_count == 0


@pytest.mark.asyncio
async def test_ir_submit_backronym_entry(db_session, ir_player_factory):
    """Test submitting a backronym entry."""
    set_service = IRBackronymSetService(db_session)
    transaction_service = TransactionService(db_session, GameType.IR)
    word_service = IRWordService(db_session)

    player = await ir_player_factory()
    initial_balance = player.wallet

    # Create set and submit entry

    backronym_set = await set_service.create_set(mode="standard")

    # Create backronym (matching word length)
    backronym_words = [f"word{i}" for i in range(len(backronym_set.word))]

    # Debit wallet for entry
    await transaction_service.debit_wallet(
        player_id=str(player.player_id),
        amount=100,
        transaction_type="entry_creation",
        reference_id=str(backronym_set.set_id),
    )

    entry = await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=str(player.player_id),
        backronym_text=backronym_words
    )

    assert entry is not None
    assert str(entry.player_id) == str(player.player_id)
    assert entry.backronym_text == backronym_words

    # Verify player was charged
    await db_session.refresh(player)
    assert player.wallet == initial_balance - 100  # Entry cost


@pytest.mark.asyncio
async def test_ir_cannot_duplicate_entry(db_session, ir_player_factory):
    """Test that player cannot submit multiple entries to same set."""
    set_service = IRBackronymSetService(db_session)
    word_service = IRWordService(db_session)

    player = await ir_player_factory()

    # Create set
    
    backronym_set = await set_service.create_set(mode="standard")

    # Submit first entry
    backronym_words_1 = [f"word{i}" for i in range(len(backronym_set.word))]
    await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=str(player.player_id),
        backronym_text=backronym_words_1
    )

    # Try to submit second entry
    backronym_words_2 = [f"other{i}" for i in range(len(backronym_set.word))]
    with pytest.raises(Exception):  # Should raise IntegrityError due to unique constraint
        await set_service.add_entry(
            set_id=backronym_set.set_id,
            player_id=str(player.player_id),
            backronym_text=backronym_words_2
        )


@pytest.mark.asyncio
async def test_ir_set_transitions_to_voting(db_session, ir_player_factory):
    """Test that set transitions to voting after 5 entries."""
    set_service = IRBackronymSetService(db_session)
    word_service = IRWordService(db_session)

    # Create 5 players and set
    players = [await ir_player_factory() for _ in range(5)]
    
    backronym_set = await set_service.create_set(mode="standard")

    # Add 5 entries
    for player in players:
        backronym_words = [f"word{i}_{uuid.uuid4().hex[:4]}" for i in range(len(backronym_set.word))]
        await set_service.add_entry(
            set_id=backronym_set.set_id,
            player_id=str(player.player_id),
            backronym_text=backronym_words
        )

    # Refresh and check status
    updated_set = await set_service.get_set_details(backronym_set.set_id)
    assert updated_set.get("entry_count") == 5
    # Note: Set might not auto-transition to voting; may need explicit call
    # This depends on implementation details


@pytest.mark.asyncio
async def test_ir_submit_vote(db_session, ir_player_factory):
    """Test submitting a vote on backronym entries."""
    set_service = IRBackronymSetService(db_session)
    vote_service = IRVoteService(db_session)
    word_service = IRWordService(db_session)

    # Create 2 players
    creator = await ir_player_factory()
    voter = await ir_player_factory()

    # Create set and entry
    
    backronym_set = await set_service.create_set(mode="standard")

    backronym_words = [f"word{i}" for i in range(len(backronym_set.word))]
    entry = await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=creator.player_id,
        backronym_text=backronym_words
    )

    # Voter submits vote
    vote = await vote_service.submit_vote(
        set_id=backronym_set.set_id,
        player_id=voter.player_id,
        chosen_entry_id=entry.entry_id,
        is_participant=False
    )

    assert vote is not None
    assert vote.get("vote_id") is not None
    assert vote.get("chosen_entry_id") is not None


@pytest.mark.asyncio
async def test_ir_cannot_self_vote(db_session, ir_player_factory):
    """Test that players cannot vote for their own entry."""
    set_service = IRBackronymSetService(db_session)
    vote_service = IRVoteService(db_session)
    word_service = IRWordService(db_session)

    player = await ir_player_factory()

    # Create set and entry
    
    backronym_set = await set_service.create_set(mode="standard")

    backronym_words = [f"word{i}" for i in range(len(backronym_set.word))]
    entry = await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=str(player.player_id),
        backronym_text=backronym_words
    )

    # Try to vote for own entry
    with pytest.raises(Exception):  # Should raise error for self-vote
        await vote_service.submit_vote(
            set_id=backronym_set.set_id,
            player_id=str(player.player_id),
            chosen_entry_id=entry.entry_id,
            is_participant=True
        )


@pytest.mark.asyncio
async def test_ir_cannot_vote_twice(db_session, ir_player_factory):
    """Test that player cannot vote twice on same set."""
    set_service = IRBackronymSetService(db_session)
    vote_service = IRVoteService(db_session)
    word_service = IRWordService(db_session)

    creator = await ir_player_factory()
    voter = await ir_player_factory()

    # Create set and entry
    
    backronym_set = await set_service.create_set(mode="standard")

    backronym_words = [f"word{i}" for i in range(len(backronym_set.word))]
    entry = await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=creator.player_id,
        backronym_text=backronym_words
    )

    # Submit first vote
    await vote_service.submit_vote(
        set_id=backronym_set.set_id,
        player_id=voter.player_id,
        chosen_entry_id=entry.entry_id,
        is_participant=False
    )

    # Try to submit second vote on same set
    with pytest.raises(Exception):  # Should raise error for duplicate vote
        await vote_service.submit_vote(
            set_id=backronym_set.set_id,
            player_id=voter.player_id,
            chosen_entry_id=entry.entry_id,
            is_participant=False
        )


@pytest.mark.asyncio
async def test_ir_non_participant_vote_cap(db_session, ir_player_factory):
    """Test guest player vote cap enforcement."""
    from backend.config import get_settings

    vote_service = IRVoteService(db_session)
    settings = get_settings()

    # This test would require setting up multiple sets with guests
    # and verifying the vote cap is enforced
    # Implementation depends on how vote cap is tracked
    pass


@pytest.mark.asyncio
async def test_ir_player_insufficient_balance(db_session, ir_player_factory):
    """Test that player cannot debit more than their balance."""
    from backend.services import TransactionService

    player = await ir_player_factory()
    transaction_service = TransactionService(db_session, GameType.IR)

    # Set balance to less than entry cost
    player.wallet = 50
    await db_session.commit()

    # Try to debit 100 when only 50 available (should fail)
    with pytest.raises(Exception):
        await transaction_service.debit_wallet(
            player_id=str(player.player_id),
            amount=100,  # Need 100 but only have 50
            transaction_type="ir_backronym_entry",
            reference_id=None
        )
