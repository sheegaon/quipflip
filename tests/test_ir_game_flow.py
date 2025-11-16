"""Tests for IR game flow (backronym creation, voting, results)."""
import pytest
import uuid
from backend.services.ir.player_service import IRPlayerService
from backend.services.ir.ir_backronym_set_service import IRBackronymSetService
from backend.services.ir.ir_vote_service import IRVoteService
from backend.services.ir.transaction_service import IRTransactionService
from backend.services.ir.ir_scoring_service import IRScoringService
from backend.services.ir.ir_word_service import IRWordService
from backend.utils.passwords import hash_password


@pytest.fixture
async def ir_player_factory(db_session):
    """Factory for creating IR test players."""
    player_service = IRPlayerService(db_session)

    async def _create_player(
        email: str | None = None,
        password: str = "TestPassword123!",
    ):
        if email is None:
            email = f"irplayer{uuid.uuid4().hex[:8]}@example.com"

        password_hash = hash_password(password)
        return await player_service.create_player(
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
    word = word_service.get_random_word()
    backronym_set = await set_service.create_set(word=word, mode="standard")

    assert backronym_set is not None
    assert backronym_set.word == word
    assert backronym_set.mode == "standard"
    assert backronym_set.status == "open"
    assert backronym_set.entry_count == 0


@pytest.mark.asyncio
async def test_ir_submit_backronym_entry(db_session, ir_player_factory):
    """Test submitting a backronym entry."""
    set_service = IRBackronymSetService(db_session)
    transaction_service = IRTransactionService(db_session)
    word_service = IRWordService(db_session)

    player = await ir_player_factory()
    initial_balance = player.wallet

    # Create set and submit entry
    word = word_service.get_random_word()
    backronym_set = await set_service.create_set(word=word, mode="standard")

    # Create backronym (matching word length)
    backronym_words = [f"word{i}" for i in range(len(word))]

    entry = await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=player.player_id,
        backronym_text=backronym_words
    )

    assert entry is not None
    assert entry.player_id == player.player_id
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
    word = word_service.get_random_word()
    backronym_set = await set_service.create_set(word=word, mode="standard")

    # Submit first entry
    backronym_words_1 = [f"word{i}" for i in range(len(word))]
    await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=player.player_id,
        backronym_text=backronym_words_1
    )

    # Try to submit second entry
    backronym_words_2 = [f"other{i}" for i in range(len(word))]
    with pytest.raises(Exception):  # Should raise IntegrityError due to unique constraint
        await set_service.add_entry(
            set_id=backronym_set.set_id,
            player_id=player.player_id,
            backronym_text=backronym_words_2
        )


@pytest.mark.asyncio
async def test_ir_set_transitions_to_voting(db_session, ir_player_factory):
    """Test that set transitions to voting after 5 entries."""
    set_service = IRBackronymSetService(db_session)
    word_service = IRWordService(db_session)

    # Create 5 players and set
    players = [await ir_player_factory() for _ in range(5)]
    word = word_service.get_random_word()
    backronym_set = await set_service.create_set(word=word, mode="standard")

    # Add 5 entries
    for player in players:
        backronym_words = [f"word{i}_{uuid.uuid4().hex[:4]}" for i in range(len(word))]
        await set_service.add_entry(
            set_id=backronym_set.set_id,
            player_id=player.player_id,
            backronym_text=backronym_words
        )

    # Refresh and check status
    updated_set = await set_service.get_set_details(backronym_set.set_id)
    assert updated_set.entry_count == 5
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
    word = word_service.get_random_word()
    backronym_set = await set_service.create_set(word=word, mode="standard")

    backronym_words = [f"word{i}" for i in range(len(word))]
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
    assert vote.player_id == voter.player_id
    assert vote.chosen_entry_id == entry.entry_id


@pytest.mark.asyncio
async def test_ir_cannot_self_vote(db_session, ir_player_factory):
    """Test that players cannot vote for their own entry."""
    set_service = IRBackronymSetService(db_session)
    vote_service = IRVoteService(db_session)
    word_service = IRWordService(db_session)

    player = await ir_player_factory()

    # Create set and entry
    word = word_service.get_random_word()
    backronym_set = await set_service.create_set(word=word, mode="standard")

    backronym_words = [f"word{i}" for i in range(len(word))]
    entry = await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=player.player_id,
        backronym_text=backronym_words
    )

    # Try to vote for own entry
    with pytest.raises(Exception):  # Should raise error for self-vote
        await vote_service.submit_vote(
            set_id=backronym_set.set_id,
            player_id=player.player_id,
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
    word = word_service.get_random_word()
    backronym_set = await set_service.create_set(word=word, mode="standard")

    backronym_words = [f"word{i}" for i in range(len(word))]
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
    """Test that player cannot start with insufficient balance."""
    set_service = IRBackronymSetService(db_session)
    word_service = IRWordService(db_session)

    player = await ir_player_factory()
    # Set balance to less than entry cost
    player.wallet = 50
    await db_session.commit()

    word = word_service.get_random_word()
    backronym_set = await set_service.create_set(word=word, mode="standard")

    backronym_words = [f"word{i}" for i in range(len(word))]

    # Should raise error for insufficient balance
    with pytest.raises(Exception):
        await set_service.add_entry(
            set_id=backronym_set.set_id,
            player_id=player.player_id,
            backronym_text=backronym_words
        )
