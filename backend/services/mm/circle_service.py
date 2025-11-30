"""Service for managing MemeMint Circles (social groups)."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.mm import MMCircle, MMCircleMember, MMCircleJoinRequest, MMPlayer


class MMCircleService:
    """Service for managing MemeMint Circles"""

    @staticmethod
    async def create_circle(
        session: AsyncSession,
        player_id: str,
        name: str,
        description: Optional[str] = None
    ) -> MMCircle:
        """
        Create a new Circle with creator as admin member.

        Args:
            session: Database session
            player_id: ID of player creating the circle
            name: Circle name (must be unique, case-insensitive)
            description: Optional circle description

        Returns:
            Created MMCircle instance

        Raises:
            ValueError: If circle name already exists
        """
        # Check for duplicate name (case-insensitive)
        existing = await session.execute(
            select(MMCircle).where(func.lower(MMCircle.name) == name.lower())
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Circle '{name}' already exists")

        # Create circle
        circle = MMCircle(
            name=name,
            description=description,
            created_by_player_id=player_id,
            member_count=1,
            status="active"
        )
        session.add(circle)
        await session.flush()

        # Add creator as admin member
        member = MMCircleMember(
            circle_id=circle.circle_id,
            player_id=player_id,
            role="admin"
        )
        session.add(member)
        await session.commit()
        await session.refresh(circle)

        return circle

    @staticmethod
    async def get_circle_by_id(
        session: AsyncSession,
        circle_id: str,
        load_members: bool = False
    ) -> Optional[MMCircle]:
        """
        Get Circle by ID with optional member loading.

        Args:
            session: Database session
            circle_id: Circle ID
            load_members: Whether to eagerly load members relationship

        Returns:
            MMCircle instance or None if not found
        """
        query = select(MMCircle).where(MMCircle.circle_id == circle_id)
        if load_members:
            query = query.options(selectinload(MMCircle.members))
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_all_circles(
        session: AsyncSession,
        status: str = "active",
        limit: int = 100,
        offset: int = 0
    ) -> list[MMCircle]:
        """
        List all discoverable Circles.

        Args:
            session: Database session
            status: Circle status filter (default: "active")
            limit: Maximum number of circles to return
            offset: Number of circles to skip

        Returns:
            List of MMCircle instances
        """
        query = (
            select(MMCircle)
            .where(MMCircle.status == status)
            .order_by(MMCircle.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_player_circles(
        session: AsyncSession,
        player_id: str
    ) -> list[MMCircle]:
        """
        Get all Circles a player belongs to.

        Args:
            session: Database session
            player_id: Player ID

        Returns:
            List of MMCircle instances the player is a member of
        """
        query = (
            select(MMCircle)
            .join(MMCircleMember, MMCircle.circle_id == MMCircleMember.circle_id)
            .where(MMCircleMember.player_id == player_id)
            .where(MMCircle.status == "active")
            .order_by(MMCircleMember.joined_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_player_circle_memberships(
        session: AsyncSession,
        player_id: str,
    ) -> list[MMCircleMember]:
        """
        Get all Circle membership records for a player.

        Args:
            session: Database session
            player_id: Player ID

        Returns:
            List of MMCircleMember instances for the player
        """
        query = (
            select(MMCircleMember)
            .where(MMCircleMember.player_id == player_id)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_circle_mates(
        session: AsyncSession,
        player_id: str
    ) -> set[str]:
        """
        Get all player IDs who share ANY Circle with the given player.

        This is a critical method for Circle prioritization in game logic.
        Returns a set of player_id strings (Circle-mates) that can be used
        for efficient membership checking.

        Args:
            session: Database session
            player_id: Player ID to find circle-mates for

        Returns:
            Set of player_id strings who are circle-mates

        Example:
            >>> circle_mates = await get_circle_mates(session, "player-123")
            >>> if "player-456" in circle_mates:
            >>>     print("They're circle-mates!")
        """
        # Get all circles the player belongs to
        player_circles_query = (
            select(MMCircleMember.circle_id)
            .where(MMCircleMember.player_id == player_id)
        )
        player_circles_result = await session.execute(player_circles_query)
        player_circle_ids = [row[0] for row in player_circles_result.all()]

        if not player_circle_ids:
            return set()

        # Get all members of those circles (excluding the player themselves)
        circle_mates_query = (
            select(MMCircleMember.player_id)
            .where(MMCircleMember.circle_id.in_(player_circle_ids))
            .where(MMCircleMember.player_id != player_id)
            .distinct()
        )
        result = await session.execute(circle_mates_query)
        return {str(row[0]) for row in result.all()}

    @staticmethod
    async def is_circle_mate(
        session: AsyncSession,
        player_id: str,
        other_player_id: str
    ) -> bool:
        """
        Check if two players share any Circle.

        This is optimized for single pair checking. For bulk checking
        (e.g., checking many players), use get_circle_mates() instead.

        Args:
            session: Database session
            player_id: First player ID
            other_player_id: Second player ID

        Returns:
            True if players share at least one Circle, False otherwise
        """
        # Get circles for player_id
        player1_circles = (
            select(MMCircleMember.circle_id)
            .where(MMCircleMember.player_id == player_id)
        )

        # Check if other_player_id is in any of those circles
        query = (
            select(func.count(MMCircleMember.player_id))
            .where(
                and_(
                    MMCircleMember.player_id == other_player_id,
                    MMCircleMember.circle_id.in_(player1_circles)
                )
            )
        )
        result = await session.execute(query)
        count = result.scalar_one()
        return count > 0

    @staticmethod
    async def add_member(
        session: AsyncSession,
        circle_id: str,
        player_id: str,
        added_by_player_id: str
    ) -> MMCircleMember:
        """
        Admin adds a member directly to a Circle.

        Args:
            session: Database session
            circle_id: Circle ID
            player_id: Player ID to add
            added_by_player_id: Player ID of admin adding the member

        Returns:
            Created MMCircleMember instance

        Raises:
            PermissionError: If added_by_player_id is not an admin
            ValueError: If player is already a member
        """
        # Verify admin permission
        admin_check = await session.execute(
            select(MMCircleMember).where(
                and_(
                    MMCircleMember.circle_id == circle_id,
                    MMCircleMember.player_id == added_by_player_id,
                    MMCircleMember.role == "admin"
                )
            )
        )
        if not admin_check.scalar_one_or_none():
            raise PermissionError("Only Circle admins can add members")

        # Check if already a member
        existing = await session.execute(
            select(MMCircleMember).where(
                and_(
                    MMCircleMember.circle_id == circle_id,
                    MMCircleMember.player_id == player_id
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Player is already a member")

        # Add member
        member = MMCircleMember(
            circle_id=circle_id,
            player_id=player_id,
            role="member"
        )
        session.add(member)

        # Update member count
        circle = await MMCircleService.get_circle_by_id(session, circle_id)
        if circle:
            circle.member_count += 1
            circle.updated_at = datetime.now(timezone.utc)

        # Delete any pending join request
        await session.execute(
            delete(MMCircleJoinRequest).where(
                and_(
                    MMCircleJoinRequest.circle_id == circle_id,
                    MMCircleJoinRequest.player_id == player_id
                )
            )
        )

        await session.commit()
        return member

    @staticmethod
    async def remove_member(
        session: AsyncSession,
        circle_id: str,
        player_id: str,
        removed_by_player_id: str
    ) -> None:
        """
        Remove a member from a Circle (admin action or self-leave).

        Args:
            session: Database session
            circle_id: Circle ID
            player_id: Player ID to remove
            removed_by_player_id: Player ID performing the removal

        Raises:
            PermissionError: If remover is neither admin nor the member themselves
            ValueError: If member not found
        """
        # Check permission: admin or self
        is_self = player_id == removed_by_player_id
        is_admin = False
        if not is_self:
            admin_check = await session.execute(
                select(MMCircleMember).where(
                    and_(
                        MMCircleMember.circle_id == circle_id,
                        MMCircleMember.player_id == removed_by_player_id,
                        MMCircleMember.role == "admin"
                    )
                )
            )
            is_admin = admin_check.scalar_one_or_none() is not None

        if not is_self and not is_admin:
            raise PermissionError("Only Circle admins or the member themselves can remove membership")

        # Remove member
        result = await session.execute(
            delete(MMCircleMember).where(
                and_(
                    MMCircleMember.circle_id == circle_id,
                    MMCircleMember.player_id == player_id
                )
            )
        )

        if result.rowcount == 0:
            raise ValueError("Member not found")

        # Update member count
        circle = await MMCircleService.get_circle_by_id(session, circle_id)
        if circle:
            circle.member_count = max(0, circle.member_count - 1)
            circle.updated_at = datetime.now(timezone.utc)

        await session.commit()

    @staticmethod
    async def request_to_join(
        session: AsyncSession,
        circle_id: str,
        player_id: str
    ) -> MMCircleJoinRequest:
        """
        Player requests to join a Circle.

        Args:
            session: Database session
            circle_id: Circle ID to join
            player_id: Player ID making the request

        Returns:
            Created MMCircleJoinRequest instance

        Raises:
            ValueError: If already a member or request already pending
        """
        # Check if already a member
        existing_member = await session.execute(
            select(MMCircleMember).where(
                and_(
                    MMCircleMember.circle_id == circle_id,
                    MMCircleMember.player_id == player_id
                )
            )
        )
        if existing_member.scalar_one_or_none():
            raise ValueError("Already a member of this Circle")

        # Check for existing pending request
        existing_request = await session.execute(
            select(MMCircleJoinRequest).where(
                and_(
                    MMCircleJoinRequest.circle_id == circle_id,
                    MMCircleJoinRequest.player_id == player_id,
                    MMCircleJoinRequest.status == "pending"
                )
            )
        )
        if existing_request.scalar_one_or_none():
            raise ValueError("Join request already pending")

        # Create request
        request = MMCircleJoinRequest(
            circle_id=circle_id,
            player_id=player_id,
            status="pending"
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)

        return request

    @staticmethod
    async def approve_join_request(
        session: AsyncSession,
        request_id: str,
        admin_player_id: str
    ) -> MMCircleMember:
        """
        Admin approves a join request.

        Args:
            session: Database session
            request_id: Join request ID
            admin_player_id: Admin player ID approving the request

        Returns:
            Created MMCircleMember instance

        Raises:
            ValueError: If request not found
            PermissionError: If admin_player_id is not a Circle admin
        """
        # Get request
        request = await session.execute(
            select(MMCircleJoinRequest).where(
                MMCircleJoinRequest.request_id == request_id
            )
        )
        request = request.scalar_one_or_none()
        if not request:
            raise ValueError("Join request not found")

        # Verify admin permission
        admin_check = await session.execute(
            select(MMCircleMember).where(
                and_(
                    MMCircleMember.circle_id == request.circle_id,
                    MMCircleMember.player_id == admin_player_id,
                    MMCircleMember.role == "admin"
                )
            )
        )
        if not admin_check.scalar_one_or_none():
            raise PermissionError("Only Circle admins can approve join requests")

        # Add member
        member = MMCircleMember(
            circle_id=request.circle_id,
            player_id=request.player_id,
            role="member"
        )
        session.add(member)

        # Update request status
        request.status = "approved"
        request.resolved_at = datetime.now(timezone.utc)
        request.resolved_by_player_id = admin_player_id

        # Update member count
        circle = await MMCircleService.get_circle_by_id(session, request.circle_id)
        if circle:
            circle.member_count += 1
            circle.updated_at = datetime.now(timezone.utc)

        await session.commit()
        return member

    @staticmethod
    async def deny_join_request(
        session: AsyncSession,
        request_id: str,
        admin_player_id: str
    ) -> None:
        """
        Admin denies a join request.

        Args:
            session: Database session
            request_id: Join request ID
            admin_player_id: Admin player ID denying the request

        Raises:
            ValueError: If request not found
            PermissionError: If admin_player_id is not a Circle admin
        """
        # Get request
        request = await session.execute(
            select(MMCircleJoinRequest).where(
                MMCircleJoinRequest.request_id == request_id
            )
        )
        request = request.scalar_one_or_none()
        if not request:
            raise ValueError("Join request not found")

        # Verify admin permission
        admin_check = await session.execute(
            select(MMCircleMember).where(
                and_(
                    MMCircleMember.circle_id == request.circle_id,
                    MMCircleMember.player_id == admin_player_id,
                    MMCircleMember.role == "admin"
                )
            )
        )
        if not admin_check.scalar_one_or_none():
            raise PermissionError("Only Circle admins can deny join requests")

        # Update request status
        request.status = "denied"
        request.resolved_at = datetime.now(timezone.utc)
        request.resolved_by_player_id = admin_player_id

        await session.commit()

    @staticmethod
    async def get_pending_join_requests(
        session: AsyncSession,
        circle_id: str
    ) -> list[MMCircleJoinRequest]:
        """
        Get all pending join requests for a Circle.

        Args:
            session: Database session
            circle_id: Circle ID

        Returns:
            List of pending MMCircleJoinRequest instances with player info loaded
        """
        query = (
            select(MMCircleJoinRequest)
            .where(
                and_(
                    MMCircleJoinRequest.circle_id == circle_id,
                    MMCircleJoinRequest.status == "pending"
                )
            )
            .order_by(MMCircleJoinRequest.requested_at.asc())
            .options(selectinload(MMCircleJoinRequest.player))
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_pending_join_requests_for_player(
        session: AsyncSession,
        player_id: str
    ) -> list[MMCircleJoinRequest]:
        """
        Get all pending join requests created by a specific player.

        Args:
            session: Database session
            player_id: Player ID

        Returns:
            List of pending MMCircleJoinRequest instances for the player
        """
        query = (
            select(MMCircleJoinRequest)
            .where(
                and_(
                    MMCircleJoinRequest.player_id == player_id,
                    MMCircleJoinRequest.status == "pending"
                )
            )
            .order_by(MMCircleJoinRequest.requested_at.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_circle_members(
        session: AsyncSession,
        circle_id: str
    ) -> list[MMCircleMember]:
        """
        Get all members of a Circle with player details.

        Args:
            session: Database session
            circle_id: Circle ID

        Returns:
            List of MMCircleMember instances with player info loaded
        """
        query = (
            select(MMCircleMember)
            .where(MMCircleMember.circle_id == circle_id)
            .order_by(MMCircleMember.joined_at.desc())
            .options(selectinload(MMCircleMember.player))
        )
        result = await session.execute(query)
        return list(result.scalars().all())
