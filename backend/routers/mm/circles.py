"""Circles API router for Meme Mint - Circle management."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_player
from backend.models.mm.player import MMPlayer
from backend.schemas.mm_circle import (
    CreateCircleRequest,
    CreateCircleResponse,
    CircleResponse,
    CircleListResponse,
    CircleMembersResponse,
    CircleJoinRequestsResponse,
    JoinCircleResponse,
    ApproveJoinRequestResponse,
    DenyJoinRequestResponse,
    AddMemberRequest,
    AddMemberResponse,
    RemoveMemberResponse,
    LeaveCircleResponse,
    CircleMemberResponse,
    CircleJoinRequestResponse,
)
from backend.services import GameType
from backend.services.mm.circle_service import MMCircleService

logger = logging.getLogger(__name__)

router = APIRouter()


# Use Meme Mint authentication
async def get_mm_player(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        db: AsyncSession = Depends(get_db),
):
    """Get authenticated Meme Mint player."""
    return await get_current_player(request=request, game_type=GameType.MM, authorization=authorization, db=db)


@router.post("", response_model=CreateCircleResponse, status_code=201)
async def create_circle(
        circle_request: CreateCircleRequest,
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Create a new Circle.

    The requesting player becomes the Circle admin.
    """
    try:
        circle = await MMCircleService.create_circle(
            db,
            name=circle_request.name,
            created_by_player_id=str(player.player_id),
            description=circle_request.description,
            is_public=circle_request.is_public,
        )

        # Build response with contextual fields
        circle_response = CircleResponse(
            circle_id=UUID(circle.circle_id),
            name=circle.name,
            description=circle.description,
            created_by_player_id=UUID(circle.created_by_player_id),
            created_at=circle.created_at,
            updated_at=circle.updated_at,
            member_count=circle.member_count,
            is_public=circle.is_public,
            status=circle.status,
            is_member=True,  # Creator is automatically a member
            is_admin=True,   # Creator is admin
            has_pending_request=False,
        )

        return CreateCircleResponse(
            success=True,
            circle=circle_response,
            message="Circle created successfully",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating Circle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create Circle")


@router.get("", response_model=CircleListResponse)
async def list_circles(
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
        limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
        offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """List all public Circles with membership status for the requesting player.

    Returns all active Circles ordered by creation date.
    """
    try:
        circles = await MMCircleService.list_all_circles(db)

        # Get player's Circle memberships and pending requests
        player_circles = await MMCircleService.get_player_circles(db, str(player.player_id))
        player_circle_ids = {UUID(c.circle_id) for c in player_circles}

        # Get pending join requests for this player
        pending_requests = await MMCircleService.get_pending_join_requests_for_player(db, str(player.player_id))
        pending_circle_ids = {UUID(req.circle_id) for req in pending_requests}

        # Build responses with contextual fields
        circle_responses = []
        for circle in circles[offset:offset + limit]:
            circle_id_uuid = UUID(circle.circle_id)
            is_member = circle_id_uuid in player_circle_ids

            # Check if player is admin
            is_admin = False
            if is_member:
                members = await MMCircleService.get_circle_members(db, str(circle.circle_id))
                for member in members:
                    if UUID(member.player_id) == player.player_id and member.role == "admin":
                        is_admin = True
                        break

            circle_responses.append(CircleResponse(
                circle_id=circle_id_uuid,
                name=circle.name,
                description=circle.description,
                created_by_player_id=UUID(circle.created_by_player_id),
                created_at=circle.created_at,
                updated_at=circle.updated_at,
                member_count=circle.member_count,
                is_public=circle.is_public,
                status=circle.status,
                is_member=is_member,
                is_admin=is_admin,
                has_pending_request=circle_id_uuid in pending_circle_ids,
            ))

        return CircleListResponse(
            circles=circle_responses,
            total_count=len(circles),
        )

    except Exception as e:
        logger.error(f"Error listing Circles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list Circles")


@router.get("/{circle_id}", response_model=CircleResponse)
async def get_circle(
        circle_id: UUID = Path(..., description="Circle ID"),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Get details for a specific Circle."""
    try:
        circle = await MMCircleService.get_circle_by_id(db, str(circle_id))
        if not circle:
            raise HTTPException(status_code=404, detail="Circle not found")

        # Check if player is a member
        members = await MMCircleService.get_circle_members(db, str(circle_id))
        is_member = any(UUID(m.player_id) == player.player_id for m in members)
        is_admin = any(UUID(m.player_id) == player.player_id and m.role == "admin" for m in members)

        # Check for pending join request
        pending_requests = await MMCircleService.get_pending_join_requests_for_player(db, str(player.player_id))
        has_pending_request = any(UUID(req.circle_id) == circle_id for req in pending_requests)

        return CircleResponse(
            circle_id=UUID(circle.circle_id),
            name=circle.name,
            description=circle.description,
            created_by_player_id=UUID(circle.created_by_player_id),
            created_at=circle.created_at,
            updated_at=circle.updated_at,
            member_count=circle.member_count,
            is_public=circle.is_public,
            status=circle.status,
            is_member=is_member,
            is_admin=is_admin,
            has_pending_request=has_pending_request,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Circle {circle_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get Circle details")


@router.post("/{circle_id}/join", response_model=JoinCircleResponse)
async def join_circle(
        circle_id: UUID = Path(..., description="Circle ID"),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Request to join a Circle.

    Creates a pending join request that requires admin approval.
    """
    try:
        circle = await MMCircleService.get_circle_by_id(db, str(circle_id))
        if not circle:
            raise HTTPException(status_code=404, detail="Circle not found")

        # Check if already a member
        members = await MMCircleService.get_circle_members(db, str(circle_id))
        if any(UUID(m.player_id) == player.player_id for m in members):
            return JoinCircleResponse(
                success=False,
                message="Already a member of this Circle",
            )

        # Request to join
        join_request = await MMCircleService.request_to_join(
            db,
            circle_id=str(circle_id),
            player_id=str(player.player_id),
        )

        return JoinCircleResponse(
            success=True,
            request_id=UUID(join_request.request_id),
            message="Join request submitted successfully",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error joining Circle {circle_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to join Circle")


@router.post("/{circle_id}/join-requests/{request_id}/approve", response_model=ApproveJoinRequestResponse)
async def approve_join_request(
        circle_id: UUID = Path(..., description="Circle ID"),
        request_id: UUID = Path(..., description="Join request ID"),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Approve a join request (admin only)."""
    try:
        # Check if player is admin
        members = await MMCircleService.get_circle_members(db, str(circle_id))
        is_admin = any(UUID(m.player_id) == player.player_id and m.role == "admin" for m in members)

        if not is_admin:
            raise HTTPException(status_code=403, detail="Only Circle admins can approve join requests")

        await MMCircleService.approve_join_request(
            db,
            request_id=str(request_id),
            approved_by_player_id=str(player.player_id),
        )

        return ApproveJoinRequestResponse(
            success=True,
            message="Join request approved",
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving join request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to approve join request")


@router.post("/{circle_id}/join-requests/{request_id}/deny", response_model=DenyJoinRequestResponse)
async def deny_join_request(
        circle_id: UUID = Path(..., description="Circle ID"),
        request_id: UUID = Path(..., description="Join request ID"),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Deny a join request (admin only)."""
    try:
        # Check if player is admin
        members = await MMCircleService.get_circle_members(db, str(circle_id))
        is_admin = any(UUID(m.player_id) == player.player_id and m.role == "admin" for m in members)

        if not is_admin:
            raise HTTPException(status_code=403, detail="Only Circle admins can deny join requests")

        await MMCircleService.deny_join_request(
            db,
            request_id=str(request_id),
            denied_by_player_id=str(player.player_id),
        )

        return DenyJoinRequestResponse(
            success=True,
            message="Join request denied",
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error denying join request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to deny join request")


@router.post("/{circle_id}/members", response_model=AddMemberResponse)
async def add_member(
        circle_id: UUID = Path(..., description="Circle ID"),
        add_request: AddMemberRequest = ...,
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Directly add a member to the Circle (admin only).

    Skips the join request process.
    """
    try:
        # Check if player is admin
        members = await MMCircleService.get_circle_members(db, str(circle_id))
        is_admin = any(UUID(m.player_id) == player.player_id and m.role == "admin" for m in members)

        if not is_admin:
            raise HTTPException(status_code=403, detail="Only Circle admins can add members directly")

        await MMCircleService.add_member(
            db,
            circle_id=str(circle_id),
            player_id=str(add_request.player_id),
            added_by_player_id=str(player.player_id),
        )

        return AddMemberResponse(
            success=True,
            message="Member added successfully",
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding member to Circle {circle_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add member")


@router.delete("/{circle_id}/members/{player_id}", response_model=RemoveMemberResponse)
async def remove_member(
        circle_id: UUID = Path(..., description="Circle ID"),
        player_id: UUID = Path(..., description="Player ID to remove"),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Remove a member from the Circle (admin only)."""
    try:
        # Check if player is admin
        members = await MMCircleService.get_circle_members(db, str(circle_id))
        is_admin = any(UUID(m.player_id) == player.player_id and m.role == "admin" for m in members)

        if not is_admin:
            raise HTTPException(status_code=403, detail="Only Circle admins can remove members")

        await MMCircleService.remove_member(
            db,
            circle_id=str(circle_id),
            player_id=str(player_id),
        )

        return RemoveMemberResponse(
            success=True,
            message="Member removed successfully",
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing member from Circle {circle_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove member")


@router.delete("/{circle_id}/leave", response_model=LeaveCircleResponse)
async def leave_circle(
        circle_id: UUID = Path(..., description="Circle ID"),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Leave a Circle.

    Any member can leave at any time.
    """
    try:
        await MMCircleService.remove_member(
            db,
            circle_id=str(circle_id),
            player_id=str(player.player_id),
        )

        return LeaveCircleResponse(
            success=True,
            message="Left Circle successfully",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error leaving Circle {circle_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to leave Circle")


@router.get("/{circle_id}/members", response_model=CircleMembersResponse)
async def get_circle_members(
        circle_id: UUID = Path(..., description="Circle ID"),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Get all members of a Circle."""
    try:
        circle = await MMCircleService.get_circle_by_id(db, str(circle_id))
        if not circle:
            raise HTTPException(status_code=404, detail="Circle not found")

        members = await MMCircleService.get_circle_members(db, str(circle_id))

        # Load player details for each member
        from sqlalchemy import select
        from backend.models.mm.player import MMPlayer as MMPlayerModel

        player_ids = [UUID(m.player_id) for m in members]
        stmt = select(MMPlayerModel).where(MMPlayerModel.player_id.in_(player_ids))
        result = await db.execute(stmt)
        players_map = {p.player_id: p for p in result.scalars().all()}

        member_responses = []
        for member in members:
            player_obj = players_map.get(UUID(member.player_id))
            if player_obj:
                member_responses.append(CircleMemberResponse(
                    player_id=UUID(member.player_id),
                    username=player_obj.username,
                    role=member.role,
                    joined_at=member.joined_at,
                ))

        return CircleMembersResponse(
            members=member_responses,
            total_count=len(member_responses),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Circle members for {circle_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get Circle members")


@router.get("/{circle_id}/join-requests", response_model=CircleJoinRequestsResponse)
async def get_join_requests(
        circle_id: UUID = Path(..., description="Circle ID"),
        player: MMPlayer = Depends(get_mm_player),
        db: AsyncSession = Depends(get_db),
):
    """Get pending join requests for a Circle (admin only)."""
    try:
        # Check if player is admin
        members = await MMCircleService.get_circle_members(db, str(circle_id))
        is_admin = any(UUID(m.player_id) == player.player_id and m.role == "admin" for m in members)

        if not is_admin:
            raise HTTPException(status_code=403, detail="Only Circle admins can view join requests")

        join_requests = await MMCircleService.get_pending_join_requests(db, str(circle_id))

        # Load player details for each request
        from sqlalchemy import select
        from backend.models.mm.player import MMPlayer as MMPlayerModel

        player_ids = [UUID(req.player_id) for req in join_requests]
        if player_ids:
            stmt = select(MMPlayerModel).where(MMPlayerModel.player_id.in_(player_ids))
            result = await db.execute(stmt)
            players_map = {p.player_id: p for p in result.scalars().all()}
        else:
            players_map = {}

        request_responses = []
        for req in join_requests:
            player_obj = players_map.get(UUID(req.player_id))
            if player_obj:
                request_responses.append(CircleJoinRequestResponse(
                    request_id=UUID(req.request_id),
                    player_id=UUID(req.player_id),
                    username=player_obj.username,
                    requested_at=req.requested_at,
                    status=req.status,
                    resolved_at=req.resolved_at,
                    resolved_by_player_id=UUID(req.resolved_by_player_id) if req.resolved_by_player_id else None,
                ))

        return CircleJoinRequestsResponse(
            join_requests=request_responses,
            total_count=len(request_responses),
        )

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting join requests for Circle {circle_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get join requests")
