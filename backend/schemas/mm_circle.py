"""Pydantic schemas for MemeMint Circles API."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


# Request schemas

class CreateCircleRequest(BaseModel):
    """Request to create a new Circle."""
    name: str = Field(..., min_length=1, max_length=100, description="Circle name")
    description: str | None = Field(None, max_length=500, description="Optional Circle description")
    is_public: bool = Field(True, description="Whether Circle is publicly discoverable")


class AddMemberRequest(BaseModel):
    """Request to directly add a member to a Circle (admin only)."""
    player_id: UUID = Field(..., description="Player ID to add as member")


# Response schemas

class CircleMemberResponse(BaseModel):
    """Response model for a Circle member."""
    player_id: UUID
    username: str
    role: str  # "admin" or "member"
    joined_at: datetime

    class Config:
        from_attributes = True


class CircleJoinRequestResponse(BaseModel):
    """Response model for a join request."""
    request_id: UUID
    player_id: UUID
    username: str
    requested_at: datetime
    status: str  # "pending", "approved", "denied"
    resolved_at: datetime | None = None
    resolved_by_player_id: UUID | None = None

    class Config:
        from_attributes = True


class CircleResponse(BaseModel):
    """Response model for Circle details."""
    circle_id: UUID
    name: str
    description: str | None
    created_by_player_id: UUID
    created_at: datetime
    updated_at: datetime
    member_count: int
    is_public: bool
    status: str  # "active", "archived"

    # Contextual fields (based on requesting player)
    is_member: bool = Field(False, description="Whether requesting player is a member")
    is_admin: bool = Field(False, description="Whether requesting player is admin")
    has_pending_request: bool = Field(False, description="Whether requesting player has pending join request")

    class Config:
        from_attributes = True


class CircleListResponse(BaseModel):
    """Response model for list of Circles."""
    circles: list[CircleResponse]
    total_count: int


class CircleMembersResponse(BaseModel):
    """Response model for Circle members list."""
    members: list[CircleMemberResponse]
    total_count: int


class CircleJoinRequestsResponse(BaseModel):
    """Response model for Circle join requests list."""
    join_requests: list[CircleJoinRequestResponse]
    total_count: int


class CreateCircleResponse(BaseModel):
    """Response after creating a Circle."""
    success: bool
    circle: CircleResponse
    message: str = "Circle created successfully"


class JoinCircleResponse(BaseModel):
    """Response after requesting to join a Circle."""
    success: bool
    request_id: UUID | None = None
    message: str


class ApproveJoinRequestResponse(BaseModel):
    """Response after approving a join request."""
    success: bool
    message: str = "Join request approved"


class DenyJoinRequestResponse(BaseModel):
    """Response after denying a join request."""
    success: bool
    message: str = "Join request denied"


class AddMemberResponse(BaseModel):
    """Response after adding a member directly."""
    success: bool
    message: str = "Member added successfully"


class RemoveMemberResponse(BaseModel):
    """Response after removing a member."""
    success: bool
    message: str = "Member removed successfully"


class LeaveCircleResponse(BaseModel):
    """Response after leaving a Circle."""
    success: bool
    message: str = "Left Circle successfully"
