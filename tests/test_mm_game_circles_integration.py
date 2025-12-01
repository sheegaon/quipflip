"""Integration tests for MM Circles game logic (Phase 3)."""

import pytest
from datetime import datetime, UTC
from uuid import UUID, uuid4
from sqlalchemy import delete

from backend.models.mm.player import MMPlayer
from backend.models.mm.image import MMImage
from backend.models.mm.caption import MMCaption
from backend.models.mm.circle import MMCircle
from backend.models.mm.circle_member import MMCircleMember
from backend.services.mm.game_service import MMGameService
from backend.services.mm.vote_service import MMVoteService
from backend.services.mm.circle_service import MMCircleService
from backend.services.transaction_service import TransactionService
from backend.utils.model_registry import GameType
from backend.utils.exceptions import NoContentAvailableError
from backend.database import AsyncSessionLocal


@pytest.fixture
async def db_session():
    """Create a test database session."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def setup_circle_test_data(db_session):
    """Create test data with Circle relationships."""
    # Create 3 players
    uid1 = uuid4()
    player1 = MMPlayer(
        player_id=uid1,
        username=f"testplayer1_{uid1.hex[:8]}",
        username_canonical=f"testplayer1_{uid1.hex[:8]}".lower(),
        email=f"test1_{uid1.hex[:8]}@example.com",
        password_hash="dummy_hash",
        wallet=1000,
        vault=0,
        created_at=datetime.now(UTC)
    )
    uid2 = uuid4()
    player2 = MMPlayer(
        player_id=uid2,
        username=f"testplayer2_{uid2.hex[:8]}",
        username_canonical=f"testplayer2_{uid2.hex[:8]}".lower(),
        email=f"test2_{uid2.hex[:8]}@example.com",
        password_hash="dummy_hash",
        wallet=1000,
        vault=0,
        created_at=datetime.now(UTC)
    )
    uid3 = uuid4()
    player3 = MMPlayer(
        player_id=uid3,
        username=f"testplayer3_{uid3.hex[:8]}",
        username_canonical=f"testplayer3_{uid3.hex[:8]}".lower(),
        email=f"test3_{uid3.hex[:8]}@example.com",
        password_hash="dummy_hash",
        wallet=1000,
        vault=0,
        created_at=datetime.now(UTC)
    )
    db_session.add_all([player1, player2, player3])
    await db_session.flush()

    # Create a Circle with player1 and player2 as members
    circle = MMCircle(
        circle_id=uuid4(),
        name=f"Test Circle {uuid4().hex[:8]}",
        created_by_player_id=player1.player_id,
        member_count=2,
        created_at=datetime.now(UTC)
    )
    db_session.add(circle)
    await db_session.flush()

    member1 = MMCircleMember(
        circle_id=circle.circle_id,
        player_id=player1.player_id,
        role="admin",
        joined_at=datetime.now(UTC)
    )
    member2 = MMCircleMember(
        circle_id=circle.circle_id,
        player_id=player2.player_id,
        role="member",
        joined_at=datetime.now(UTC)
    )
    db_session.add_all([member1, member2])
    await db_session.flush()

    # Create images
    image_with_circle = MMImage(
        image_id=uuid4(),
        source_url="https://example.com/circle.jpg",
        status="active",
        created_at=datetime.now(UTC)
    )
    image_global = MMImage(
        image_id=uuid4(),
        source_url="https://example.com/global.jpg",
        status="active",
        created_at=datetime.now(UTC)
    )
    db_session.add_all([image_with_circle, image_global])
    await db_session.flush()

    # Create captions on image_with_circle
    # 3 from Circle-mate (player2), 5 from non-Circle player (player3)
    circle_captions = []
    for i in range(3):
        caption = MMCaption(
            caption_id=uuid4(),
            image_id=image_with_circle.image_id,
            text=f"Circle caption {i}",
            author_player_id=player2.player_id,
            kind="caption",
            status="active",
            quality_score=0.5 + (i * 0.1),
            created_at=datetime.now(UTC)
        )
        circle_captions.append(caption)
        db_session.add(caption)

    global_captions_on_circle_image = []
    for i in range(5):
        caption = MMCaption(
            caption_id=uuid4(),
            image_id=image_with_circle.image_id,
            text=f"Global caption on circle image {i}",
            author_player_id=player3.player_id,
            kind="caption",
            status="active",
            quality_score=0.5 + (i * 0.1),
            created_at=datetime.now(UTC)
        )
        global_captions_on_circle_image.append(caption)
        db_session.add(caption)

    # Create captions on image_global (all from player3)
    global_captions = []
    for i in range(5):
        caption = MMCaption(
            caption_id=uuid4(),
            image_id=image_global.image_id,
            text=f"Global caption {i}",
            author_player_id=player3.player_id,
            kind="caption",
            status="active",
            quality_score=0.5 + (i * 0.1),
            created_at=datetime.now(UTC)
        )
        global_captions.append(caption)
        db_session.add(caption)

    await db_session.commit()

    test_data = {
        "player1": player1,
        "player2": player2,
        "player3": player3,
        "circle": circle,
        "image_with_circle": image_with_circle,
        "image_global": image_global,
        "circle_captions": circle_captions,
        "global_captions_on_circle_image": global_captions_on_circle_image,
        "global_captions": global_captions,
    }

    yield test_data

    # Cleanup: Delete test circle after test completes
    # Cascade deletion will automatically remove members and join requests
    try:
        await db_session.execute(
            delete(MMCircle).where(MMCircle.circle_id == circle.circle_id)
        )
        await db_session.commit()
    except Exception:
        # Circle may have already been deleted by the test
        await db_session.rollback()


@pytest.mark.asyncio
async def test_image_selection_prioritizes_circle_content(db_session, setup_circle_test_data):
    """Test that image selection prioritizes images with Circle-mate content."""
    data = setup_circle_test_data
    player1 = data["player1"]
    image_with_circle = data["image_with_circle"]

    game_service = MMGameService(db_session)

    # Player1 should preferentially get image_with_circle since it has Circle-mate captions
    # Run multiple times to check for preference (not guaranteed every time due to randomness)
    circle_image_count = 0
    trials = 10

    for _ in range(trials):
        image = await game_service._select_image_for_vote(player1.player_id, 5)
        if image and image.image_id == image_with_circle.image_id:
            circle_image_count += 1

    # Should select Circle image at least 70% of the time (with some randomness tolerance)
    assert circle_image_count >= 7, (
        f"Expected Circle image to be selected at least 7/10 times, "
        f"but got {circle_image_count}/10"
    )


@pytest.mark.asyncio
async def test_caption_selection_circle_first_case_a(db_session, setup_circle_test_data):
    """Test caption selection Case A: >= 5 Circle captions available."""
    data = setup_circle_test_data
    player1 = data["player1"]
    image_with_circle = data["image_with_circle"]
    player2 = data["player2"]

    # Add 2 more Circle captions to get to 5 total
    for i in range(2):
        caption = MMCaption(
            caption_id=uuid4(),
            image_id=image_with_circle.image_id,
            text=f"Extra circle caption {i}",
            author_player_id=player2.player_id,
            kind="caption",
            status="active",
            quality_score=0.6,
            created_at=datetime.now(UTC)
        )
        db_session.add(caption)
    await db_session.commit()

    game_service = MMGameService(db_session)

    # Select captions
    selected = await game_service._select_captions_for_round(
        image_with_circle.image_id,
        player1.player_id,
        5
    )

    # All 5 should be from Circle-mate (player2)
    assert len(selected) == 5
    assert all(c.author_player_id == player2.player_id for c in selected), (
        "Expected all 5 captions to be from Circle-mate in Case A"
    )


@pytest.mark.asyncio
async def test_caption_selection_circle_first_case_b(db_session, setup_circle_test_data):
    """Test caption selection Case B: 0 < k < 5 Circle captions."""
    data = setup_circle_test_data
    player1 = data["player1"]
    image_with_circle = data["image_with_circle"]
    player2 = data["player2"]
    player3 = data["player3"]

    game_service = MMGameService(db_session)

    # 3 Circle captions + 5 global captions available
    selected = await game_service._select_captions_for_round(
        image_with_circle.image_id,
        player1.player_id,
        5
    )

    # Should have all 3 Circle captions + 2 global
    assert len(selected) == 5
    circle_count = sum(1 for c in selected if c.author_player_id == player2.player_id)
    global_count = sum(1 for c in selected if c.author_player_id == player3.player_id)

    assert circle_count == 3, f"Expected 3 Circle captions, got {circle_count}"
    assert global_count == 2, f"Expected 2 Global captions, got {global_count}"


@pytest.mark.asyncio
async def test_caption_selection_circle_first_case_c(db_session, setup_circle_test_data):
    """Test caption selection Case C: 0 Circle captions."""
    data = setup_circle_test_data
    player1 = data["player1"]
    image_global = data["image_global"]
    player3 = data["player3"]

    game_service = MMGameService(db_session)

    # image_global has no Circle captions
    selected = await game_service._select_captions_for_round(
        image_global.image_id,
        player1.player_id,
        5
    )

    # All should be global (from player3)
    assert len(selected) == 5
    assert all(c.author_player_id == player3.player_id for c in selected), (
        "Expected all 5 captions to be from global pool in Case C"
    )


@pytest.mark.asyncio
async def test_system_bonus_suppressed_for_circle_mates(db_session, setup_circle_test_data):
    """Test that system bonus is suppressed when voting for Circle-mate's caption."""
    data = setup_circle_test_data
    player1 = data["player1"]
    player2 = data["player2"]
    circle_captions = data["circle_captions"]

    # Create a round for player1
    transaction_service = TransactionService(db_session, GameType.MM)
    game_service = MMGameService(db_session)
    vote_service = MMVoteService(db_session)

    # Start a vote round
    round_obj = await game_service.start_vote_round(player1, transaction_service)
    await db_session.refresh(player1)
    wallet_after_entry = player1.wallet  # Should be 1000 - 5 = 995

    # Get a Circle-mate's caption from the round
    caption_ids_shown = [UUID(c) if isinstance(c, str) else c for c in round_obj.caption_ids_shown]

    # Find a Circle caption that was shown (if any)
    circle_caption_id = None
    for cid in caption_ids_shown:
        caption = await db_session.get(MMCaption, cid)
        if caption and caption.author_player_id == player2.player_id:
            circle_caption_id = caption.caption_id
            break

    if not circle_caption_id:
        pytest.skip("No Circle caption was shown in this round (randomness)")

    # Submit vote for Circle-mate's caption
    result = await vote_service.submit_vote(
        round_obj,
        circle_caption_id,
        player1,
        transaction_service
    )

    await db_session.refresh(player2)

    # Entry cost = 5 MC
    # Base payout = 5 MC (always given)
    # Writer bonus = 5 * 2 = 10 MC (SUPPRESSED for Circle-mate)
    # Total gross = 5 MC (base only)
    # House rake = 5 * 0.3 = 1.5 MC
    # Net to author = 5 - 1.5 = 3.5 MC

    # Check that player2 got only base payout (no 3x multiplier)
    payout_info = result.get("payout_info", {})
    total_gross = payout_info.get("total_gross", 0)

    # Total gross should be 5 (base only), not 15 (base + 2x bonus)
    assert total_gross == 5, (
        f"Expected total_gross=5 (base only) for Circle-mate, got {total_gross}"
    )


@pytest.mark.asyncio
async def test_system_bonus_awarded_for_non_circle_mates(db_session, setup_circle_test_data):
    """Test that system bonus is awarded when voting for non-Circle-mate's caption."""
    data = setup_circle_test_data
    player1 = data["player1"]
    player3 = data["player3"]

    transaction_service = TransactionService(db_session, GameType.MM)
    game_service = MMGameService(db_session)
    vote_service = MMVoteService(db_session)

    # Start a vote round
    round_obj = await game_service.start_vote_round(player1, transaction_service)
    await db_session.refresh(player1)

    # Get a non-Circle caption from the round
    caption_ids_shown = [UUID(c) if isinstance(c, str) else c for c in round_obj.caption_ids_shown]

    non_circle_caption_id = None
    for cid in caption_ids_shown:
        caption = await db_session.get(MMCaption, cid)
        if caption and caption.author_player_id == player3.player_id:
            non_circle_caption_id = caption.caption_id
            break

    if not non_circle_caption_id:
        pytest.skip("No non-Circle caption was shown in this round (randomness)")

    # Submit vote for non-Circle-mate's caption
    result = await vote_service.submit_vote(
        round_obj,
        non_circle_caption_id,
        player1,
        transaction_service
    )

    await db_session.refresh(player3)

    # Entry cost = 5 MC
    # Base payout = 5 MC
    # Writer bonus = 5 * 2 = 10 MC (AWARDED for non-Circle-mate)
    # Total gross = 15 MC
    # House rake = 15 * 0.3 = 4.5 MC
    # Net to author = 15 - 4.5 = 10.5 MC

    payout_info = result.get("payout_info", {})
    total_gross = payout_info.get("total_gross", 0)

    # Total gross should be 15 (base + 2x bonus)
    assert total_gross == 15, (
        f"Expected total_gross=15 (base + bonus) for non-Circle-mate, got {total_gross}"
    )


@pytest.mark.asyncio
async def test_circle_mate_relationship_is_bidirectional(db_session):
    """Test that Circle-mate relationship works both ways."""
    # Create 2 players in a Circle
    uid_a = uuid4()
    player_a = MMPlayer(
        player_id=uid_a,
        username=f"testplayera_{uid_a.hex[:8]}",
        username_canonical=f"testplayera_{uid_a.hex[:8]}".lower(),
        email=f"testa_{uid_a.hex[:8]}@example.com",
        password_hash="dummy_hash",
        wallet=1000,
        vault=0,
        created_at=datetime.now(UTC)
    )
    uid_b = uuid4()
    player_b = MMPlayer(
        player_id=uid_b,
        username=f"testplayerb_{uid_b.hex[:8]}",
        username_canonical=f"testplayerb_{uid_b.hex[:8]}".lower(),
        email=f"testb_{uid_b.hex[:8]}@example.com",
        password_hash="dummy_hash",
        wallet=1000,
        vault=0,
        created_at=datetime.now(UTC)
    )
    db_session.add_all([player_a, player_b])
    await db_session.flush()

    circle = MMCircle(
        circle_id=uuid4(),
        name=f"Bidirectional Test Circle {uuid4().hex[:8]}",
        created_by_player_id=player_a.player_id,
        member_count=2,
        created_at=datetime.now(UTC)
    )
    db_session.add(circle)
    await db_session.flush()

    member_a = MMCircleMember(
        circle_id=circle.circle_id,
        player_id=player_a.player_id,
        role="admin",
        joined_at=datetime.now(UTC)
    )
    member_b = MMCircleMember(
        circle_id=circle.circle_id,
        player_id=player_b.player_id,
        role="member",
        joined_at=datetime.now(UTC)
    )
    db_session.add_all([member_a, member_b])
    await db_session.commit()

    # Check both directions
    a_mates = await MMCircleService.get_circle_mates(db_session, player_a.player_id)
    b_mates = await MMCircleService.get_circle_mates(db_session, player_b.player_id)

    assert player_b.player_id in a_mates, "Player B should be in Player A's Circle-mates"
    assert player_a.player_id in b_mates, "Player A should be in Player B's Circle-mates"

    # Check is_circle_mate utility
    assert await MMCircleService.is_circle_mate(
        db_session, str(player_a.player_id), str(player_b.player_id)
    ), "A and B should be Circle-mates"

    assert await MMCircleService.is_circle_mate(
        db_session, str(player_b.player_id), str(player_a.player_id)
    ), "B and A should be Circle-mates (bidirectional)"


@pytest.mark.asyncio
async def test_riff_parent_bonus_suppression_independent(db_session, setup_circle_test_data):
    """Test that riff parent and author bonuses are evaluated independently."""
    data = setup_circle_test_data
    player1 = data["player1"]
    player2 = data["player2"]  # Circle-mate
    player3 = data["player3"]  # Non-Circle
    image_with_circle = data["image_with_circle"]

    # Create parent caption by player3 (non-Circle)
    parent_caption = MMCaption(
        caption_id=uuid4(),
        image_id=image_with_circle.image_id,
        text="Parent caption",
        author_player_id=player3.player_id,
        status="active",
        quality_score=0.5,
        kind="original",
        created_at=datetime.now(UTC)
    )
    db_session.add(parent_caption)
    await db_session.flush()

    # Create riff caption by player2 (Circle-mate)
    riff_caption = MMCaption(
        caption_id=uuid4(),
        image_id=image_with_circle.image_id,
        text="Riff caption",
        author_player_id=player2.player_id,
        parent_caption_id=parent_caption.caption_id,
        status="active",
        quality_score=0.5,
        kind="riff",
        created_at=datetime.now(UTC)
    )
    db_session.add(riff_caption)
    await db_session.commit()

    transaction_service = TransactionService(db_session, GameType.MM)
    vote_service = MMVoteService(db_session)

    # Simulate payout distribution
    payout_info = await vote_service._distribute_caption_payouts(
        riff_caption,
        5,  # entry_cost
        0.3,  # house_rake_vault_pct
        transaction_service,
        voter_player_id=player1.player_id
    )

    # Expected:
    # - Riff author (player2, Circle-mate): base only, NO bonus
    # - Parent author (player3, non-Circle): base + bonus
    # Base = 5 MC each
    # Bonus = 10 MC (only for parent)
    # Total gross = 5 + 0 + 5 + 10 = 20 MC

    total_gross = payout_info.get("total_gross", 0)
    author_gross = payout_info.get("author_gross", 0)
    parent_gross = payout_info.get("parent_gross", 0)

    # Riff author should get 5 MC (base only, bonus suppressed)
    assert author_gross == 5, (
        f"Expected riff author gross=5 (Circle-mate, bonus suppressed), got {author_gross}"
    )

    # Parent author should get 15 MC (base + bonus, not Circle-mate)
    assert parent_gross == 15, (
        f"Expected parent author gross=15 (non-Circle, bonus awarded), got {parent_gross}"
    )

    # Total should be 20 MC
    assert total_gross == 20, (
        f"Expected total_gross=20 (5 + 15), got {total_gross}"
    )
