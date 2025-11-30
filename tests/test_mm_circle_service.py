"""Test MemeMint CircleService."""
import pytest
from uuid import uuid4
from datetime import datetime, UTC

from backend.services.mm.circle_service import MMCircleService
from backend.models.mm import MMCircle, MMCircleMember, MMCircleJoinRequest, MMPlayer
from backend.database import AsyncSessionLocal


@pytest.fixture
async def db_session():
    """Create a test database session."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def test_player(db_session):
    """Create a test player."""
    player = MMPlayer(
        player_id=str(uuid4()),
        username=f"testuser_{uuid4().hex[:8]}",
        username_canonical=f"testuser_{uuid4().hex[:8]}".lower(),
        email=f"test_{uuid4().hex[:8]}@example.com",
        password_hash="dummy_hash",
        wallet=500,
        vault=0
    )
    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)
    return player


@pytest.fixture
async def test_player_2(db_session):
    """Create a second test player."""
    player = MMPlayer(
        player_id=str(uuid4()),
        username=f"testuser2_{uuid4().hex[:8]}",
        username_canonical=f"testuser2_{uuid4().hex[:8]}".lower(),
        email=f"test2_{uuid4().hex[:8]}@example.com",
        password_hash="dummy_hash",
        wallet=500,
        vault=0
    )
    db_session.add(player)
    await db_session.commit()
    await db_session.refresh(player)
    return player


@pytest.mark.asyncio
async def test_create_circle(db_session, test_player):
    """Test creating a new Circle."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}",
        description="A test circle"
    )

    assert circle.circle_id is not None
    assert circle.name is not None
    assert circle.created_by_player_id == test_player.player_id
    assert circle.member_count == 1
    assert circle.status == "active"

    # Verify creator is admin member
    members = await MMCircleService.get_circle_members(db_session, circle.circle_id)
    assert len(members) == 1
    assert members[0].player_id == test_player.player_id
    assert members[0].role == "admin"


@pytest.mark.asyncio
async def test_create_circle_duplicate_name(db_session, test_player):
    """Test that duplicate circle names are rejected."""
    circle_name = f"Unique Circle {uuid4().hex[:8]}"

    # Create first circle
    await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=circle_name
    )

    # Try to create second circle with same name
    with pytest.raises(ValueError, match="already exists"):
        await MMCircleService.create_circle(
            session=db_session,
            player_id=test_player.player_id,
            name=circle_name
        )


@pytest.mark.asyncio
async def test_get_circle_by_id(db_session, test_player):
    """Test retrieving a Circle by ID."""
    created_circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    retrieved_circle = await MMCircleService.get_circle_by_id(
        session=db_session,
        circle_id=created_circle.circle_id
    )

    assert retrieved_circle is not None
    assert retrieved_circle.circle_id == created_circle.circle_id
    assert retrieved_circle.name == created_circle.name


@pytest.mark.asyncio
async def test_list_all_circles(db_session, test_player):
    """Test listing all circles."""
    # Create a few circles
    circle1 = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Circle 1 {uuid4().hex[:8]}"
    )
    circle2 = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Circle 2 {uuid4().hex[:8]}"
    )

    circles = await MMCircleService.list_all_circles(
        session=db_session,
        limit=10
    )

    assert len(circles) >= 2
    circle_ids = {c.circle_id for c in circles}
    assert circle1.circle_id in circle_ids
    assert circle2.circle_id in circle_ids


@pytest.mark.asyncio
async def test_get_player_circles(db_session, test_player, test_player_2):
    """Test getting circles a player belongs to."""
    # Create circle as player 1
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    # Add player 2 to the circle
    await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    # Get player 2's circles
    player2_circles = await MMCircleService.get_player_circles(
        session=db_session,
        player_id=test_player_2.player_id
    )

    assert len(player2_circles) == 1
    assert player2_circles[0].circle_id == circle.circle_id


@pytest.mark.asyncio
async def test_get_circle_mates(db_session, test_player, test_player_2):
    """Test getting circle-mates for a player."""
    # Create circle with both players
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    # Get circle-mates for player 1
    circle_mates = await MMCircleService.get_circle_mates(
        session=db_session,
        player_id=test_player.player_id
    )

    assert test_player_2.player_id in circle_mates
    assert test_player.player_id not in circle_mates  # Shouldn't include self


@pytest.mark.asyncio
async def test_is_circle_mate(db_session, test_player, test_player_2):
    """Test checking if two players are circle-mates."""
    # Initially not circle-mates
    is_mate = await MMCircleService.is_circle_mate(
        session=db_session,
        player_id=test_player.player_id,
        other_player_id=test_player_2.player_id
    )
    assert not is_mate

    # Create circle with both players
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    # Now they are circle-mates
    is_mate = await MMCircleService.is_circle_mate(
        session=db_session,
        player_id=test_player.player_id,
        other_player_id=test_player_2.player_id
    )
    assert is_mate


@pytest.mark.asyncio
async def test_add_member(db_session, test_player, test_player_2):
    """Test adding a member to a Circle."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    initial_count = circle.member_count

    member = await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    assert member.player_id == test_player_2.player_id
    assert member.role == "member"

    # Verify member count increased
    updated_circle = await MMCircleService.get_circle_by_id(
        session=db_session,
        circle_id=circle.circle_id
    )
    assert updated_circle.member_count == initial_count + 1


@pytest.mark.asyncio
async def test_add_member_no_permission(db_session, test_player, test_player_2):
    """Test that non-admin cannot add members."""
    # Create player 3
    player3 = MMPlayer(
        player_id=str(uuid4()),
        username=f"testuser3_{uuid4().hex[:8]}",
        username_canonical=f"testuser3_{uuid4().hex[:8]}".lower(),
        email=f"test3_{uuid4().hex[:8]}@example.com",
        password_hash="dummy_hash",
        wallet=500,
        vault=0
    )
    db_session.add(player3)
    await db_session.commit()

    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    # Add player 2 as regular member
    await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    # Try to add player 3 as player 2 (not admin)
    with pytest.raises(PermissionError, match="Only Circle admins"):
        await MMCircleService.add_member(
            session=db_session,
            circle_id=circle.circle_id,
            player_id=player3.player_id,
            added_by_player_id=test_player_2.player_id
        )


@pytest.mark.asyncio
async def test_remove_member(db_session, test_player, test_player_2):
    """Test removing a member from a Circle."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    initial_count = (await MMCircleService.get_circle_by_id(
        session=db_session,
        circle_id=circle.circle_id
    )).member_count

    # Remove member
    await MMCircleService.remove_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        removed_by_player_id=test_player.player_id
    )

    # Verify member count decreased
    updated_circle = await MMCircleService.get_circle_by_id(
        session=db_session,
        circle_id=circle.circle_id
    )
    assert updated_circle.member_count == initial_count - 1


@pytest.mark.asyncio
async def test_remove_member_self(db_session, test_player, test_player_2):
    """Test that a member can remove themselves."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    # Player 2 removes themselves
    await MMCircleService.remove_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        removed_by_player_id=test_player_2.player_id
    )

    # Verify they're no longer a circle-mate
    is_mate = await MMCircleService.is_circle_mate(
        session=db_session,
        player_id=test_player.player_id,
        other_player_id=test_player_2.player_id
    )
    assert not is_mate


@pytest.mark.asyncio
async def test_request_to_join(db_session, test_player, test_player_2):
    """Test requesting to join a Circle."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    request = await MMCircleService.request_to_join(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id
    )

    assert request.request_id is not None
    assert request.circle_id == circle.circle_id
    assert request.player_id == test_player_2.player_id
    assert request.status == "pending"


@pytest.mark.asyncio
async def test_request_to_join_already_member(db_session, test_player, test_player_2):
    """Test that members cannot request to join again."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    with pytest.raises(ValueError, match="Already a member"):
        await MMCircleService.request_to_join(
            session=db_session,
            circle_id=circle.circle_id,
            player_id=test_player_2.player_id
        )


@pytest.mark.asyncio
async def test_approve_join_request(db_session, test_player, test_player_2):
    """Test approving a join request."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    request = await MMCircleService.request_to_join(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id
    )

    # Approve request
    member = await MMCircleService.approve_join_request(
        session=db_session,
        request_id=request.request_id,
        admin_player_id=test_player.player_id
    )

    assert member.player_id == test_player_2.player_id

    # Verify they're now circle-mates
    is_mate = await MMCircleService.is_circle_mate(
        session=db_session,
        player_id=test_player.player_id,
        other_player_id=test_player_2.player_id
    )
    assert is_mate


@pytest.mark.asyncio
async def test_deny_join_request(db_session, test_player, test_player_2):
    """Test denying a join request."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    request = await MMCircleService.request_to_join(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id
    )

    # Deny request
    await MMCircleService.deny_join_request(
        session=db_session,
        request_id=request.request_id,
        admin_player_id=test_player.player_id
    )

    # Verify they're not circle-mates
    is_mate = await MMCircleService.is_circle_mate(
        session=db_session,
        player_id=test_player.player_id,
        other_player_id=test_player_2.player_id
    )
    assert not is_mate


@pytest.mark.asyncio
async def test_get_pending_join_requests(db_session, test_player, test_player_2):
    """Test getting pending join requests for a Circle."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    await MMCircleService.request_to_join(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id
    )

    requests = await MMCircleService.get_pending_join_requests(
        session=db_session,
        circle_id=circle.circle_id
    )

    assert len(requests) == 1
    assert requests[0].player_id == test_player_2.player_id
    assert requests[0].status == "pending"


@pytest.mark.asyncio
async def test_get_circle_members(db_session, test_player, test_player_2):
    """Test getting all members of a Circle."""
    circle = await MMCircleService.create_circle(
        session=db_session,
        player_id=test_player.player_id,
        name=f"Test Circle {uuid4().hex[:8]}"
    )

    await MMCircleService.add_member(
        session=db_session,
        circle_id=circle.circle_id,
        player_id=test_player_2.player_id,
        added_by_player_id=test_player.player_id
    )

    members = await MMCircleService.get_circle_members(
        session=db_session,
        circle_id=circle.circle_id
    )

    assert len(members) == 2
    member_ids = {m.player_id for m in members}
    assert test_player.player_id in member_ids
    assert test_player_2.player_id in member_ids
