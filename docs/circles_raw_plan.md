# MemeMint Circles Feature - Implementation Plan

**Date:** 2025-11-28  
**Status:** Planning Phase  
**Document Version:** 1.0

---

## Table of Contents
1. [Overview](#overview)
2. [Database Schema Design](#database-schema-design)
3. [Backend Implementation](#backend-implementation)
4. [Frontend Implementation](#frontend-implementation)
5. [Migration Strategy](#migration-strategy)
6. [Testing Considerations](#testing-considerations)
7. [Implementation Phases](#implementation-phases)
8. [Critical Files Summary](#critical-files-summary)

---

## Overview

This plan details the implementation of the "Circles" feature for MemeMint - persistent social groups that influence content prioritization during gameplay. Key goals:

- **Image Prioritization**: Prefer images with Circle-mate captions
- **Caption Prioritization**: Fill vote rounds with Circle captions first (up to 5)
- **System Bonus Suppression**: Remove 3x writer bonus when voting for Circle-mates (prevents farming)
- **Circle Management**: Create/join/leave circles, admin controls, discovery

**Core Principle**: Circles create a "room with people you know" feeling without requiring real-time coordination.

---

## Database Schema Design

### 2.1 New Tables

#### Table: `mm_circles`
Stores circle definitions.

```sql
CREATE TABLE mm_circles (
    circle_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_by_player_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    
    CONSTRAINT fk_mm_circles_created_by 
        FOREIGN KEY (created_by_player_id) 
        REFERENCES mm_players(player_id) 
        ON DELETE SET NULL,
    
    CONSTRAINT uq_mm_circles_name UNIQUE (name)
);

CREATE INDEX ix_mm_circles_status ON mm_circles(status);
CREATE INDEX ix_mm_circles_created_by ON mm_circles(created_by_player_id);
CREATE INDEX ix_mm_circles_name ON mm_circles(name);
```

**Columns:**
- `circle_id`: Primary key
- `name`: Unique circle name (100 chars max)
- `description`: Optional description (TEXT)
- `created_by_player_id`: Admin/creator (SET NULL on delete to preserve circle)
- `created_at`: Creation timestamp
- `updated_at`: Last modification timestamp
- `status`: 'active' or 'deleted' (soft delete support)

**Indexes:**
- Status for filtering active circles
- Creator for admin queries
- Name for search/uniqueness

---

#### Table: `mm_circle_members`
Tracks circle membership (many-to-many).

```sql
CREATE TABLE mm_circle_members (
    membership_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    circle_id UUID NOT NULL,
    player_id UUID NOT NULL,
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    invited_by_player_id UUID,
    
    CONSTRAINT fk_mm_circle_members_circle 
        FOREIGN KEY (circle_id) 
        REFERENCES mm_circles(circle_id) 
        ON DELETE CASCADE,
    
    CONSTRAINT fk_mm_circle_members_player 
        FOREIGN KEY (player_id) 
        REFERENCES mm_players(player_id) 
        ON DELETE CASCADE,
    
    CONSTRAINT fk_mm_circle_members_invited_by 
        FOREIGN KEY (invited_by_player_id) 
        REFERENCES mm_players(player_id) 
        ON DELETE SET NULL,
    
    CONSTRAINT uq_mm_circle_members_circle_player 
        UNIQUE (circle_id, player_id)
);

CREATE INDEX ix_mm_circle_members_circle ON mm_circle_members(circle_id);
CREATE INDEX ix_mm_circle_members_player ON mm_circle_members(player_id);
CREATE INDEX ix_mm_circle_members_joined_at ON mm_circle_members(joined_at);
```

**Columns:**
- `membership_id`: Primary key
- `circle_id`: Circle reference (CASCADE delete)
- `player_id`: Player reference (CASCADE delete)
- `joined_at`: Membership start timestamp
- `invited_by_player_id`: Who added them (NULL if self-requested and approved)

**Indexes:**
- Circle lookup (for member lists)
- Player lookup (for "my circles")
- Joined timestamp (for sorting)

**Key constraint:** Unique (circle_id, player_id) prevents duplicate memberships

---

#### Table: `mm_circle_join_requests`
Pending join requests for circles.

```sql
CREATE TABLE mm_circle_join_requests (
    request_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    circle_id UUID NOT NULL,
    player_id UUID NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    reviewed_by_player_id UUID,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT fk_mm_circle_join_requests_circle 
        FOREIGN KEY (circle_id) 
        REFERENCES mm_circles(circle_id) 
        ON DELETE CASCADE,
    
    CONSTRAINT fk_mm_circle_join_requests_player 
        FOREIGN KEY (player_id) 
        REFERENCES mm_players(player_id) 
        ON DELETE CASCADE,
    
    CONSTRAINT fk_mm_circle_join_requests_reviewed_by 
        FOREIGN KEY (reviewed_by_player_id) 
        REFERENCES mm_players(player_id) 
        ON DELETE SET NULL,
    
    CONSTRAINT uq_mm_circle_join_requests_circle_player 
        UNIQUE (circle_id, player_id)
);

CREATE INDEX ix_mm_circle_join_requests_circle_status 
    ON mm_circle_join_requests(circle_id, status);
CREATE INDEX ix_mm_circle_join_requests_player 
    ON mm_circle_join_requests(player_id);
```

**Columns:**
- `request_id`: Primary key
- `circle_id`: Target circle (CASCADE delete)
- `player_id`: Requesting player (CASCADE delete)
- `requested_at`: Request timestamp
- `status`: 'pending', 'approved', 'denied'
- `reviewed_by_player_id`: Admin who reviewed (optional)
- `reviewed_at`: Review timestamp

**Indexes:**
- Circle + status for admin review panel
- Player for "my requests"

**Key constraint:** Unique (circle_id, player_id) - one active request per player-circle

---

### 2.2 Query Patterns

#### Q1: Get all Circle-mates for player P
```sql
-- Get all players who share ANY circle with player P
SELECT DISTINCT cm2.player_id
FROM mm_circle_members cm1
JOIN mm_circle_members cm2 
    ON cm1.circle_id = cm2.circle_id 
    AND cm2.player_id != :player_id
WHERE cm1.player_id = :player_id
```

**Performance**: With proper indexes on `mm_circle_members(player_id)` and `mm_circle_members(circle_id)`, this query is O(C*M) where C = circles player is in, M = avg members per circle. Expected to be fast (<10ms) for typical use.

---

#### Q2: Get images with Circle-mate captions (Image Prioritization)
```sql
-- Find active images that have at least one eligible caption from a Circle-mate
SELECT DISTINCT i.image_id, COUNT(DISTINCT c.caption_id) as circle_caption_count
FROM mm_images i
JOIN mm_captions c ON c.image_id = i.image_id
WHERE i.status = 'active'
  AND c.status = 'active'
  AND c.author_player_id IN (
      -- Circle-mates subquery
      SELECT DISTINCT cm2.player_id
      FROM mm_circle_members cm1
      JOIN mm_circle_members cm2 ON cm1.circle_id = cm2.circle_id
      WHERE cm1.player_id = :player_id AND cm2.player_id != :player_id
  )
  AND c.author_player_id != :player_id
  AND NOT EXISTS (
      SELECT 1 FROM mm_caption_seen cs
      WHERE cs.caption_id = c.caption_id AND cs.player_id = :player_id
  )
GROUP BY i.image_id
HAVING COUNT(DISTINCT c.caption_id) >= :min_captions_per_round
```

**Note**: This can be optimized by materializing Circle-mate relationships in application code once, then using an IN clause.

---

#### Q3: Partition captions into Circle vs Global pools
```sql
-- Get eligible captions for an image, tagged by Circle membership
SELECT 
    c.*,
    CASE WHEN cm_check.player_id IS NOT NULL THEN true ELSE false END as is_circle_mate
FROM mm_captions c
LEFT JOIN (
    -- Circle-mates subquery
    SELECT DISTINCT cm2.player_id
    FROM mm_circle_members cm1
    JOIN mm_circle_members cm2 ON cm1.circle_id = cm2.circle_id
    WHERE cm1.player_id = :player_id AND cm2.player_id != :player_id
) cm_check ON c.author_player_id = cm_check.player_id
WHERE c.image_id = :image_id
  AND c.status = 'active'
  AND (c.author_player_id IS NULL OR c.author_player_id != :player_id)
  AND NOT EXISTS (
      SELECT 1 FROM mm_caption_seen cs
      WHERE cs.caption_id = c.caption_id AND cs.player_id = :player_id
  )
ORDER BY c.quality_score DESC
```

Application code then partitions results into Circle vs Global, applies weighted random selection within each pool.

---

#### Q4: Check if caption author is Circle-mate (for bonus suppression)
```sql
-- Check if author_id is a Circle-mate of voter_id
SELECT EXISTS (
    SELECT 1
    FROM mm_circle_members cm1
    JOIN mm_circle_members cm2 ON cm1.circle_id = cm2.circle_id
    WHERE cm1.player_id = :voter_id
      AND cm2.player_id = :author_id
) as is_circle_mate
```

---

### 2.3 Performance Considerations

- **Circle-mate lookup** is the hottest query. Cache results per request in application memory.
- Use **prepared statements** for repeated queries
- **Composite indexes** on (circle_id, player_id) are critical
- Consider adding a **materialized view** for Circle-mates if performance degrades (future optimization)

---

## Backend Implementation

### 3.1 Models

#### File: `/backend/models/mm/circle.py`

```python
"""Meme Mint circle model."""
import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMCircle(Base):
    """Represents a Circle - a persistent social group."""

    __tablename__ = "mm_circles"

    circle_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_by_player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
    status = Column(String(20), default="active", nullable=False)

    # Relationships
    created_by = relationship("MMPlayer", foreign_keys=[created_by_player_id])
    members = relationship("MMCircleMember", back_populates="circle", cascade="all, delete-orphan")
    join_requests = relationship("MMCircleJoinRequest", back_populates="circle", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_mm_circles_status", "status"),
        Index("ix_mm_circles_created_by", "created_by_player_id"),
        Index("ix_mm_circles_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<MMCircle(circle_id={self.circle_id}, name={self.name})>"
```

---

#### File: `/backend/models/mm/circle_member.py`

```python
"""Meme Mint circle membership model."""
import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMCircleMember(Base):
    """Represents membership in a Circle."""

    __tablename__ = "mm_circle_members"

    membership_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    circle_id = get_uuid_column(
        ForeignKey("mm_circles.circle_id", ondelete="CASCADE"), nullable=False
    )
    player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"), nullable=False
    )
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    invited_by_player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    circle = relationship("MMCircle", back_populates="members")
    player = relationship("MMPlayer", foreign_keys=[player_id])
    invited_by = relationship("MMPlayer", foreign_keys=[invited_by_player_id])

    __table_args__ = (
        UniqueConstraint("circle_id", "player_id", name="uq_mm_circle_members_circle_player"),
        Index("ix_mm_circle_members_circle", "circle_id"),
        Index("ix_mm_circle_members_player", "player_id"),
        Index("ix_mm_circle_members_joined_at", "joined_at"),
    )

    def __repr__(self) -> str:
        return f"<MMCircleMember(circle_id={self.circle_id}, player_id={self.player_id})>"
```

---

#### File: `/backend/models/mm/circle_join_request.py`

```python
"""Meme Mint circle join request model."""
import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class MMCircleJoinRequest(Base):
    """Represents a pending join request for a Circle."""

    __tablename__ = "mm_circle_join_requests"

    request_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    circle_id = get_uuid_column(
        ForeignKey("mm_circles.circle_id", ondelete="CASCADE"), nullable=False
    )
    player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"), nullable=False
    )
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    reviewed_by_player_id = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    circle = relationship("MMCircle", back_populates="join_requests")
    player = relationship("MMPlayer", foreign_keys=[player_id])
    reviewed_by = relationship("MMPlayer", foreign_keys=[reviewed_by_player_id])

    __table_args__ = (
        UniqueConstraint("circle_id", "player_id", name="uq_mm_circle_join_requests_circle_player"),
        Index("ix_mm_circle_join_requests_circle_status", "circle_id", "status"),
        Index("ix_mm_circle_join_requests_player", "player_id"),
    )

    def __repr__(self) -> str:
        return f"<MMCircleJoinRequest(request_id={self.request_id}, status={self.status})>"
```

---

#### Update: `/backend/models/mm/__init__.py`

Add imports:
```python
from .circle import MMCircle
from .circle_member import MMCircleMember
from .circle_join_request import MMCircleJoinRequest
```

---

### 3.2 Pydantic Schemas

#### File: `/backend/schemas/mm_circle.py`

```python
"""Meme Mint Circle-related Pydantic schemas."""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID
from backend.schemas.base import BaseSchema
import re


# Circle schemas

class CircleCreate(BaseModel):
    """Create a new Circle."""
    name: str = Field(..., min_length=3, max_length=100)
    description: str | None = Field(None, max_length=500)

    @field_validator('name')
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        """Validate circle name."""
        v = v.strip()
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError('Circle name can only contain letters, numbers, spaces, hyphens, and underscores')
        return v


class CircleUpdate(BaseModel):
    """Update Circle details."""
    description: str | None = Field(None, max_length=500)


class CircleMemberInfo(BaseSchema):
    """Circle member information."""
    player_id: UUID
    username: str
    joined_at: datetime
    is_admin: bool  # True if this player is the creator


class CircleDetail(BaseSchema):
    """Detailed Circle information."""
    circle_id: UUID
    name: str
    description: str | None
    created_by_player_id: UUID | None
    created_at: datetime
    updated_at: datetime
    member_count: int
    members: list[CircleMemberInfo]
    is_member: bool  # Whether requesting player is a member
    is_admin: bool   # Whether requesting player is the admin
    has_pending_request: bool  # Whether requesting player has a pending join request


class CircleSummary(BaseSchema):
    """Summary information for Circle discovery."""
    circle_id: UUID
    name: str
    description: str | None
    member_count: int
    created_at: datetime
    is_member: bool
    is_admin: bool
    has_pending_request: bool


class CircleListResponse(BaseSchema):
    """List of circles."""
    circles: list[CircleSummary]


# Join request schemas

class JoinRequestCreate(BaseModel):
    """Request to join a Circle."""
    circle_id: UUID


class JoinRequestResponse(BaseSchema):
    """Join request response."""
    request_id: UUID
    circle_id: UUID
    player_id: UUID
    requested_at: datetime
    status: str


class ApproveJoinRequest(BaseModel):
    """Approve/deny a join request."""
    request_id: UUID
    approved: bool  # True to approve, False to deny


class AddMemberRequest(BaseModel):
    """Admin adds a member directly."""
    username: str  # Username to add


# Management responses

class CircleActionResponse(BaseSchema):
    """Generic Circle action response."""
    success: bool
    message: str
    circle_id: UUID | None = None
```

---

### 3.3 Service Layer

#### File: `/backend/services/mm/circle_service.py`

```python
"""Service for managing MemeMint Circles."""

import logging
from datetime import datetime, UTC
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.mm.circle import MMCircle
from backend.models.mm.circle_member import MMCircleMember
from backend.models.mm.circle_join_request import MMCircleJoinRequest
from backend.models.mm.player import MMPlayer

logger = logging.getLogger(__name__)


class MMCircleService:
    """Service for Circle management operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_circle(
        self,
        name: str,
        creator_id: UUID,
        description: str | None = None
    ) -> MMCircle:
        """Create a new Circle.

        The creator becomes the first member and admin.

        Args:
            name: Circle name (unique)
            creator_id: Player creating the circle
            description: Optional description

        Returns:
            Created Circle

        Raises:
            ValueError: If circle name already exists
        """
        # Check if name exists
        stmt = select(MMCircle).where(MMCircle.name == name)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError(f"Circle name '{name}' already exists")

        # Create circle
        circle = MMCircle(
            name=name,
            description=description,
            created_by_player_id=creator_id
        )
        self.db.add(circle)
        await self.db.flush([circle])

        # Add creator as first member
        member = MMCircleMember(
            circle_id=circle.circle_id,
            player_id=creator_id
        )
        self.db.add(member)
        await self.db.commit()

        logger.info(f"Circle '{name}' created by player {creator_id}")
        return circle

    async def get_circle(self, circle_id: UUID) -> Optional[MMCircle]:
        """Get a Circle by ID."""
        stmt = select(MMCircle).where(
            MMCircle.circle_id == circle_id,
            MMCircle.status == 'active'
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_circle_with_members(self, circle_id: UUID) -> Optional[MMCircle]:
        """Get Circle with members loaded."""
        stmt = (
            select(MMCircle)
            .options(selectinload(MMCircle.members))
            .where(
                MMCircle.circle_id == circle_id,
                MMCircle.status == 'active'
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all_circles(self) -> list[MMCircle]:
        """List all active circles."""
        stmt = select(MMCircle).where(MMCircle.status == 'active')
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_player_circles(self, player_id: UUID) -> list[MMCircle]:
        """List all circles a player is a member of."""
        stmt = (
            select(MMCircle)
            .join(MMCircleMember)
            .where(
                MMCircleMember.player_id == player_id,
                MMCircle.status == 'active'
            )
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_member(
        self,
        circle_id: UUID,
        player_id: UUID,
        invited_by_id: UUID
    ) -> MMCircleMember:
        """Add a member to a Circle.

        Args:
            circle_id: Circle to add to
            player_id: Player to add
            invited_by_id: Player performing the add (must be admin)

        Returns:
            Created membership

        Raises:
            ValueError: If player is already a member or circle doesn't exist
            PermissionError: If inviter is not admin
        """
        # Verify circle exists and inviter is admin
        circle = await self.get_circle(circle_id)
        if not circle:
            raise ValueError("Circle not found")

        if circle.created_by_player_id != invited_by_id:
            raise PermissionError("Only circle admin can add members")

        # Check if already a member
        stmt = select(MMCircleMember).where(
            MMCircleMember.circle_id == circle_id,
            MMCircleMember.player_id == player_id
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("Player is already a member")

        # Add member
        member = MMCircleMember(
            circle_id=circle_id,
            player_id=player_id,
            invited_by_player_id=invited_by_id
        )
        self.db.add(member)

        # Delete any pending join request
        await self._delete_join_request(circle_id, player_id)

        await self.db.commit()
        logger.info(f"Player {player_id} added to Circle {circle_id} by {invited_by_id}")
        return member

    async def remove_member(
        self,
        circle_id: UUID,
        player_id: UUID,
        removed_by_id: UUID
    ) -> None:
        """Remove a member from a Circle.

        Args:
            circle_id: Circle to remove from
            player_id: Player to remove
            removed_by_id: Player performing removal (must be admin or self)

        Raises:
            ValueError: If membership doesn't exist
            PermissionError: If remover lacks permission
        """
        circle = await self.get_circle(circle_id)
        if not circle:
            raise ValueError("Circle not found")

        # Admin can remove anyone, or player can remove themselves
        is_admin = circle.created_by_player_id == removed_by_id
        is_self = player_id == removed_by_id

        if not (is_admin or is_self):
            raise PermissionError("Only admin or self can remove membership")

        # Find and delete membership
        stmt = select(MMCircleMember).where(
            MMCircleMember.circle_id == circle_id,
            MMCircleMember.player_id == player_id
        )
        result = await self.db.execute(stmt)
        member = result.scalar_one_or_none()

        if not member:
            raise ValueError("Player is not a member of this circle")

        await self.db.delete(member)
        await self.db.commit()

        logger.info(f"Player {player_id} removed from Circle {circle_id}")

    async def request_to_join(self, circle_id: UUID, player_id: UUID) -> MMCircleJoinRequest:
        """Create a join request for a Circle.

        Args:
            circle_id: Circle to join
            player_id: Player requesting to join

        Returns:
            Created join request

        Raises:
            ValueError: If already a member or request exists
        """
        # Check if already a member
        stmt = select(MMCircleMember).where(
            MMCircleMember.circle_id == circle_id,
            MMCircleMember.player_id == player_id
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("Already a member of this circle")

        # Check for existing pending request
        stmt = select(MMCircleJoinRequest).where(
            MMCircleJoinRequest.circle_id == circle_id,
            MMCircleJoinRequest.player_id == player_id,
            MMCircleJoinRequest.status == 'pending'
        )
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("Join request already pending")

        # Create request
        request = MMCircleJoinRequest(
            circle_id=circle_id,
            player_id=player_id
        )
        self.db.add(request)
        await self.db.commit()

        logger.info(f"Join request created: player {player_id} -> Circle {circle_id}")
        return request

    async def approve_join_request(
        self,
        request_id: UUID,
        reviewer_id: UUID,
        approved: bool
    ) -> None:
        """Approve or deny a join request.

        Args:
            request_id: Join request ID
            reviewer_id: Player reviewing (must be admin)
            approved: True to approve, False to deny

        Raises:
            ValueError: If request doesn't exist or not pending
            PermissionError: If reviewer is not admin
        """
        # Get request
        stmt = select(MMCircleJoinRequest).where(
            MMCircleJoinRequest.request_id == request_id
        )
        result = await self.db.execute(stmt)
        request = result.scalar_one_or_none()

        if not request:
            raise ValueError("Join request not found")

        if request.status != 'pending':
            raise ValueError("Join request already processed")

        # Verify reviewer is admin
        circle = await self.get_circle(request.circle_id)
        if not circle or circle.created_by_player_id != reviewer_id:
            raise PermissionError("Only circle admin can approve requests")

        # Update request
        request.status = 'approved' if approved else 'denied'
        request.reviewed_by_player_id = reviewer_id
        request.reviewed_at = datetime.now(UTC)

        # If approved, add member
        if approved:
            member = MMCircleMember(
                circle_id=request.circle_id,
                player_id=request.player_id
            )
            self.db.add(member)

        await self.db.commit()
        logger.info(f"Join request {request_id} {'approved' if approved else 'denied'} by {reviewer_id}")

    async def get_pending_requests_for_circle(self, circle_id: UUID) -> list[MMCircleJoinRequest]:
        """Get all pending join requests for a Circle."""
        stmt = (
            select(MMCircleJoinRequest)
            .where(
                MMCircleJoinRequest.circle_id == circle_id,
                MMCircleJoinRequest.status == 'pending'
            )
            .order_by(MMCircleJoinRequest.requested_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _delete_join_request(self, circle_id: UUID, player_id: UUID) -> None:
        """Delete any join request for a player-circle pair (internal helper)."""
        stmt = select(MMCircleJoinRequest).where(
            MMCircleJoinRequest.circle_id == circle_id,
            MMCircleJoinRequest.player_id == player_id
        )
        result = await self.db.execute(stmt)
        request = result.scalar_one_or_none()
        if request:
            await self.db.delete(request)

    async def get_circle_mates(self, player_id: UUID) -> set[UUID]:
        """Get all Circle-mates for a player.

        Returns set of player IDs who share any Circle with the given player.
        Result EXCLUDES the player themselves.

        This is cached per request in the calling code for performance.
        """
        stmt = (
            select(MMCircleMember.player_id)
            .distinct()
            .join(
                MMCircleMember.alias('cm2'),
                MMCircleMember.circle_id == MMCircleMember.alias('cm2').circle_id
            )
            .where(
                MMCircleMember.alias('cm2').player_id == player_id,
                MMCircleMember.player_id != player_id
            )
        )
        result = await self.db.execute(stmt)
        return set(result.scalars().all())

    async def is_circle_mate(self, player1_id: UUID, player2_id: UUID) -> bool:
        """Check if two players are Circle-mates (share any Circle)."""
        stmt = (
            select(
                exists(
                    select(1)
                    .select_from(MMCircleMember.alias('cm1'))
                    .join(
                        MMCircleMember.alias('cm2'),
                        MMCircleMember.alias('cm1').circle_id == MMCircleMember.alias('cm2').circle_id
                    )
                    .where(
                        MMCircleMember.alias('cm1').player_id == player1_id,
                        MMCircleMember.alias('cm2').player_id == player2_id
                    )
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar()

    async def get_member_count(self, circle_id: UUID) -> int:
        """Get member count for a Circle."""
        stmt = select(func.count()).select_from(MMCircleMember).where(
            MMCircleMember.circle_id == circle_id
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0
```

---

### 3.4 Game Logic Modifications

#### Update: `/backend/services/mm/game_service.py`

**Key Changes:**
1. Modify `_select_image_for_vote()` to prioritize images with Circle-mate captions
2. Modify `_select_captions_for_round()` to partition Circle vs Global and fill Circle-first

**New helper method:**
```python
async def _get_circle_mate_ids(self, player_id: UUID) -> set[UUID]:
    """Get Circle-mates for a player (cached per request)."""
    from backend.services.mm.circle_service import MMCircleService
    circle_service = MMCircleService(self.db)
    return await circle_service.get_circle_mates(player_id)
```

**Modified `_select_image_for_vote()`:**
```python
async def _select_image_for_vote(
    self,
    player_id: UUID,
    captions_per_round: int
) -> Optional[MMImage]:
    """Select an image with Circle prioritization.
    
    1. Try to find images with Circle-mate captions first
    2. Fall back to global selection if no Circle content
    """
    # Get Circle-mates
    circle_mate_ids = await self._get_circle_mate_ids(player_id)
    
    if circle_mate_ids:
        # Try Circle-participating images first
        image = await self._select_circle_participating_image(
            player_id, captions_per_round, circle_mate_ids
        )
        if image:
            logger.debug(f"Selected Circle-participating image {image.image_id} for player {player_id}")
            return image
    
    # Fall back to global selection
    return await self._select_global_image(player_id, captions_per_round)


async def _select_circle_participating_image(
    self,
    player_id: UUID,
    captions_per_round: int,
    circle_mate_ids: set[UUID]
) -> Optional[MMImage]:
    """Select image that has Circle-mate captions."""
    # Subquery: count unseen Circle captions per image
    unseen_circle_captions_subq = (
        select(
            MMCaption.image_id,
            func.count(MMCaption.caption_id).label('circle_caption_count')
        )
        .outerjoin(
            MMCaptionSeen,
            and_(
                MMCaptionSeen.caption_id == MMCaption.caption_id,
                MMCaptionSeen.player_id == player_id
            )
        )
        .where(
            MMCaption.status == 'active',
            MMCaption.author_player_id.in_(circle_mate_ids),
            MMCaptionSeen.player_id.is_(None)
        )
        .group_by(MMCaption.image_id)
        .having(func.count(MMCaption.caption_id) >= 1)  # At least 1 Circle caption
        .subquery()
    )
    
    # Also need total eligible caption count >= captions_per_round
    total_captions_subq = (
        select(
            MMCaption.image_id,
            func.count(MMCaption.caption_id).label('total_count')
        )
        .outerjoin(
            MMCaptionSeen,
            and_(
                MMCaptionSeen.caption_id == MMCaption.caption_id,
                MMCaptionSeen.player_id == player_id
            )
        )
        .where(
            MMCaption.status == 'active',
            or_(MMCaption.author_player_id.is_(None), MMCaption.author_player_id != player_id),
            MMCaptionSeen.player_id.is_(None)
        )
        .group_by(MMCaption.image_id)
        .having(func.count(MMCaption.caption_id) >= captions_per_round)
        .subquery()
    )
    
    # Select from images that meet both criteria
    stmt = (
        select(MMImage)
        .join(unseen_circle_captions_subq, unseen_circle_captions_subq.c.image_id == MMImage.image_id)
        .join(total_captions_subq, total_captions_subq.c.image_id == MMImage.image_id)
        .where(MMImage.status == 'active')
        .order_by(func.random())
        .limit(10)
    )
    
    result = await self.db.execute(stmt)
    images = result.scalars().all()
    
    if not images:
        return None
    
    return random.choice(images)


async def _select_global_image(
    self,
    player_id: UUID,
    captions_per_round: int
) -> Optional[MMImage]:
    """Original global image selection (no Circle filtering)."""
    # This is the current logic from _select_image_for_vote
    unseen_captions_subq = (
        select(
            MMCaption.image_id,
            func.count(MMCaption.caption_id).label('unseen_count')
        )
        .outerjoin(
            MMCaptionSeen,
            and_(
                MMCaptionSeen.caption_id == MMCaption.caption_id,
                MMCaptionSeen.player_id == player_id
            )
        )
        .where(
            MMCaption.status == 'active',
            or_(MMCaption.author_player_id.is_(None), MMCaption.author_player_id != player_id),
            MMCaptionSeen.player_id.is_(None)
        )
        .group_by(MMCaption.image_id)
        .having(func.count(MMCaption.caption_id) >= captions_per_round)
        .subquery()
    )
    
    stmt = (
        select(MMImage)
        .join(unseen_captions_subq, unseen_captions_subq.c.image_id == MMImage.image_id)
        .where(MMImage.status == 'active')
        .order_by(func.random())
        .limit(10)
    )
    
    result = await self.db.execute(stmt)
    images = result.scalars().all()
    
    if not images:
        return None
    
    return random.choice(images)
```

**Modified `_select_captions_for_round()`:**
```python
async def _select_captions_for_round(
    self,
    image_id: UUID,
    player_id: UUID,
    count: int
) -> list[MMCaption]:
    """Select captions with Circle-first prioritization.
    
    Strategy:
    - If >= count Circle captions: select all from Circle pool
    - If 0 < k < count Circle captions: select all k Circle + (count-k) Global
    - If 0 Circle captions: select all from Global pool
    
    Within each pool, use quality_score weighted random.
    """
    # Get Circle-mates
    circle_mate_ids = await self._get_circle_mate_ids(player_id)
    
    # Get all eligible captions
    stmt = (
        select(MMCaption)
        .outerjoin(
            MMCaptionSeen,
            and_(
                MMCaptionSeen.caption_id == MMCaption.caption_id,
                MMCaptionSeen.player_id == player_id
            )
        )
        .where(
            MMCaption.image_id == image_id,
            MMCaption.status == 'active',
            or_(MMCaption.author_player_id.is_(None), MMCaption.author_player_id != player_id),
            MMCaptionSeen.player_id.is_(None)
        )
    )
    
    result = await self.db.execute(stmt)
    all_candidates = result.scalars().all()
    
    # Partition into Circle vs Global
    circle_captions = [
        c for c in all_candidates 
        if c.author_player_id and c.author_player_id in circle_mate_ids
    ]
    global_captions = [
        c for c in all_candidates 
        if not (c.author_player_id and c.author_player_id in circle_mate_ids)
    ]
    
    k = len(circle_captions)
    
    logger.debug(
        f"Caption partition for image {image_id}: "
        f"{k} Circle captions, {len(global_captions)} Global captions"
    )
    
    # Apply selection strategy
    if k >= count:
        # All from Circle pool
        return self._weighted_random_select(circle_captions, count)
    elif k > 0:
        # All Circle + fill with Global
        selected = list(circle_captions)
        global_count = count - k
        if len(global_captions) >= global_count:
            selected.extend(self._weighted_random_select(global_captions, global_count))
        else:
            # Not enough captions total
            selected.extend(global_captions)
        
        if len(selected) < count:
            raise NoContentAvailableError(
                f"Not enough unseen captions for image {image_id}. "
                f"Need {count}, have {len(selected)}"
            )
        return selected
    else:
        # All from Global pool
        if len(global_captions) < count:
            raise NoContentAvailableError(
                f"Not enough unseen captions for image {image_id}. "
                f"Need {count}, have {len(global_captions)}"
            )
        return self._weighted_random_select(global_captions, count)


def _weighted_random_select(self, candidates: list[MMCaption], count: int) -> list[MMCaption]:
    """Select captions using quality_score weighted random (existing logic)."""
    weights = [caption.quality_score or 0 for caption in candidates]
    selected: list[MMCaption] = []
    available = list(candidates)
    
    for _ in range(count):
        if not available:
            break
        
        total_weight = sum(weights)
        if total_weight <= 0:
            idx = random.randrange(len(available))
        else:
            pick = random.uniform(0, total_weight)
            cumulative = 0.0
            idx = 0
            for i, w in enumerate(weights):
                cumulative += w
                if pick <= cumulative:
                    idx = i
                    break
        
        selected.append(available.pop(idx))
        weights.pop(idx)
    
    return selected
```

---

#### Update: `/backend/services/mm/vote_service.py`

**System Bonus Suppression**: Modify `_distribute_caption_payouts()` to suppress writer bonus for Circle-mates.

**Add helper method:**
```python
async def _is_circle_mate(self, player1_id: UUID, player2_id: UUID) -> bool:
    """Check if two players are Circle-mates."""
    from backend.services.mm.circle_service import MMCircleService
    circle_service = MMCircleService(self.db)
    return await circle_service.is_circle_mate(player1_id, player2_id)
```

**Modified `_distribute_caption_payouts()`:**
```python
async def _distribute_caption_payouts(
    self,
    caption: MMCaption,
    entry_cost: int,
    house_rake_vault_pct: float,
    transaction_service: TransactionService,
    voter_id: UUID  # NEW PARAMETER
) -> dict:
    """Distribute payouts with Circle-mate bonus suppression.
    
    Per MM_CIRCLES.md Section 6:
    - If voter and author are Circle-mates, suppress system writer bonus (3x)
    - Base payout from entry_cost is always given
    - Evaluated per earning author (riff vs parent can differ)
    """
    if not caption.author_player_id:
        logger.error(f"Caption {caption.caption_id} has no author_player_id")
        raise ValueError("Invalid caption: missing author_player_id")
    
    # Check Circle relationship for author
    author_is_circle_mate = await self._is_circle_mate(voter_id, caption.author_player_id)
    
    # Get writer bonus multiplier (default 3)
    writer_bonus_multiplier = await self.config_service.get_config_value(
        "mm_writer_bonus_multiplier", default=3
    )
    
    # Calculate payouts
    base_payout = entry_cost
    
    # Suppress system bonus if Circle-mate
    if author_is_circle_mate:
        writer_bonus = 0
        logger.info(
            f"System bonus suppressed for caption {caption.caption_id}: "
            f"voter {voter_id} and author {caption.author_player_id} are Circle-mates"
        )
    else:
        writer_bonus = entry_cost * writer_bonus_multiplier
    
    gross_payout = base_payout + writer_bonus
    
    # Get lifetime earnings for split calculation
    author_lifetime_earnings = caption.lifetime_earnings_gross
    parent_lifetime_earnings = 0
    parent_caption = None
    parent_is_circle_mate = False
    
    is_riff = caption.kind == 'riff'
    if is_riff and caption.parent_caption_id:
        parent_caption = await self.db.get(MMCaption, caption.parent_caption_id)
        if parent_caption and parent_caption.author_player_id:
            parent_lifetime_earnings = parent_caption.lifetime_earnings_gross
            parent_is_circle_mate = await self._is_circle_mate(
                voter_id, parent_caption.author_player_id
            )
            
            # Suppress parent bonus if parent is Circle-mate
            if parent_is_circle_mate:
                logger.info(
                    f"Parent system bonus suppressed for caption {parent_caption.caption_id}: "
                    f"voter {voter_id} and parent author {parent_caption.author_player_id} are Circle-mates"
                )
    
    # Calculate split with modified gross payout
    # NOTE: The scoring_service.calculate_caption_payout() handles the split
    # We pass gross_payout which now excludes bonuses for Circle-mates
    payout_breakdown = self.scoring_service.calculate_caption_payout(
        gross_payout,
        author_lifetime_earnings,
        parent_lifetime_earnings,
        is_riff
    )
    
    # If parent is Circle-mate, adjust parent's share similarly
    # (This requires coordination with scoring service - see note below)
    
    # Update caption earnings
    caption.lifetime_earnings_gross += payout_breakdown['total_gross']
    caption.lifetime_to_wallet += payout_breakdown['author_wallet']
    caption.lifetime_to_vault += payout_breakdown['author_vault']
    
    # Distribute transactions...
    # (rest of existing logic unchanged)
    
    return {
        'total_gross': payout_breakdown['total_gross'],
        'total_wallet': payout_breakdown['author_wallet'] + payout_breakdown['parent_wallet'],
        'total_vault': payout_breakdown['author_vault'] + payout_breakdown['parent_vault'],
        'author_wallet': payout_breakdown['author_wallet'],
        'author_vault': payout_breakdown['author_vault'],
        'parent_wallet': payout_breakdown['parent_wallet'],
        'parent_vault': payout_breakdown['parent_vault'],
        'bonus_suppressed': author_is_circle_mate or parent_is_circle_mate,
    }
```

**Update call site in `submit_vote()`:**
```python
# Calculate and distribute payouts to caption author(s)
payout_info = await self._distribute_caption_payouts(
    caption,
    round_obj.entry_cost,
    house_rake_vault_pct,
    transaction_service,
    player.player_id  # Pass voter ID for Circle-mate check
)
```

**IMPORTANT NOTE**: The exact implementation of bonus suppression depends on how you want to handle riffs:
- **Option A**: Suppress entire gross payout if author is Circle-mate (simple)
- **Option B**: Calculate base vs bonus separately for author and parent (more complex but precise)

The spec says "evaluated per earning author", so Option B is more accurate. This may require refactoring `calculate_caption_payout()` to accept separate base/bonus amounts for author vs parent.

---

### 3.5 API Router

#### File: `/backend/routers/mm/circles.py`

```python
"""Circles API router for Meme Mint."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.mm.player import MMPlayer
from backend.routers.mm.rounds import get_mm_player
from backend.schemas.mm_circle import (
    CircleCreate,
    CircleUpdate,
    CircleDetail,
    CircleSummary,
    CircleListResponse,
    JoinRequestCreate,
    JoinRequestResponse,
    ApproveJoinRequest,
    AddMemberRequest,
    CircleActionResponse,
    CircleMemberInfo,
)
from backend.services.mm.circle_service import MMCircleService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=CircleActionResponse)
async def create_circle(
    request: CircleCreate,
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """Create a new Circle."""
    circle_service = MMCircleService(db)
    
    try:
        circle = await circle_service.create_circle(
            name=request.name,
            creator_id=player.player_id,
            description=request.description
        )
        
        return CircleActionResponse(
            success=True,
            message=f"Circle '{circle.name}' created successfully",
            circle_id=circle.circle_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating circle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create circle")


@router.get("/", response_model=CircleListResponse)
async def list_circles(
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """List all discoverable circles with membership status."""
    circle_service = MMCircleService(db)
    
    try:
        all_circles = await circle_service.list_all_circles()
        player_circles = set(c.circle_id for c in await circle_service.list_player_circles(player.player_id))
        
        # Get pending requests
        from backend.models.mm.circle_join_request import MMCircleJoinRequest
        from sqlalchemy import select
        stmt = select(MMCircleJoinRequest.circle_id).where(
            MMCircleJoinRequest.player_id == player.player_id,
            MMCircleJoinRequest.status == 'pending'
        )
        result = await db.execute(stmt)
        pending_request_circles = set(result.scalars().all())
        
        # Build summaries
        summaries = []
        for circle in all_circles:
            member_count = await circle_service.get_member_count(circle.circle_id)
            summaries.append(
                CircleSummary(
                    circle_id=circle.circle_id,
                    name=circle.name,
                    description=circle.description,
                    member_count=member_count,
                    created_at=circle.created_at,
                    is_member=circle.circle_id in player_circles,
                    is_admin=circle.created_by_player_id == player.player_id,
                    has_pending_request=circle.circle_id in pending_request_circles
                )
            )
        
        return CircleListResponse(circles=summaries)
    
    except Exception as e:
        logger.error(f"Error listing circles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list circles")


@router.get("/my", response_model=CircleListResponse)
async def list_my_circles(
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """List circles the current player is a member of."""
    circle_service = MMCircleService(db)
    
    try:
        player_circles = await circle_service.list_player_circles(player.player_id)
        
        summaries = []
        for circle in player_circles:
            member_count = await circle_service.get_member_count(circle.circle_id)
            summaries.append(
                CircleSummary(
                    circle_id=circle.circle_id,
                    name=circle.name,
                    description=circle.description,
                    member_count=member_count,
                    created_at=circle.created_at,
                    is_member=True,
                    is_admin=circle.created_by_player_id == player.player_id,
                    has_pending_request=False
                )
            )
        
        return CircleListResponse(circles=summaries)
    
    except Exception as e:
        logger.error(f"Error listing player circles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list circles")


@router.get("/{circle_id}", response_model=CircleDetail)
async def get_circle_detail(
    circle_id: UUID = Path(...),
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a Circle."""
    circle_service = MMCircleService(db)
    
    try:
        circle = await circle_service.get_circle_with_members(circle_id)
        if not circle:
            raise HTTPException(status_code=404, detail="Circle not found")
        
        # Load member player info
        from sqlalchemy import select
        from backend.models.mm.player import MMPlayer as PlayerModel
        
        member_ids = [m.player_id for m in circle.members]
        stmt = select(PlayerModel).where(PlayerModel.player_id.in_(member_ids))
        result = await db.execute(stmt)
        players_map = {p.player_id: p for p in result.scalars().all()}
        
        # Build member list
        members = []
        for membership in circle.members:
            player_obj = players_map.get(membership.player_id)
            if player_obj:
                members.append(
                    CircleMemberInfo(
                        player_id=player_obj.player_id,
                        username=player_obj.username,
                        joined_at=membership.joined_at,
                        is_admin=player_obj.player_id == circle.created_by_player_id
                    )
                )
        
        # Check pending request
        from backend.models.mm.circle_join_request import MMCircleJoinRequest
        stmt = select(MMCircleJoinRequest).where(
            MMCircleJoinRequest.circle_id == circle_id,
            MMCircleJoinRequest.player_id == player.player_id,
            MMCircleJoinRequest.status == 'pending'
        )
        result = await db.execute(stmt)
        has_pending = result.scalar_one_or_none() is not None
        
        return CircleDetail(
            circle_id=circle.circle_id,
            name=circle.name,
            description=circle.description,
            created_by_player_id=circle.created_by_player_id,
            created_at=circle.created_at,
            updated_at=circle.updated_at,
            member_count=len(members),
            members=members,
            is_member=any(m.player_id == player.player_id for m in members),
            is_admin=circle.created_by_player_id == player.player_id,
            has_pending_request=has_pending
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting circle detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get circle details")


@router.post("/{circle_id}/join", response_model=JoinRequestResponse)
async def request_to_join_circle(
    circle_id: UUID = Path(...),
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """Request to join a Circle."""
    circle_service = MMCircleService(db)
    
    try:
        request = await circle_service.request_to_join(circle_id, player.player_id)
        
        return JoinRequestResponse(
            request_id=request.request_id,
            circle_id=request.circle_id,
            player_id=request.player_id,
            requested_at=request.requested_at,
            status=request.status
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error requesting to join circle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create join request")


@router.post("/{circle_id}/members/add", response_model=CircleActionResponse)
async def add_member_to_circle(
    circle_id: UUID = Path(...),
    request: AddMemberRequest = ...,
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a Circle (admin only)."""
    circle_service = MMCircleService(db)
    
    try:
        # Look up player by username
        from sqlalchemy import select
        from backend.models.mm.player import MMPlayer as PlayerModel
        
        stmt = select(PlayerModel).where(PlayerModel.username == request.username)
        result = await db.execute(stmt)
        target_player = result.scalar_one_or_none()
        
        if not target_player:
            raise HTTPException(status_code=404, detail=f"Player '{request.username}' not found")
        
        await circle_service.add_member(
            circle_id=circle_id,
            player_id=target_player.player_id,
            invited_by_id=player.player_id
        )
        
        return CircleActionResponse(
            success=True,
            message=f"Player '{request.username}' added to circle",
            circle_id=circle_id
        )
    
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding member: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add member")


@router.delete("/{circle_id}/members/{player_id}", response_model=CircleActionResponse)
async def remove_member_from_circle(
    circle_id: UUID = Path(...),
    player_id: UUID = Path(...),
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from a Circle (admin or self)."""
    circle_service = MMCircleService(db)
    
    try:
        await circle_service.remove_member(
            circle_id=circle_id,
            player_id=player_id,
            removed_by_id=player.player_id
        )
        
        return CircleActionResponse(
            success=True,
            message="Member removed from circle",
            circle_id=circle_id
        )
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing member: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove member")


@router.post("/{circle_id}/requests/{request_id}/review", response_model=CircleActionResponse)
async def review_join_request(
    circle_id: UUID = Path(...),
    request_id: UUID = Path(...),
    request: ApproveJoinRequest = ...,
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """Approve or deny a join request (admin only)."""
    circle_service = MMCircleService(db)
    
    try:
        await circle_service.approve_join_request(
            request_id=request.request_id,
            reviewer_id=player.player_id,
            approved=request.approved
        )
        
        action = "approved" if request.approved else "denied"
        return CircleActionResponse(
            success=True,
            message=f"Join request {action}",
            circle_id=circle_id
        )
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error reviewing join request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to review request")


@router.get("/{circle_id}/requests", response_model=list[JoinRequestResponse])
async def get_pending_requests(
    circle_id: UUID = Path(...),
    player: MMPlayer = Depends(get_mm_player),
    db: AsyncSession = Depends(get_db),
):
    """Get pending join requests for a Circle (admin only)."""
    circle_service = MMCircleService(db)
    
    try:
        # Verify admin
        circle = await circle_service.get_circle(circle_id)
        if not circle:
            raise HTTPException(status_code=404, detail="Circle not found")
        
        if circle.created_by_player_id != player.player_id:
            raise HTTPException(status_code=403, detail="Only circle admin can view requests")
        
        requests = await circle_service.get_pending_requests_for_circle(circle_id)
        
        return [
            JoinRequestResponse(
                request_id=req.request_id,
                circle_id=req.circle_id,
                player_id=req.player_id,
                requested_at=req.requested_at,
                status=req.status
            )
            for req in requests
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending requests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get requests")
```

**Register router in main MM router:**

Update `/backend/routers/mm/__init__.py`:
```python
from fastapi import APIRouter
from .auth import router as auth_router
from .rounds import router as rounds_router
from .player import router as player_router
from .images import router as images_router
from .circles import router as circles_router  # NEW

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(rounds_router, prefix="/rounds", tags=["rounds"])
router.include_router(player_router, prefix="/player", tags=["player"])
router.include_router(images_router, prefix="/images", tags=["images"])
router.include_router(circles_router, prefix="/circles", tags=["circles"])  # NEW
```

---

## Frontend Implementation

### 4.1 API Client Methods

#### Update: `/mm_frontend/src/api/client.ts`

Add new types and methods:

```typescript
// Add to types imports at top
import type {
  CircleSummary,
  CircleDetail,
  CircleListResponse,
  CircleActionResponse,
  JoinRequestResponse,
  CircleMemberInfo,
} from './types';

// Add new Circle API methods
const apiClient = {
  // ... existing methods ...

  // Circles
  async listCircles(): Promise<CircleListResponse> {
    logApi('GET', '/circles', 'start');
    try {
      const { data } = await axiosInstance.get<CircleListResponse>('/circles');
      logApi('GET', '/circles', 'success', data);
      return data;
    } catch (error) {
      logApi('GET', '/circles', 'error', error);
      throw error;
    }
  },

  async listMyCircles(): Promise<CircleListResponse> {
    logApi('GET', '/circles/my', 'start');
    try {
      const { data } = await axiosInstance.get<CircleListResponse>('/circles/my');
      logApi('GET', '/circles/my', 'success', data);
      return data;
    } catch (error) {
      logApi('GET', '/circles/my', 'error', error);
      throw error;
    }
  },

  async getCircleDetail(circleId: string): Promise<CircleDetail> {
    logApi('GET', `/circles/${circleId}`, 'start');
    try {
      const { data } = await axiosInstance.get<CircleDetail>(`/circles/${circleId}`);
      logApi('GET', `/circles/${circleId}`, 'success', data);
      return data;
    } catch (error) {
      logApi('GET', `/circles/${circleId}`, 'error', error);
      throw error;
    }
  },

  async createCircle(name: string, description?: string): Promise<CircleActionResponse> {
    logApi('POST', '/circles', 'start');
    try {
      const { data } = await axiosInstance.post<CircleActionResponse>('/circles', {
        name,
        description,
      });
      logApi('POST', '/circles', 'success', data);
      return data;
    } catch (error) {
      logApi('POST', '/circles', 'error', error);
      throw error;
    }
  },

  async requestToJoinCircle(circleId: string): Promise<JoinRequestResponse> {
    logApi('POST', `/circles/${circleId}/join`, 'start');
    try {
      const { data } = await axiosInstance.post<JoinRequestResponse>(
        `/circles/${circleId}/join`
      );
      logApi('POST', `/circles/${circleId}/join`, 'success', data);
      return data;
    } catch (error) {
      logApi('POST', `/circles/${circleId}/join`, 'error', error);
      throw error;
    }
  },

  async addMemberToCircle(circleId: string, username: string): Promise<CircleActionResponse> {
    logApi('POST', `/circles/${circleId}/members/add`, 'start');
    try {
      const { data } = await axiosInstance.post<CircleActionResponse>(
        `/circles/${circleId}/members/add`,
        { username }
      );
      logApi('POST', `/circles/${circleId}/members/add`, 'success', data);
      return data;
    } catch (error) {
      logApi('POST', `/circles/${circleId}/members/add`, 'error', error);
      throw error;
    }
  },

  async removeMemberFromCircle(circleId: string, playerId: string): Promise<CircleActionResponse> {
    logApi('DELETE', `/circles/${circleId}/members/${playerId}`, 'start');
    try {
      const { data } = await axiosInstance.delete<CircleActionResponse>(
        `/circles/${circleId}/members/${playerId}`
      );
      logApi('DELETE', `/circles/${circleId}/members/${playerId}`, 'success', data);
      return data;
    } catch (error) {
      logApi('DELETE', `/circles/${circleId}/members/${playerId}`, 'error', error);
      throw error;
    }
  },

  async reviewJoinRequest(
    circleId: string,
    requestId: string,
    approved: boolean
  ): Promise<CircleActionResponse> {
    logApi('POST', `/circles/${circleId}/requests/${requestId}/review`, 'start');
    try {
      const { data } = await axiosInstance.post<CircleActionResponse>(
        `/circles/${circleId}/requests/${requestId}/review`,
        { request_id: requestId, approved }
      );
      logApi('POST', `/circles/${circleId}/requests/${requestId}/review`, 'success', data);
      return data;
    } catch (error) {
      logApi('POST', `/circles/${circleId}/requests/${requestId}/review`, 'error', error);
      throw error;
    }
  },

  async getPendingRequests(circleId: string): Promise<JoinRequestResponse[]> {
    logApi('GET', `/circles/${circleId}/requests`, 'start');
    try {
      const { data } = await axiosInstance.get<JoinRequestResponse[]>(
        `/circles/${circleId}/requests`
      );
      logApi('GET', `/circles/${circleId}/requests`, 'success', data);
      return data;
    } catch (error) {
      logApi('GET', `/circles/${circleId}/requests`, 'error', error);
      throw error;
    }
  },
};

export default apiClient;
export { extractErrorMessage };
```

---

#### File: `/mm_frontend/src/api/types.ts`

Add Circle-related types:

```typescript
// Circle types
export interface CircleSummary {
  circle_id: string;
  name: string;
  description: string | null;
  member_count: number;
  created_at: string;
  is_member: boolean;
  is_admin: boolean;
  has_pending_request: boolean;
}

export interface CircleMemberInfo {
  player_id: string;
  username: string;
  joined_at: string;
  is_admin: boolean;
}

export interface CircleDetail {
  circle_id: string;
  name: string;
  description: string | null;
  created_by_player_id: string | null;
  created_at: string;
  updated_at: string;
  member_count: number;
  members: CircleMemberInfo[];
  is_member: boolean;
  is_admin: boolean;
  has_pending_request: boolean;
}

export interface CircleListResponse {
  circles: CircleSummary[];
}

export interface CircleActionResponse {
  success: boolean;
  message: string;
  circle_id: string | null;
}

export interface JoinRequestResponse {
  request_id: string;
  circle_id: string;
  player_id: string;
  requested_at: string;
  status: string;
}
```

---

### 4.2 Circles Page

#### File: `/mm_frontend/src/pages/Circles.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '../api/client';
import type { CircleSummary } from '../api/types';
import { LoadingSpinner } from '../components/LoadingSpinner';

export const Circles: React.FC = () => {
  const navigate = useNavigate();
  const [myCircles, setMyCircles] = useState<CircleSummary[]>([]);
  const [allCircles, setAllCircles] = useState<CircleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadCircles();
  }, []);

  const loadCircles = async () => {
    setLoading(true);
    setError(null);
    try {
      const [myData, allData] = await Promise.all([
        apiClient.listMyCircles(),
        apiClient.listCircles(),
      ]);
      setMyCircles(myData.circles);
      setAllCircles(allData.circles);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to load circles');
    } finally {
      setLoading(false);
    }
  };

  const handleCircleClick = (circleId: string) => {
    navigate(`/game/circles/${circleId}`);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading message="Loading circles..." />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 pb-12 pt-4">
      <div className="tile-card p-6 md:p-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Circles</h1>
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-quip-teal text-white font-bold py-2 px-6 rounded-tile shadow-tile hover:shadow-tile-sm transition-all"
          >
            Create Circle
          </button>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* My Circles */}
        <section className="mb-8">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">My Circles</h2>
          {myCircles.length === 0 ? (
            <p className="text-gray-600">You haven't joined any circles yet.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {myCircles.map((circle) => (
                <CircleCard
                  key={circle.circle_id}
                  circle={circle}
                  onClick={() => handleCircleClick(circle.circle_id)}
                />
              ))}
            </div>
          )}
        </section>

        {/* Discover Circles */}
        <section>
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">
            Discover Circles
          </h2>
          {allCircles.length === 0 ? (
            <p className="text-gray-600">No circles available yet. Create the first one!</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {allCircles.map((circle) => (
                <CircleCard
                  key={circle.circle_id}
                  circle={circle}
                  onClick={() => handleCircleClick(circle.circle_id)}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      {showCreateModal && (
        <CreateCircleModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            loadCircles();
          }}
        />
      )}
    </div>
  );
};

const CircleCard: React.FC<{
  circle: CircleSummary;
  onClick: () => void;
}> = ({ circle, onClick }) => {
  return (
    <div
      onClick={onClick}
      className="border-2 border-quip-navy rounded-tile p-4 bg-white cursor-pointer hover:shadow-tile transition-shadow"
    >
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-xl font-display font-bold text-quip-navy">{circle.name}</h3>
        {circle.is_admin && (
          <span className="text-xs bg-quip-orange text-white px-2 py-1 rounded">Admin</span>
        )}
      </div>
      <p className="text-sm text-gray-600 mb-3">
        {circle.description || 'No description'}
      </p>
      <div className="flex justify-between items-center text-sm">
        <span className="text-quip-teal font-semibold">{circle.member_count} members</span>
        {circle.is_member ? (
          <span className="text-green-600">Member</span>
        ) : circle.has_pending_request ? (
          <span className="text-yellow-600">Pending</span>
        ) : (
          <span className="text-gray-500">Not a member</span>
        )}
      </div>
    </div>
  );
};

const CreateCircleModal: React.FC<{
  onClose: () => void;
  onSuccess: () => void;
}> = ({ onClose, onSuccess }) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await apiClient.createCircle(name, description || undefined);
      onSuccess();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to create circle');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-tile p-6 max-w-md w-full mx-4">
        <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Create Circle</h2>
        
        {error && (
          <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-semibold text-quip-navy mb-2">
              Circle Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border-2 border-quip-navy rounded px-3 py-2"
              placeholder="e.g., Meme Masters"
              required
              minLength={3}
              maxLength={100}
            />
          </div>

          <div className="mb-6">
            <label className="block text-sm font-semibold text-quip-navy mb-2">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full border-2 border-quip-navy rounded px-3 py-2"
              placeholder="What's this circle about?"
              rows={3}
              maxLength={500}
            />
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 border-2 border-quip-navy text-quip-navy font-bold py-2 px-4 rounded-tile"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 bg-quip-teal text-white font-bold py-2 px-4 rounded-tile shadow-tile hover:shadow-tile-sm transition-all disabled:opacity-50"
              disabled={submitting}
            >
              {submitting ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Circles;
```

---

#### File: `/mm_frontend/src/pages/CircleDetail.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '../api/client';
import type { CircleDetail as CircleDetailType, CircleMemberInfo } from '../api/types';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { useGame } from '../contexts/GameContext';

export const CircleDetail: React.FC = () => {
  const { circleId } = useParams<{ circleId: string }>();
  const navigate = useNavigate();
  const { state } = useGame();
  const currentPlayerId = state.player?.player_id;

  const [circle, setCircle] = useState<CircleDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState(false);

  useEffect(() => {
    if (circleId) {
      loadCircle();
    }
  }, [circleId]);

  const loadCircle = async () => {
    if (!circleId) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getCircleDetail(circleId);
      setCircle(data);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to load circle');
    } finally {
      setLoading(false);
    }
  };

  const handleJoinRequest = async () => {
    if (!circleId || !circle) return;
    
    setActionInProgress(true);
    setError(null);
    try {
      await apiClient.requestToJoinCircle(circleId);
      await loadCircle();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to send join request');
    } finally {
      setActionInProgress(false);
    }
  };

  const handleLeave = async () => {
    if (!circleId || !circle || !currentPlayerId) return;
    
    if (!confirm('Are you sure you want to leave this circle?')) return;
    
    setActionInProgress(true);
    setError(null);
    try {
      await apiClient.removeMemberFromCircle(circleId, currentPlayerId);
      navigate('/game/circles');
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to leave circle');
      setActionInProgress(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading message="Loading circle..." />
      </div>
    );
  }

  if (!circle) {
    return (
      <div className="max-w-4xl mx-auto px-4 pb-12 pt-4">
        <div className="tile-card p-6">
          <p className="text-red-600">{error || 'Circle not found'}</p>
          <button
            onClick={() => navigate('/game/circles')}
            className="mt-4 text-quip-teal font-semibold"
          >
            ← Back to Circles
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 pb-12 pt-4">
      <div className="tile-card p-6 md:p-8">
        <button
          onClick={() => navigate('/game/circles')}
          className="mb-4 text-quip-teal font-semibold hover:underline"
        >
          ← Back to Circles
        </button>

        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-3xl font-display font-bold text-quip-navy mb-2">
              {circle.name}
            </h1>
            {circle.description && (
              <p className="text-gray-600">{circle.description}</p>
            )}
          </div>
          {circle.is_admin && (
            <span className="bg-quip-orange text-white px-3 py-1 rounded font-semibold">
              Admin
            </span>
          )}
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Action buttons */}
        <div className="mb-6">
          {!circle.is_member && !circle.has_pending_request && (
            <button
              onClick={handleJoinRequest}
              disabled={actionInProgress}
              className="bg-quip-teal text-white font-bold py-2 px-6 rounded-tile shadow-tile hover:shadow-tile-sm transition-all disabled:opacity-50"
            >
              {actionInProgress ? 'Requesting...' : 'Request to Join'}
            </button>
          )}
          {circle.has_pending_request && (
            <span className="text-yellow-600 font-semibold">Join request pending</span>
          )}
          {circle.is_member && !circle.is_admin && (
            <button
              onClick={handleLeave}
              disabled={actionInProgress}
              className="border-2 border-red-500 text-red-500 font-bold py-2 px-6 rounded-tile hover:bg-red-50 transition-all disabled:opacity-50"
            >
              {actionInProgress ? 'Leaving...' : 'Leave Circle'}
            </button>
          )}
        </div>

        {/* Members list */}
        <section>
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">
            Members ({circle.member_count})
          </h2>
          <div className="space-y-2">
            {circle.members.map((member) => (
              <MemberRow
                key={member.player_id}
                member={member}
                isCurrentPlayer={member.player_id === currentPlayerId}
                canRemove={circle.is_admin && member.player_id !== currentPlayerId}
                onRemove={async () => {
                  if (!circleId) return;
                  if (!confirm(`Remove ${member.username} from circle?`)) return;
                  
                  setActionInProgress(true);
                  try {
                    await apiClient.removeMemberFromCircle(circleId, member.player_id);
                    await loadCircle();
                  } catch (err) {
                    setError(extractErrorMessage(err) || 'Failed to remove member');
                  } finally {
                    setActionInProgress(false);
                  }
                }}
              />
            ))}
          </div>
        </section>

        {/* Admin controls */}
        {circle.is_admin && (
          <section className="mt-8 pt-6 border-t-2 border-gray-200">
            <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">
              Admin Controls
            </h2>
            <AddMemberForm circleId={circleId!} onSuccess={loadCircle} />
          </section>
        )}
      </div>
    </div>
  );
};

const MemberRow: React.FC<{
  member: CircleMemberInfo;
  isCurrentPlayer: boolean;
  canRemove: boolean;
  onRemove: () => void;
}> = ({ member, isCurrentPlayer, canRemove, onRemove }) => {
  return (
    <div className="flex justify-between items-center border-2 border-quip-navy rounded p-3 bg-white">
      <div>
        <span className="font-semibold text-quip-navy">
          {member.username}
          {isCurrentPlayer && <span className="text-sm text-gray-500 ml-2">(you)</span>}
        </span>
        {member.is_admin && (
          <span className="ml-2 text-xs bg-quip-orange text-white px-2 py-1 rounded">
            Admin
          </span>
        )}
      </div>
      {canRemove && (
        <button
          onClick={onRemove}
          className="text-red-500 text-sm font-semibold hover:underline"
        >
          Remove
        </button>
      )}
    </div>
  );
};

const AddMemberForm: React.FC<{
  circleId: string;
  onSuccess: () => void;
}> = ({ circleId, onSuccess }) => {
  const [username, setUsername] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await apiClient.addMemberToCircle(circleId, username);
      setUsername('');
      onSuccess();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to add member');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="border-2 border-quip-teal rounded-tile p-4 bg-quip-teal/5">
      <h3 className="font-semibold text-quip-navy mb-3">Add Member</h3>
      
      {error && (
        <div className="mb-3 p-2 bg-red-100 border border-red-400 text-red-700 rounded text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="flex-1 border-2 border-quip-navy rounded px-3 py-2"
          placeholder="Enter username"
          required
        />
        <button
          type="submit"
          className="bg-quip-teal text-white font-bold py-2 px-6 rounded-tile shadow-tile hover:shadow-tile-sm transition-all disabled:opacity-50"
          disabled={submitting}
        >
          {submitting ? 'Adding...' : 'Add'}
        </button>
      </form>
    </div>
  );
};

export default CircleDetail;
```

---

### 4.3 VoteRound UI Changes

#### Update: `/mm_frontend/src/pages/VoteRound.tsx`

Add Circle badge display after vote reveal.

**Key changes:**
1. Fetch Circle-mate status after vote submission
2. Display badge next to Circle-mate authors in results

**Add new type to `/mm_frontend/src/api/types.ts`:**
```typescript
export interface VoteResult {
  success: boolean;
  chosen_caption_id: string;
  payout: number;
  correct: boolean;
  new_wallet: number;
  new_vault: number;
  circle_mate_authors?: string[];  // NEW: List of Circle-mate author IDs
}
```

**Backend update needed**: Modify `/backend/schemas/mm_round.py` `SubmitVoteResponse` to include `circle_mate_authors` field:

```python
class SubmitVoteResponse(BaseModel):
    """Submit vote response."""
    success: bool
    chosen_caption_id: UUID
    payout: int
    correct: bool
    new_wallet: int
    new_vault: int
    circle_mate_authors: list[UUID] = []  # NEW
```

**Backend logic update in `/backend/routers/mm/rounds.py` `submit_vote()`:**

After vote submission, identify which caption authors are Circle-mates:

```python
# After vote service returns result
# Load caption authors
caption_ids = [UUID(str(cid)) for cid in round_obj.caption_ids_shown]
stmt = select(MMCaption).where(MMCaption.caption_id.in_(caption_ids))
result_captions = await db.execute(stmt)
captions_map = {c.caption_id: c for c in result_captions.scalars().all()}

# Get Circle-mates
from backend.services.mm.circle_service import MMCircleService
circle_service = MMCircleService(db)
circle_mate_ids = await circle_service.get_circle_mates(player.player_id)

# Identify Circle-mate authors
circle_mate_authors = [
    c.author_player_id
    for c in captions_map.values()
    if c.author_player_id and c.author_player_id in circle_mate_ids
]

return SubmitVoteResponse(
    success=True,
    chosen_caption_id=request.caption_id,
    payout=result['payout_wallet'] + result['payout_vault'],
    correct=True,
    new_wallet=result['new_wallet'],
    new_vault=result['new_vault'],
    circle_mate_authors=circle_mate_authors  # NEW
)
```

**Frontend VoteRound.tsx update:**

In the results display section, add Circle badge:

```typescript
{/* After vote reveal, show all captions with results */}
{result && round && (
  <div className="space-y-3">
    {round.captions.map((caption) => {
      const isWinner = caption.caption_id === result.chosen_caption_id;
      const isCircleMate = result.circle_mate_authors?.includes(caption.author_id);
      
      return (
        <div
          key={caption.caption_id}
          className={`border-2 rounded-tile p-4 ${
            isWinner ? 'border-quip-orange bg-quip-orange/10' : 'border-quip-navy'
          }`}
        >
          <p className="text-lg mb-2">{caption.text}</p>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>by {caption.author_name || 'Anonymous'}</span>
            {isCircleMate && (
              <span className="inline-flex items-center gap-1 bg-quip-teal/20 text-quip-teal px-2 py-0.5 rounded text-xs font-semibold">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M13 6a3 3 0 11-6 0 3 3 0 016 0zM18 8a2 2 0 11-4 0 2 2 0 014 0zM14 15a4 4 0 00-8 0v3h8v-3zM6 8a2 2 0 11-4 0 2 2 0 014 0zM16 18v-3a5.972 5.972 0 00-.75-2.906A3.005 3.005 0 0119 15v3h-3zM4.75 12.094A5.973 5.973 0 004 15v3H1v-3a3 3 0 013.75-2.906z" />
                </svg>
                Circle
              </span>
            )}
            {isWinner && (
              <span className="text-quip-orange font-bold">Winner!</span>
            )}
          </div>
        </div>
      );
    })}
  </div>
)}
```

---

### 4.4 Navigation Updates

#### Update: `/mm_frontend/src/App.tsx`

Add Circles route:

```typescript
import Circles from './pages/Circles';
import CircleDetail from './pages/CircleDetail';

// In AppRoutes component
<Routes>
  {/* Existing routes */}
  <Route path="/" element={renderWithSuspense(<Landing />)} />
  <Route path="/game/dashboard" element={renderProtectedRoute(<Dashboard />)} />
  <Route path="/game/vote" element={renderProtectedRoute(<VoteRound />)} />
  <Route path="/game/caption" element={renderProtectedRoute(<CaptionRound />)} />
  
  {/* NEW: Circles routes */}
  <Route path="/game/circles" element={renderProtectedRoute(<Circles />)} />
  <Route path="/game/circles/:circleId" element={renderProtectedRoute(<CircleDetail />)} />
  
  {/* Other routes... */}
</Routes>
```

#### Update: `/mm_frontend/src/components/SubHeader.tsx`

Add Circles navigation link (if SubHeader exists, otherwise add to Header):

```typescript
<nav className="flex gap-6">
  <NavLink to="/game/dashboard">Dashboard</NavLink>
  <NavLink to="/game/circles">Circles</NavLink>  {/* NEW */}
  <NavLink to="/game/leaderboard">Leaderboard</NavLink>
  <NavLink to="/game/history">History</NavLink>
  {/* Other links */}
</nav>
```

---

## Migration Strategy

### 5.1 Alembic Migration File

#### File: `/backend/migrations/versions/YYYYMMDD_add_circles_tables.py`

```python
"""Add Circles tables for MemeMint.

Revision ID: [generated]
Revises: [latest]
Create Date: [timestamp]
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_uuid_type, get_timestamp_default

# revision identifiers, used by Alembic.
revision: str = "[generated]"
down_revision: str | None = "[latest]"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = get_uuid_type()
    timestamp_default = get_timestamp_default()

    # mm_circles table
    op.create_table(
        "mm_circles",
        sa.Column("circle_id", uuid, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_player_id", uuid, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(["created_by_player_id"], ["mm_players.player_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("circle_id"),
        sa.UniqueConstraint("name", name="uq_mm_circles_name"),
    )
    op.create_index("ix_mm_circles_status", "mm_circles", ["status"])
    op.create_index("ix_mm_circles_created_by", "mm_circles", ["created_by_player_id"])
    op.create_index("ix_mm_circles_name", "mm_circles", ["name"])

    # mm_circle_members table
    op.create_table(
        "mm_circle_members",
        sa.Column("membership_id", uuid, nullable=False),
        sa.Column("circle_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("invited_by_player_id", uuid, nullable=True),
        sa.ForeignKeyConstraint(["circle_id"], ["mm_circles.circle_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_player_id"], ["mm_players.player_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint("circle_id", "player_id", name="uq_mm_circle_members_circle_player"),
    )
    op.create_index("ix_mm_circle_members_circle", "mm_circle_members", ["circle_id"])
    op.create_index("ix_mm_circle_members_player", "mm_circle_members", ["player_id"])
    op.create_index("ix_mm_circle_members_joined_at", "mm_circle_members", ["joined_at"])

    # mm_circle_join_requests table
    op.create_table(
        "mm_circle_join_requests",
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("circle_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_player_id", uuid, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["circle_id"], ["mm_circles.circle_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["mm_players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_player_id"], ["mm_players.player_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("request_id"),
        sa.UniqueConstraint("circle_id", "player_id", name="uq_mm_circle_join_requests_circle_player"),
    )
    op.create_index("ix_mm_circle_join_requests_circle_status", "mm_circle_join_requests", ["circle_id", "status"])
    op.create_index("ix_mm_circle_join_requests_player", "mm_circle_join_requests", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_mm_circle_join_requests_player", table_name="mm_circle_join_requests")
    op.drop_index("ix_mm_circle_join_requests_circle_status", table_name="mm_circle_join_requests")
    op.drop_table("mm_circle_join_requests")
    
    op.drop_index("ix_mm_circle_members_joined_at", table_name="mm_circle_members")
    op.drop_index("ix_mm_circle_members_player", table_name="mm_circle_members")
    op.drop_index("ix_mm_circle_members_circle", table_name="mm_circle_members")
    op.drop_table("mm_circle_members")
    
    op.drop_index("ix_mm_circles_name", table_name="mm_circles")
    op.drop_index("ix_mm_circles_created_by", table_name="mm_circles")
    op.drop_index("ix_mm_circles_status", table_name="mm_circles")
    op.drop_table("mm_circles")
```

**Run migration:**
```bash
cd /Users/tfish/PycharmProjects/quipflip
alembic revision --autogenerate -m "add_circles_tables"
alembic upgrade head
```

---

### 5.2 Data Migration Considerations

**No data migration needed** for MVP - this is purely additive. Existing players/captions/images are unaffected.

**Future considerations:**
- If implementing Circle invite history, migrate old data
- If adding Circle-specific stats, backfill from vote_rounds

---

## Testing Considerations

### 6.1 Key Test Scenarios

#### Unit Tests

**Service Layer:**
1. `MMCircleService.create_circle()` - circle name uniqueness, creator becomes member
2. `MMCircleService.add_member()` - admin permission check, duplicate prevention
3. `MMCircleService.remove_member()` - admin or self permission
4. `MMCircleService.get_circle_mates()` - union of all circles
5. `MMCircleService.is_circle_mate()` - shared circle detection

**Game Logic:**
1. `MMGameService._select_image_for_vote()` with Circle prioritization
2. `MMGameService._select_captions_for_round()` with Circle-first partitioning
3. `MMVoteService._distribute_caption_payouts()` bonus suppression

#### Integration Tests

**API Endpoints:**
1. POST `/circles` - create circle
2. GET `/circles` - list all circles with membership status
3. POST `/circles/{id}/join` - request to join
4. POST `/circles/{id}/members/add` - admin add member
5. DELETE `/circles/{id}/members/{player_id}` - remove member

**Game Flow:**
1. Two players in same Circle -> vote round shows Circle content preferentially
2. Player votes for Circle-mate caption -> system bonus suppressed
3. Player leaves Circle -> no longer gets Circle prioritization

---

### 6.2 Edge Cases

1. **Player with no Circles**: Should behave exactly as today (global selection only)
2. **Circle with inactive members**: Should gracefully handle members with no recent content
3. **Empty Circle content pool**: Should fall back to global without error
4. **Riff caption bonus suppression**: Parent and riff author evaluated separately
5. **Admin leaves Circle**: Circle persists, but no admin (spec allows this for MVP)
6. **Concurrent join/leave**: Unique constraints prevent duplicates
7. **Deleted player**: Foreign key SET NULL handles gracefully

---

## Implementation Phases

### Phase 1: Database & Models (Week 1)
- Create Alembic migration
- Implement ORM models (Circle, CircleMember, CircleJoinRequest)
- Run migration on dev environment
- Write model unit tests

### Phase 2: Service Layer (Week 1-2)
- Implement `MMCircleService` with all CRUD operations
- Add Circle-mate lookup methods
- Write service layer unit tests
- Integration tests for service methods

### Phase 3: Game Logic Integration (Week 2)
- Modify `MMGameService._select_image_for_vote()` for Circle prioritization
- Modify `MMGameService._select_captions_for_round()` for Circle-first selection
- Modify `MMVoteService._distribute_caption_payouts()` for bonus suppression
- Write game logic integration tests

### Phase 4: API Layer (Week 3)
- Implement `/circles` router endpoints
- Add Pydantic schemas
- Update existing round endpoints to return Circle metadata
- API integration tests

### Phase 5: Frontend (Week 3-4)
- Implement Circles page
- Implement CircleDetail page
- Update VoteRound results display with Circle badge
- Add navigation links
- Frontend E2E tests

### Phase 6: Testing & Polish (Week 4)
- Comprehensive integration testing
- Performance testing (Circle-mate queries)
- UI/UX polish
- Documentation updates

---

## Critical Files Summary

### Backend Files to Create:
1. `/backend/models/mm/circle.py` - Circle model
2. `/backend/models/mm/circle_member.py` - Membership model
3. `/backend/models/mm/circle_join_request.py` - Join request model
4. `/backend/services/mm/circle_service.py` - Circle management service
5. `/backend/routers/mm/circles.py` - Circles API router
6. `/backend/schemas/mm_circle.py` - Pydantic schemas
7. `/backend/migrations/versions/YYYYMMDD_add_circles_tables.py` - Migration

### Backend Files to Modify:
1. `/backend/services/mm/game_service.py` - Image & caption selection logic
2. `/backend/services/mm/vote_service.py` - Payout logic with bonus suppression
3. `/backend/routers/mm/rounds.py` - Add Circle metadata to vote response
4. `/backend/models/mm/__init__.py` - Import new models
5. `/backend/routers/mm/__init__.py` - Register circles router
6. `/backend/schemas/mm_round.py` - Add circle_mate_authors field

### Frontend Files to Create:
1. `/mm_frontend/src/pages/Circles.tsx` - Circles list page
2. `/mm_frontend/src/pages/CircleDetail.tsx` - Circle detail page

### Frontend Files to Modify:
1. `/mm_frontend/src/api/client.ts` - Add Circle API methods
2. `/mm_frontend/src/api/types.ts` - Add Circle types
3. `/mm_frontend/src/pages/VoteRound.tsx` - Add Circle badge display
4. `/mm_frontend/src/App.tsx` - Add routes
5. `/mm_frontend/src/components/SubHeader.tsx` or `/mm_frontend/src/components/Header.tsx` - Add navigation link

---

## Performance Optimization Notes

1. **Circle-mate lookup caching**: Cache `get_circle_mates()` result per request in application memory
2. **Lazy loading**: Only fetch Circle metadata when needed (not on every dashboard load)
3. **Index optimization**: All critical queries have covering indexes
4. **Connection pooling**: Ensure DB pool can handle additional Circle queries
5. **Future: Materialized view**: If Circle-mate queries become bottleneck, materialize the union

---

## Rollout Plan

1. **Deploy to staging**: Full feature testing with synthetic data
2. **Beta testing**: Select group of users test Circles for 1 week
3. **Gradual rollout**: Enable Circles page for 25% -> 50% -> 100% of users
4. **Monitor**: Track query performance, user engagement, bonus suppression rates
5. **Iterate**: Based on feedback, adjust UI, add moderation tools
