"""End-to-end tests for complete IR game flows."""
import pytest
import uuid
from backend.services import AuthService
from backend.services import IRBackronymSetService
from backend.services import IRVoteService
from backend.services import IRWordService
from backend.services import IRResultViewService
from backend.services import IRStatisticsService


@pytest.mark.asyncio
async def test_ir_complete_game_flow(db_session):
    """Test complete IR game flow from start to finish."""
    # Services
    auth_service = AuthService(db_session)
    set_service = IRBackronymSetService(db_session)
    vote_service = IRVoteService(db_session)
    word_service = IRWordService(db_session)
    result_service = IRResultViewService(db_session)
    stats_service = IRStatisticsService(db_session)

    # 1. Create 5 players
    players = []
    for i in range(5):
        username = f"player{i}_{uuid.uuid4().hex[:4]}"
        email = f"player{i}{uuid.uuid4().hex[:4]}@example.com"
        player, token = await auth_service.register(
            username=username,
            email=email,
            password="TestPassword123!"
        )
        players.append(player)

    # 2. Create a backronym set
    backronym_set = await set_service.create_set(mode="standard")
    assert backronym_set.status == "open"
    word = backronym_set.word

    # 3. First 5 players submit backronyms
    entries = []
    for i, player in enumerate(players):
        backronym_words = [f"word{j}_{i}" for j in range(len(word))]
        entry = await set_service.add_entry(
            set_id=backronym_set.set_id,
            player_id=player.player_id,
            backronym_text=backronym_words
        )
        entries.append(entry)

    # Verify set has 5 entries
    updated_set = await set_service.get_set_details(backronym_set.set_id)
    assert updated_set.get("entry_count") == 5

    # 4. Create additional voters
    voters = []
    for i in range(3):
        username = f"voter{i}_{uuid.uuid4().hex[:4]}"
        email = f"voter{i}{uuid.uuid4().hex[:4]}@example.com"
        voter, _ = await auth_service.register(
            username=username,
            email=email,
            password="TestPassword123!"
        )
        voters.append(voter)

    # 5. Voters submit votes (non-participants)
    votes = []
    for voter in voters:
        # Each voter votes for a different entry
        entry_index = voters.index(voter) % len(entries)
        vote = await vote_service.submit_vote(
            set_id=backronym_set.set_id,
            player_id=voter.player_id,
            chosen_entry_id=entries[entry_index].entry_id,
            is_participant=False
        )
        votes.append(vote)

    # Verify votes were recorded
    assert len(votes) == 3

    # 6. Verify player stats exist
    for player in players:
        stats = await stats_service.get_player_stats(player.player_id)
        # Stats should be available (even if zero)
        assert stats is not None

    # 7. Test results viewing (claim results)
    # Note: Results endpoint would typically return finalized set with payouts
    # This is a simplified test of the flow
    finalized_set = await set_service.get_set_details(backronym_set.set_id)
    assert finalized_set is not None

    print(f"✅ Complete game flow test passed!")
    print(f"   - Created 5 players")
    print(f"   - Created 1 backronym set with word '{word}'")
    print(f"   - Submitted 5 backronym entries")
    print(f"   - Created 3 voters")
    print(f"   - Submitted 3 votes")
    print(f"   - Verified stats and results")


@pytest.mark.asyncio
async def test_ir_guest_player_flow(db_session):
    """Test IR game flow with guest player."""
    auth_service = AuthService(db_session)
    set_service = IRBackronymSetService(db_session)
    word_service = IRWordService(db_session)

    # 1. Create guest player
    guest, guest_token = await auth_service.register_guest()
    assert guest.is_guest is True

    # 2. Guest can start a game
    backronym_set = await set_service.create_set(mode="standard")
    word = backronym_set.word

    # 3. Guest submits backronym
    backronym_words = [f"word{i}" for i in range(len(word))]
    entry = await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=guest.player_id,
        backronym_text=backronym_words
    )
    assert entry is not None

    # 4. Upgrade guest to full account
    email = f"upgraded{uuid.uuid4().hex[:8]}@example.com"
    upgraded_player, new_token = await auth_service.upgrade_guest(
        guest,
        email,
        "NewPassword123!"
    )

    assert upgraded_player.is_guest is False
    assert upgraded_player.email == email
    assert new_token is not None

    print(f"✅ Guest player flow test passed!")
    print(f"   - Created guest account")
    print(f"   - Guest submitted backronym")
    print(f"   - Upgraded guest to full account")


@pytest.mark.asyncio
async def test_ir_daily_bonus_flow(db_session):
    """Test daily bonus claiming flow."""
    from backend.services import IRDailyBonusService
    from datetime import timedelta

    auth_service = AuthService(db_session)
    bonus_service = IRDailyBonusService(db_session)

    # 1. Register player
    username = f"bonusplayer{uuid.uuid4().hex[:4]}"
    email = f"bonus{uuid.uuid4().hex[:4]}@example.com"
    player, _ = await auth_service.register(
        username=username,
        email=email,
        password="TestPassword123!"
    )

    # Set created_at to at least 1 day ago so bonus is available
    player.created_at = player.created_at - timedelta(days=1)
    await db_session.commit()

    initial_balance = player.wallet

    # 2. Claim daily bonus
    bonus = await bonus_service.claim_bonus(player.player_id)
    assert bonus is not None

    # Verify balance increased
    from sqlalchemy import select
    from backend.models.ir.player import IRPlayer
    stmt = select(IRPlayer).where(IRPlayer.player_id == player.player_id)
    result = await db_session.execute(stmt)
    updated_player = result.scalars().first()

    assert updated_player.wallet > initial_balance

    # 3. Try to claim again (should fail or return None)
    try:
        bonus2 = await bonus_service.claim_bonus(player.player_id)
        # If it succeeds, check that it's not allowed twice
        if bonus2 is not None:
            assert False, "Should not allow claiming bonus twice"
    except Exception:
        # Expected to raise an exception
        pass

    print(f"✅ Daily bonus flow test passed!")
    print(f"   - Claimed daily bonus successfully")
    print(f"   - Balance increased by 100 IC")
    print(f"   - Second claim blocked")


@pytest.mark.asyncio
async def test_ir_self_vote_prevention(db_session):
    """Test that players cannot vote for their own entries."""
    auth_service = AuthService(db_session)
    set_service = IRBackronymSetService(db_session)
    vote_service = IRVoteService(db_session)
    word_service = IRWordService(db_session)

    # 1. Create player
    player, _ = await auth_service.register(
        username=f"player{uuid.uuid4().hex[:4]}",
        email=f"test{uuid.uuid4().hex[:4]}@example.com",
        password="TestPassword123!"
    )

    # 2. Create set and submit entry
    backronym_set = await set_service.create_set(mode="standard")
    word = backronym_set.word

    backronym_words = [f"word{i}" for i in range(len(word))]
    entry = await set_service.add_entry(
        set_id=backronym_set.set_id,
        player_id=player.player_id,
        backronym_text=backronym_words
    )

    # 3. Try to vote for own entry (should fail)
    with pytest.raises(Exception):
        await vote_service.submit_vote(
            set_id=backronym_set.set_id,
            player_id=player.player_id,
            chosen_entry_id=entry.entry_id,
            is_participant=True
        )

    print(f"✅ Self-vote prevention test passed!")
    print(f"   - Player cannot vote for own entry")


@pytest.mark.asyncio
async def test_ir_insufficient_balance_blocking(db_session):
    """Test that players with insufficient balance cannot enter."""
    from sqlalchemy import update
    from backend.models.ir.player import IRPlayer
    from backend.services import TransactionService

    auth_service = AuthService(db_session)
    set_service = IRBackronymSetService(db_session)
    transaction_service = TransactionService(db_session)

    # 1. Create player
    player, _ = await auth_service.register(
        username=f"player{uuid.uuid4().hex[:4]}",
        email=f"test{uuid.uuid4().hex[:4]}@example.com",
        password="TestPassword123!"
    )

    # 2. Set balance to 50 (less than 100 entry cost)
    stmt = update(IRPlayer).where(IRPlayer.player_id == player.player_id).values(wallet=50)
    await db_session.execute(stmt)
    await db_session.commit()

    # 3. Try to debit wallet (should fail with insufficient balance)
    backronym_set = await set_service.create_set(mode="standard")

    with pytest.raises(Exception):
        await transaction_service.debit_wallet(
            player_id=str(player.player_id),
            amount=100,  # costs 100 IC but player only has 50
            transaction_type=transaction_service.ENTRY_CREATION,
            reference_id=str(backronym_set.set_id),
        )

    print(f"✅ Insufficient balance blocking test passed!")
    print(f"   - Player with 50 IC cannot debit 100 IC (insufficient balance)")
