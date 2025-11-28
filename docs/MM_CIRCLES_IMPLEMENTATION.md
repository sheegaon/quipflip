# MemeMint Circles Feature - Detailed Implementation Plan

## Table of Contents

1. [Overview](#overview)
2. [Database Schema](#database-schema)
3. [Backend Implementation](#backend-implementation)
4. [Frontend Implementation](#frontend-implementation)
5. [Migration Strategy](#migration-strategy)
6. [Testing Considerations](#testing-considerations)
7. [Implementation Phases](#implementation-phases)

---

## Overview

The Circles feature adds persistent social groups to MemeMint. Members' content is preferentially shown to each other during gameplay, creating a "playing with friends" experience without requiring real-time coordination.

### Key Principles

- **Circle-mate definition**: Anyone who shares ANY Circle with you
- **Content prioritization**: System prefers Circle content when available, falls back to global pool seamlessly
- **No farming advantage**: System bonus suppressed when voting for Circle-mates
- **Multi-membership**: Players can belong to many Circles
- **Public MVP**: All Circles are discoverable; admin approval required to join

---

## Database Schema

### Table 1: `mm_circles`

Stores Circle definitions.

```sql
CREATE TABLE mm_circles (
    circle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_by_player_id UUID NOT NULL REFERENCES mm_players(player_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    member_count INTEGER NOT NULL DEFAULT 1,
    is_public BOOLEAN NOT NULL DEFAULT true,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
);

CREATE INDEX idx_mm_circles_created_by ON mm_circles(created_by_player_id);
CREATE INDEX idx_mm_circles_status ON mm_circles(status);
CREATE INDEX idx_mm_circles_name_lower ON mm_circles(LOWER(name));
```

**Fields:**
- `circle_id`: UUID primary key
- `name`: Unique Circle name (100 chars max)
- `description`: Optional description
- `created_by_player_id`: Admin/founder (foreign key to mm_players)
- `created_at`, `updated_at`: Timestamps
- `member_count`: Denormalized member count for efficient display
- `is_public`: Always `true` for MVP
- `status`: `active` | `archived`

**Indexes:**
- Primary key on `circle_id`
- Index on `created_by_player_id` for "my created circles" queries
- Index on `status` for filtering active circles
- Index on `LOWER(name)` for case-insensitive search

---

### Table 2: `mm_circle_members`

Tracks Circle membership.

```sql
CREATE TABLE mm_circle_members (
    circle_id UUID NOT NULL REFERENCES mm_circles(circle_id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES mm_players(player_id) ON DELETE CASCADE,
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    role VARCHAR(20) NOT NULL DEFAULT 'member',
    PRIMARY KEY (circle_id, player_id)
);

CREATE INDEX idx_mm_circle_members_player_id ON mm_circle_members(player_id);
CREATE INDEX idx_mm_circle_members_joined_at ON mm_circle_members(circle_id, joined_at DESC);
```

**Fields:**
- `circle_id`: Foreign key to mm_circles
- `player_id`: Foreign key to mm_players
- `joined_at`: When player joined
- `role`: `admin` | `member` (admin = creator in MVP)

**Primary Key:** Composite `(circle_id, player_id)`

**Indexes:**
- Index on `player_id` for "my circles" queries
- Index on `(circle_id, joined_at DESC)` for member lists sorted by join date

---

### Table 3: `mm_circle_join_requests`

Tracks pending join requests.

```sql
CREATE TABLE mm_circle_join_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    circle_id UUID NOT NULL REFERENCES mm_circles(circle_id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES mm_players(player_id) ON DELETE CASCADE,
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by_player_id UUID REFERENCES mm_players(player_id) ON DELETE SET NULL,
    UNIQUE (circle_id, player_id)
);

CREATE INDEX idx_mm_circle_join_requests_circle_status ON mm_circle_join_requests(circle_id, status);
CREATE INDEX idx_mm_circle_join_requests_player ON mm_circle_join_requests(player_id);
```

**Fields:**
- `request_id`: UUID primary key
- `circle_id`: Foreign key to mm_circles
- `player_id`: Requesting player
- `requested_at`: When request was made
- `status`: `pending` | `approved` | `denied`
- `resolved_at`: When admin responded
- `resolved_by_player_id`: Which admin approved/denied

**Constraints:**
- Unique constraint on `(circle_id, player_id)` to prevent duplicate requests

**Indexes:**
- Index on `(circle_id, status)` for admin view of pending requests
- Index on `player_id` for "my requests" queries

---

## Backend Implementation

### Phase 1: Database Models

Create three new model files in `/backend/models/mm/`:

#### File: `/backend/models/mm/circle.py`

```python
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, get_uuid_column

if TYPE_CHECKING:
    from .player import MMPlayer
    from .circle_member import MMCircleMember
    from .circle_join_request import MMCircleJoinRequest


class MMCircle(Base):
    """MemeMint Circle - persistent social group"""
    __tablename__ = "mm_circles"

    circle_id: Mapped[str] = get_uuid_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_player_id: Mapped[str] = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    member_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        index=True
    )

    # Relationships
    created_by: Mapped["MMPlayer"] = relationship(
        "MMPlayer",
        foreign_keys=[created_by_player_id],
        back_populates="created_circles"
    )
    members: Mapped[list["MMCircleMember"]] = relationship(
        "MMCircleMember",
        back_populates="circle",
        cascade="all, delete-orphan"
    )
    join_requests: Mapped[list["MMCircleJoinRequest"]] = relationship(
        "MMCircleJoinRequest",
        back_populates="circle",
        cascade="all, delete-orphan"
    )
```

#### File: `/backend/models/mm/circle_member.py`

```python
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, get_uuid_column

if TYPE_CHECKING:
    from .circle import MMCircle
    from .player import MMPlayer


class MMCircleMember(Base):
    """MemeMint Circle membership record"""
    __tablename__ = "mm_circle_members"
    __table_args__ = (
        UniqueConstraint("circle_id", "player_id", name="uq_mm_circle_member"),
    )

    circle_id: Mapped[str] = get_uuid_column(
        ForeignKey("mm_circles.circle_id", ondelete="CASCADE"),
        primary_key=True
    )
    player_id: Mapped[str] = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"),
        primary_key=True,
        index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")

    # Relationships
    circle: Mapped["MMCircle"] = relationship("MMCircle", back_populates="members")
    player: Mapped["MMPlayer"] = relationship("MMPlayer", back_populates="circle_memberships")
```

#### File: `/backend/models/mm/circle_join_request.py`

```python
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, get_uuid_column

if TYPE_CHECKING:
    from .circle import MMCircle
    from .player import MMPlayer


class MMCircleJoinRequest(Base):
    """MemeMint Circle join request"""
    __tablename__ = "mm_circle_join_requests"
    __table_args__ = (
        UniqueConstraint("circle_id", "player_id", name="uq_mm_circle_join_request"),
    )

    request_id: Mapped[str] = get_uuid_column(primary_key=True)
    circle_id: Mapped[str] = get_uuid_column(
        ForeignKey("mm_circles.circle_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    player_id: Mapped[str] = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    resolved_by_player_id: Mapped[str | None] = get_uuid_column(
        ForeignKey("mm_players.player_id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    circle: Mapped["MMCircle"] = relationship("MMCircle", back_populates="join_requests")
    player: Mapped["MMPlayer"] = relationship(
        "MMPlayer",
        foreign_keys=[player_id],
        back_populates="circle_join_requests"
    )
    resolved_by: Mapped["MMPlayer | None"] = relationship(
        "MMPlayer",
        foreign_keys=[resolved_by_player_id]
    )
```

#### File: `/backend/models/mm/player.py` (Update)

Add relationships to existing MMPlayer model:

```python
# Add to MMPlayer class:
created_circles: Mapped[list["MMCircle"]] = relationship(
    "MMCircle",
    foreign_keys="MMCircle.created_by_player_id",
    back_populates="created_by"
)
circle_memberships: Mapped[list["MMCircleMember"]] = relationship(
    "MMCircleMember",
    back_populates="player"
)
circle_join_requests: Mapped[list["MMCircleJoinRequest"]] = relationship(
    "MMCircleJoinRequest",
    foreign_keys="MMCircleJoinRequest.player_id",
    back_populates="player"
)
```

#### File: `/backend/models/mm/__init__.py` (Update)

Add exports:

```python
from .circle import MMCircle
from .circle_member import MMCircleMember
from .circle_join_request import MMCircleJoinRequest
```

---

### Phase 2: Service Layer

#### File: `/backend/services/mm/circle_service.py`

```python
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
        """Create a new Circle with creator as admin member."""
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
        """Get Circle by ID with optional member loading."""
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
        """List all discoverable Circles."""
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
        """Get all Circles a player belongs to."""
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
    async def get_circle_mates(
        session: AsyncSession,
        player_id: str
    ) -> set[str]:
        """
        Get all player IDs who share ANY Circle with the given player.
        Returns a set of player_id strings (Circle-mates).
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
        return {row[0] for row in result.all()}

    @staticmethod
    async def is_circle_mate(
        session: AsyncSession,
        player_id: str,
        other_player_id: str
    ) -> bool:
        """Check if two players share any Circle."""
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
        """Admin adds a member directly to a Circle."""
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
        """Remove a member from a Circle (admin action or self-leave)."""
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

        await session.commit()

    @staticmethod
    async def request_to_join(
        session: AsyncSession,
        circle_id: str,
        player_id: str
    ) -> MMCircleJoinRequest:
        """Player requests to join a Circle."""
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
        """Admin approves a join request."""
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

        await session.commit()
        return member

    @staticmethod
    async def deny_join_request(
        session: AsyncSession,
        request_id: str,
        admin_player_id: str
    ) -> None:
        """Admin denies a join request."""
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
        """Get all pending join requests for a Circle."""
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
    async def get_circle_members(
        session: AsyncSession,
        circle_id: str
    ) -> list[MMCircleMember]:
        """Get all members of a Circle with player details."""
        query = (
            select(MMCircleMember)
            .where(MMCircleMember.circle_id == circle_id)
            .order_by(MMCircleMember.joined_at.desc())
            .options(selectinload(MMCircleMember.player))
        )
        result = await session.execute(query)
        return list(result.scalars().all())
```

---

### Phase 3: Game Logic Integration

#### Modify: `/backend/services/mm/game_service.py`

**Changes to `_select_image_for_vote()` method:**

```python
async def _select_image_for_vote(
    self,
    session: AsyncSession,
    player_id: str,
    config: dict
) -> Optional[MMImage]:
    """
    Select an image for a vote round, prioritizing Circle-participating images.

    Circle prioritization:
    1. Get all Circle-mates for the player
    2. Identify images with >= 5 unseen captions where at least 1 is from a Circle-mate
    3. If Circle-participating images exist, pick randomly from those
    4. Otherwise, fall back to global selection
    """
    from backend.services.mm.circle_service import MMCircleService

    captions_per_round = config.get("mm_captions_per_round", 5)

    # Get Circle-mates
    circle_mate_ids = await MMCircleService.get_circle_mates(session, player_id)

    # Build base query for unseen caption count
    unseen_captions_subquery = (
        select(
            MMCaption.image_id,
            func.count(MMCaption.caption_id).label("unseen_count"),
            func.sum(
                case(
                    (MMCaption.author_player_id.in_(circle_mate_ids), 1),
                    else_=0
                )
            ).label("circle_caption_count") if circle_mate_ids else literal(0).label("circle_caption_count")
        )
        .outerjoin(
            MMCaptionSeen,
            and_(
                MMCaptionSeen.caption_id == MMCaption.caption_id,
                MMCaptionSeen.player_id == player_id
            )
        )
        .where(
            and_(
                MMCaption.status == "active",
                or_(
                    MMCaption.author_player_id.is_(None),  # System captions
                    MMCaption.author_player_id != player_id  # Not own captions
                ),
                MMCaptionSeen.player_id.is_(None)  # Not seen
            )
        )
        .group_by(MMCaption.image_id)
        .having(func.count(MMCaption.caption_id) >= captions_per_round)
        .subquery()
    )

    # Step 1: Try to get Circle-participating images
    if circle_mate_ids:
        circle_images_query = (
            select(MMImage)
            .join(unseen_captions_subquery, MMImage.image_id == unseen_captions_subquery.c.image_id)
            .where(
                and_(
                    MMImage.status == "active",
                    unseen_captions_subquery.c.circle_caption_count > 0
                )
            )
            .order_by(func.random())
            .limit(10)
        )

        circle_images_result = await session.execute(circle_images_query)
        circle_images = list(circle_images_result.scalars().all())

        if circle_images:
            import random
            return random.choice(circle_images)

    # Step 2: Fall back to global selection
    global_images_query = (
        select(MMImage)
        .join(unseen_captions_subquery, MMImage.image_id == unseen_captions_subquery.c.image_id)
        .where(MMImage.status == "active")
        .order_by(func.random())
        .limit(10)
    )

    global_images_result = await session.execute(global_images_query)
    global_images = list(global_images_result.scalars().all())

    if not global_images:
        return None

    import random
    return random.choice(global_images)
```

**Changes to `_select_captions_for_round()` method:**

```python
async def _select_captions_for_round(
    self,
    session: AsyncSession,
    image_id: str,
    player_id: str,
    count: int = 5
) -> list[MMCaption]:
    """
    Select captions for a round with Circle-first prioritization.

    Algorithm:
    1. Get all eligible captions (not seen, not own, active)
    2. Partition into Circle captions vs Global captions
    3. Fill slots Circle-first:
       - If >= 5 Circle captions: pick 5 from Circle pool
       - If 0 < k < 5 Circle captions: pick all k Circle + (5-k) Global
       - If 0 Circle captions: pick 5 Global
    4. Within each pool, use quality-weighted random selection
    """
    from backend.services.mm.circle_service import MMCircleService

    # Get Circle-mates
    circle_mate_ids = await MMCircleService.get_circle_mates(session, player_id)

    # Get all eligible captions
    eligible_query = (
        select(MMCaption)
        .outerjoin(
            MMCaptionSeen,
            and_(
                MMCaptionSeen.caption_id == MMCaption.caption_id,
                MMCaptionSeen.player_id == player_id
            )
        )
        .where(
            and_(
                MMCaption.image_id == image_id,
                MMCaption.status == "active",
                or_(
                    MMCaption.author_player_id.is_(None),
                    MMCaption.author_player_id != player_id
                ),
                MMCaptionSeen.player_id.is_(None)
            )
        )
    )

    result = await session.execute(eligible_query)
    all_eligible = list(result.scalars().all())

    if len(all_eligible) < count:
        raise ValueError(f"Insufficient eligible captions for image {image_id}")

    # Partition into Circle vs Global
    circle_captions = []
    global_captions = []

    for caption in all_eligible:
        if caption.author_player_id and caption.author_player_id in circle_mate_ids:
            circle_captions.append(caption)
        else:
            global_captions.append(caption)

    # Fill slots based on Circle caption availability
    selected_captions = []
    circle_count = len(circle_captions)

    if circle_count >= count:
        # Case A: >= 5 Circle captions available
        selected_captions = self._weighted_random_sample(circle_captions, count)
    elif circle_count > 0:
        # Case B: 0 < k < 5 Circle captions
        selected_captions.extend(circle_captions)  # Add all Circle captions
        remaining = count - circle_count
        selected_captions.extend(
            self._weighted_random_sample(global_captions, remaining)
        )
    else:
        # Case C: 0 Circle captions
        selected_captions = self._weighted_random_sample(global_captions, count)

    return selected_captions


def _weighted_random_sample(
    self,
    captions: list[MMCaption],
    count: int
) -> list[MMCaption]:
    """
    Select captions using quality-weighted random sampling.
    Uses quality_score as weight: (picks + 1) / (shows + 3)
    """
    import random

    if len(captions) <= count:
        return captions

    # Calculate weights
    weights = [caption.quality_score for caption in captions]

    # Handle edge case of all zero weights
    if sum(weights) == 0:
        weights = [1.0] * len(captions)

    # Sample without replacement
    selected = random.choices(
        captions,
        weights=weights,
        k=min(count, len(captions))
    )

    # Ensure no duplicates (choices can repeat)
    seen = set()
    unique_selected = []
    for caption in selected:
        if caption.caption_id not in seen:
            seen.add(caption.caption_id)
            unique_selected.append(caption)

    # If we need more due to duplicates, sample remaining
    if len(unique_selected) < count:
        remaining_captions = [c for c in captions if c.caption_id not in seen]
        remaining_weights = [c.quality_score for c in remaining_captions]
        if sum(remaining_weights) == 0:
            remaining_weights = [1.0] * len(remaining_captions)

        additional = random.choices(
            remaining_captions,
            weights=remaining_weights,
            k=count - len(unique_selected)
        )
        unique_selected.extend(additional)

    return unique_selected[:count]
```

#### Modify: `/backend/services/mm/vote_service.py`

**Changes to `_distribute_caption_payouts()` method:**

Add Circle-mate checking for system bonus suppression.

```python
async def _distribute_caption_payouts(
    self,
    session: AsyncSession,
    chosen_caption: MMCaption,
    round_entry_cost: int,
    writer_bonus_multiplier: float,
    voter_player_id: str,
    round_id: str
) -> None:
    """
    Distribute payouts to caption authors with system bonus suppression for Circle-mates.

    System bonus suppression rule:
    - If voter is a Circle-mate of any earning author, suppress the 3x system bonus for that author
    - Base payout (from entry cost) is always given
    """
    from backend.services.mm.circle_service import MMCircleService

    # Get Circle-mates of voter
    circle_mate_ids = await MMCircleService.get_circle_mates(session, voter_player_id)

    # Calculate base payout from entry cost
    base_payout = round_entry_cost  # Default 5 MC

    # Calculate total writer bonus (minted by system)
    total_writer_bonus = int(round_entry_cost * writer_bonus_multiplier)  # Default 15 MC

    # Determine earning authors based on caption kind
    if chosen_caption.kind == "original":
        # Original caption: 100% to author
        authors = [
            {
                "player_id": chosen_caption.author_player_id,
                "base_share": base_payout,
                "bonus_share": total_writer_bonus,
                "caption_id": chosen_caption.caption_id
            }
        ]
    elif chosen_caption.kind == "riff":
        # Riff caption: split between riff author and parent author
        riff_split_ratio = 0.6  # Configurable

        riff_base = int(base_payout * riff_split_ratio)
        parent_base = base_payout - riff_base

        riff_bonus = int(total_writer_bonus * riff_split_ratio)
        parent_bonus = total_writer_bonus - riff_bonus

        # Get parent caption
        parent_caption = await session.get(MMCaption, chosen_caption.parent_caption_id)

        authors = [
            {
                "player_id": chosen_caption.author_player_id,
                "base_share": riff_base,
                "bonus_share": riff_bonus,
                "caption_id": chosen_caption.caption_id
            },
            {
                "player_id": parent_caption.author_player_id if parent_caption else None,
                "base_share": parent_base,
                "bonus_share": parent_bonus,
                "caption_id": parent_caption.caption_id if parent_caption else None
            }
        ]
    else:
        raise ValueError(f"Unknown caption kind: {chosen_caption.kind}")

    # Distribute payouts with Circle-mate bonus suppression
    for author_info in authors:
        author_id = author_info["player_id"]
        caption_id = author_info["caption_id"]

        # Skip if author is None (system caption)
        if not author_id:
            continue

        # Check if author is a Circle-mate of voter
        is_circle_mate = author_id in circle_mate_ids

        # Apply bonus suppression rule
        base_amount = author_info["base_share"]
        bonus_amount = 0 if is_circle_mate else author_info["bonus_share"]

        total_gross_payout = base_amount + bonus_amount

        # Apply wallet/vault split based on caption's lifetime earnings
        caption = await session.get(MMCaption, caption_id)
        wallet_amount, vault_amount = await self._calculate_wallet_vault_split(
            caption=caption,
            gross_payout=total_gross_payout
        )

        # Create wallet transaction
        if wallet_amount > 0:
            await self._create_transaction(
                session=session,
                player_id=author_id,
                amount=wallet_amount,
                transaction_type="mm_caption_payout_wallet",
                reference_id=round_id,
                wallet_type="wallet"
            )

        # Create vault transaction
        if vault_amount > 0:
            await self._create_transaction(
                session=session,
                player_id=author_id,
                amount=vault_amount,
                transaction_type="mm_caption_payout_vault",
                reference_id=round_id,
                wallet_type="vault"
            )

        # Update caption earnings stats
        caption.lifetime_earnings_gross += total_gross_payout
        caption.lifetime_to_wallet += wallet_amount
        caption.lifetime_to_vault += vault_amount
```

---

## Frontend Implementation

### Phase 4: API Client

#### File: `/mm_frontend/src/api/client.ts` (Add methods)

```typescript
// Circle management methods

export const createCircle = async (
  name: string,
  description?: string
): Promise<Circle> => {
  const response = await apiClient.post('/circles', { name, description });
  return response.data;
};

export const listAllCircles = async (
  limit: number = 100,
  offset: number = 0
): Promise<Circle[]> => {
  const response = await apiClient.get('/circles', { params: { limit, offset } });
  return response.data;
};

export const getMyCircles = async (): Promise<Circle[]> => {
  const response = await apiClient.get('/circles/my-circles');
  return response.data;
};

export const getCircleDetails = async (circleId: string): Promise<CircleDetails> => {
  const response = await apiClient.get(`/circles/${circleId}`);
  return response.data;
};

export const requestToJoinCircle = async (circleId: string): Promise<void> => {
  await apiClient.post(`/circles/${circleId}/join-request`);
};

export const addMemberToCircle = async (
  circleId: string,
  playerIdToAdd: string
): Promise<void> => {
  await apiClient.post(`/circles/${circleId}/members`, { player_id: playerIdToAdd });
};

export const removeMemberFromCircle = async (
  circleId: string,
  playerIdToRemove: string
): Promise<void> => {
  await apiClient.delete(`/circles/${circleId}/members/${playerIdToRemove}`);
};

export const leaveCircle = async (circleId: string): Promise<void> => {
  const response = await apiClient.get('/player/me');
  const myPlayerId = response.data.player_id;
  await apiClient.delete(`/circles/${circleId}/members/${myPlayerId}`);
};

export const approveJoinRequest = async (
  circleId: string,
  requestId: string
): Promise<void> => {
  await apiClient.post(`/circles/${circleId}/join-requests/${requestId}/approve`);
};

export const denyJoinRequest = async (
  circleId: string,
  requestId: string
): Promise<void> => {
  await apiClient.post(`/circles/${circleId}/join-requests/${requestId}/deny`);
};
```

#### File: `/mm_frontend/src/api/types.ts` (Add types)

```typescript
export interface Circle {
  circle_id: string;
  name: string;
  description: string | null;
  created_by_player_id: string;
  created_at: string;
  updated_at: string;
  member_count: number;
  is_public: boolean;
  status: string;
}

export interface CircleMember {
  circle_id: string;
  player_id: string;
  joined_at: string;
  role: 'admin' | 'member';
  player?: {
    player_id: string;
    username: string;
  };
}

export interface CircleJoinRequest {
  request_id: string;
  circle_id: string;
  player_id: string;
  requested_at: string;
  status: 'pending' | 'approved' | 'denied';
  resolved_at: string | null;
  resolved_by_player_id: string | null;
  player?: {
    player_id: string;
    username: string;
  };
}

export interface CircleDetails extends Circle {
  members: CircleMember[];
  join_requests: CircleJoinRequest[];
  is_member: boolean;
  is_admin: boolean;
}
```

---

### Phase 5: Frontend Pages

#### File: `/mm_frontend/src/pages/Circles.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listAllCircles, getMyCircles, createCircle, requestToJoinCircle } from '../api/client';
import { Circle } from '../api/types';
import Header from '../components/Header';
import SubHeader from '../components/SubHeader';
import LoadingSpinner from '../components/LoadingSpinner';

const Circles: React.FC = () => {
  const navigate = useNavigate();
  const [myCircles, setMyCircles] = useState<Circle[]>([]);
  const [allCircles, setAllCircles] = useState<Circle[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newCircleName, setNewCircleName] = useState('');
  const [newCircleDescription, setNewCircleDescription] = useState('');

  useEffect(() => {
    loadCircles();
  }, []);

  const loadCircles = async () => {
    setLoading(true);
    try {
      const [my, all] = await Promise.all([
        getMyCircles(),
        listAllCircles()
      ]);
      setMyCircles(my);
      setAllCircles(all);
    } catch (error) {
      console.error('Failed to load circles:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCircle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCircleName.trim()) return;

    try {
      const created = await createCircle(
        newCircleName.trim(),
        newCircleDescription.trim() || undefined
      );
      setShowCreateForm(false);
      setNewCircleName('');
      setNewCircleDescription('');
      navigate(`/circles/${created.circle_id}`);
    } catch (error) {
      console.error('Failed to create circle:', error);
      alert('Failed to create circle. The name may already be taken.');
    }
  };

  const handleRequestJoin = async (circleId: string) => {
    try {
      await requestToJoinCircle(circleId);
      alert('Join request sent!');
      await loadCircles();
    } catch (error) {
      console.error('Failed to request join:', error);
      alert('Failed to send join request.');
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <SubHeader />

      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Circles</h1>

        {/* My Circles Section */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">My Circles</h2>
          {myCircles.length === 0 ? (
            <p className="text-gray-500">You haven't joined any Circles yet.</p>
          ) : (
            <div className="grid gap-4">
              {myCircles.map(circle => (
                <div
                  key={circle.circle_id}
                  className="bg-white p-4 rounded-lg shadow cursor-pointer hover:shadow-md transition"
                  onClick={() => navigate(`/circles/${circle.circle_id}`)}
                >
                  <h3 className="text-xl font-semibold">{circle.name}</h3>
                  {circle.description && (
                    <p className="text-gray-600 mt-1">{circle.description}</p>
                  )}
                  <p className="text-sm text-gray-500 mt-2">
                    {circle.member_count} {circle.member_count === 1 ? 'member' : 'members'}
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Create Circle Section */}
        <section className="mb-8">
          <h2 className="text-2xl font-semibold mb-4">Create a Circle</h2>
          {!showCreateForm ? (
            <button
              onClick={() => setShowCreateForm(true)}
              className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition"
            >
              + New Circle
            </button>
          ) : (
            <form onSubmit={handleCreateCircle} className="bg-white p-4 rounded-lg shadow">
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Circle Name *</label>
                <input
                  type="text"
                  value={newCircleName}
                  onChange={(e) => setNewCircleName(e.target.value)}
                  maxLength={100}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="Enter circle name"
                  required
                />
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2">Description (optional)</label>
                <textarea
                  value={newCircleDescription}
                  onChange={(e) => setNewCircleDescription(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg"
                  placeholder="Enter circle description"
                  rows={3}
                />
              </div>
              <div className="flex gap-2">
                <button
                  type="submit"
                  className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition"
                >
                  Create
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateForm(false);
                    setNewCircleName('');
                    setNewCircleDescription('');
                  }}
                  className="bg-gray-300 text-gray-700 px-6 py-2 rounded-lg hover:bg-gray-400 transition"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </section>

        {/* Discover Circles Section */}
        <section>
          <h2 className="text-2xl font-semibold mb-4">Discover Circles</h2>
          <div className="grid gap-4">
            {allCircles.map(circle => {
              const isMember = myCircles.some(c => c.circle_id === circle.circle_id);
              return (
                <div
                  key={circle.circle_id}
                  className="bg-white p-4 rounded-lg shadow"
                >
                  <div className="flex justify-between items-start">
                    <div
                      className="flex-1 cursor-pointer"
                      onClick={() => navigate(`/circles/${circle.circle_id}`)}
                    >
                      <h3 className="text-xl font-semibold">{circle.name}</h3>
                      {circle.description && (
                        <p className="text-gray-600 mt-1">{circle.description}</p>
                      )}
                      <p className="text-sm text-gray-500 mt-2">
                        {circle.member_count} {circle.member_count === 1 ? 'member' : 'members'}
                      </p>
                    </div>
                    {!isMember && (
                      <button
                        onClick={() => handleRequestJoin(circle.circle_id)}
                        className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition text-sm"
                      >
                        Request to Join
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
};

export default Circles;
```

#### File: `/mm_frontend/src/pages/CircleDetail.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getCircleDetails,
  addMemberToCircle,
  removeMemberFromCircle,
  leaveCircle,
  approveJoinRequest,
  denyJoinRequest
} from '../api/client';
import { CircleDetails, CircleMember, CircleJoinRequest } from '../api/types';
import Header from '../components/Header';
import SubHeader from '../components/SubHeader';
import LoadingSpinner from '../components/LoadingSpinner';

const CircleDetail: React.FC = () => {
  const { circleId } = useParams<{ circleId: string }>();
  const navigate = useNavigate();
  const [circle, setCircle] = useState<CircleDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [addMemberUsername, setAddMemberUsername] = useState('');

  useEffect(() => {
    if (circleId) {
      loadCircleDetails();
    }
  }, [circleId]);

  const loadCircleDetails = async () => {
    if (!circleId) return;

    setLoading(true);
    try {
      const details = await getCircleDetails(circleId);
      setCircle(details);
    } catch (error) {
      console.error('Failed to load circle details:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!circleId || !addMemberUsername.trim()) return;

    try {
      // Note: Backend would need to resolve username to player_id
      // For MVP, we might use player_id directly or add username lookup endpoint
      await addMemberToCircle(circleId, addMemberUsername.trim());
      setAddMemberUsername('');
      await loadCircleDetails();
    } catch (error) {
      console.error('Failed to add member:', error);
      alert('Failed to add member. Check the username and try again.');
    }
  };

  const handleRemoveMember = async (playerId: string) => {
    if (!circleId) return;
    if (!confirm('Are you sure you want to remove this member?')) return;

    try {
      await removeMemberFromCircle(circleId, playerId);
      await loadCircleDetails();
    } catch (error) {
      console.error('Failed to remove member:', error);
      alert('Failed to remove member.');
    }
  };

  const handleLeaveCircle = async () => {
    if (!circleId) return;
    if (!confirm('Are you sure you want to leave this Circle?')) return;

    try {
      await leaveCircle(circleId);
      navigate('/circles');
    } catch (error) {
      console.error('Failed to leave circle:', error);
      alert('Failed to leave circle.');
    }
  };

  const handleApproveRequest = async (requestId: string) => {
    if (!circleId) return;

    try {
      await approveJoinRequest(circleId, requestId);
      await loadCircleDetails();
    } catch (error) {
      console.error('Failed to approve request:', error);
      alert('Failed to approve join request.');
    }
  };

  const handleDenyRequest = async (requestId: string) => {
    if (!circleId) return;

    try {
      await denyJoinRequest(circleId, requestId);
      await loadCircleDetails();
    } catch (error) {
      console.error('Failed to deny request:', error);
      alert('Failed to deny join request.');
    }
  };

  if (loading || !circle) {
    return <LoadingSpinner />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <SubHeader />

      <div className="max-w-4xl mx-auto p-6">
        <button
          onClick={() => navigate('/circles')}
          className="text-blue-600 hover:underline mb-4"
        >
          ← Back to Circles
        </button>

        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <h1 className="text-3xl font-bold mb-2">{circle.name}</h1>
          {circle.description && (
            <p className="text-gray-600 mb-4">{circle.description}</p>
          )}
          <p className="text-sm text-gray-500">
            {circle.member_count} {circle.member_count === 1 ? 'member' : 'members'}
          </p>

          {circle.is_member && !circle.is_admin && (
            <button
              onClick={handleLeaveCircle}
              className="mt-4 bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition"
            >
              Leave Circle
            </button>
          )}
        </div>

        {/* Admin: Add Member */}
        {circle.is_admin && (
          <section className="bg-white p-6 rounded-lg shadow mb-6">
            <h2 className="text-2xl font-semibold mb-4">Add Member</h2>
            <form onSubmit={handleAddMember} className="flex gap-2">
              <input
                type="text"
                value={addMemberUsername}
                onChange={(e) => setAddMemberUsername(e.target.value)}
                placeholder="Enter username or player ID"
                className="flex-1 px-3 py-2 border rounded-lg"
              />
              <button
                type="submit"
                className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition"
              >
                Add
              </button>
            </form>
          </section>
        )}

        {/* Admin: Pending Join Requests */}
        {circle.is_admin && circle.join_requests.length > 0 && (
          <section className="bg-white p-6 rounded-lg shadow mb-6">
            <h2 className="text-2xl font-semibold mb-4">Pending Join Requests</h2>
            <div className="space-y-2">
              {circle.join_requests.map(request => (
                <div
                  key={request.request_id}
                  className="flex justify-between items-center p-3 border rounded-lg"
                >
                  <span>{request.player?.username || 'Unknown user'}</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleApproveRequest(request.request_id)}
                      className="bg-green-600 text-white px-4 py-1 rounded hover:bg-green-700 transition text-sm"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleDenyRequest(request.request_id)}
                      className="bg-red-600 text-white px-4 py-1 rounded hover:bg-red-700 transition text-sm"
                    >
                      Deny
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Members List */}
        <section className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-2xl font-semibold mb-4">Members</h2>
          <div className="space-y-2">
            {circle.members.map(member => (
              <div
                key={member.player_id}
                className="flex justify-between items-center p-3 border rounded-lg"
              >
                <div>
                  <span className="font-medium">{member.player?.username || 'Unknown'}</span>
                  {member.role === 'admin' && (
                    <span className="ml-2 text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                      Admin
                    </span>
                  )}
                </div>
                {circle.is_admin && member.role !== 'admin' && (
                  <button
                    onClick={() => handleRemoveMember(member.player_id)}
                    className="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 transition text-sm"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
};

export default CircleDetail;
```

---

## Migration Strategy

### Alembic Migration File

Create: `/backend/migrations/versions/YYYYMMDD_HHMMSS_add_circles_tables.py`

```python
"""add circles tables

Revision ID: abc123def456
Revises: <previous_revision>
Create Date: 2024-XX-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from backend.migrations.util import get_uuid_type, get_uuid_default, get_timestamp_default

# revision identifiers, used by Alembic.
revision = 'abc123def456'
down_revision = '<previous_revision>'  # Replace with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    # Create mm_circles table
    op.create_table(
        'mm_circles',
        sa.Column('circle_id', get_uuid_type(), nullable=False, server_default=get_uuid_default()),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_player_id', get_uuid_type(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.Column('member_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.ForeignKeyConstraint(['created_by_player_id'], ['mm_players.player_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('circle_id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_mm_circles_created_by', 'mm_circles', ['created_by_player_id'])
    op.create_index('idx_mm_circles_status', 'mm_circles', ['status'])
    op.create_index('idx_mm_circles_name_lower', 'mm_circles', [sa.text('LOWER(name)')])

    # Create mm_circle_members table
    op.create_table(
        'mm_circle_members',
        sa.Column('circle_id', get_uuid_type(), nullable=False),
        sa.Column('player_id', get_uuid_type(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='member'),
        sa.ForeignKeyConstraint(['circle_id'], ['mm_circles.circle_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['mm_players.player_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('circle_id', 'player_id'),
        sa.UniqueConstraint('circle_id', 'player_id', name='uq_mm_circle_member')
    )
    op.create_index('idx_mm_circle_members_player_id', 'mm_circle_members', ['player_id'])
    op.create_index('idx_mm_circle_members_joined_at', 'mm_circle_members', ['circle_id', sa.text('joined_at DESC')])

    # Create mm_circle_join_requests table
    op.create_table(
        'mm_circle_join_requests',
        sa.Column('request_id', get_uuid_type(), nullable=False, server_default=get_uuid_default()),
        sa.Column('circle_id', get_uuid_type(), nullable=False),
        sa.Column('player_id', get_uuid_type(), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False, server_default=get_timestamp_default()),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by_player_id', get_uuid_type(), nullable=True),
        sa.ForeignKeyConstraint(['circle_id'], ['mm_circles.circle_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['player_id'], ['mm_players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resolved_by_player_id'], ['mm_players.player_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('request_id'),
        sa.UniqueConstraint('circle_id', 'player_id', name='uq_mm_circle_join_request')
    )
    op.create_index('idx_mm_circle_join_requests_circle_status', 'mm_circle_join_requests', ['circle_id', 'status'])
    op.create_index('idx_mm_circle_join_requests_player', 'mm_circle_join_requests', ['player_id'])


def downgrade():
    op.drop_table('mm_circle_join_requests')
    op.drop_table('mm_circle_members')
    op.drop_table('mm_circles')
```

---

## Testing Considerations

### Key Test Scenarios

1. **Circle Creation & Membership:**
   - Create circle successfully
   - Prevent duplicate circle names
   - Creator automatically becomes admin member
   - Add/remove members as admin
   - Leave circle as member

2. **Join Requests:**
   - Request to join circle
   - Prevent duplicate join requests
   - Approve join request (adds member)
   - Deny join request
   - Can't request if already member

3. **Circle-mate Relationships:**
   - Two players in same circle are Circle-mates
   - Players in different circles are not Circle-mates
   - Multi-membership: player in Circle A and B sees all members as Circle-mates

4. **Image Prioritization:**
   - Image with Circle-mate captions selected first
   - Falls back to global when no Circle images available
   - Random selection within Circle-participating images

5. **Caption Prioritization:**
   - All 5 Circle captions shown when ≥5 available
   - Mixed Circle + Global when 0 < k < 5
   - Global only when 0 Circle captions
   - Quality weighting works within each pool

6. **System Bonus Suppression:**
   - System bonus (3×) suppressed when voting for Circle-mate
   - Base 5 MC payout always given
   - Riff/parent split: each author evaluated separately
   - Suppression only for Circle-mates, not global players

7. **Edge Cases:**
   - Player with no Circles (global experience)
   - Empty Circle (no eligible content)
   - Player leaves Circle (immediately not Circle-mates)
   - All Circle captions already seen (falls back to global)
   - System/bot captions never Circle-mates

### Integration Test Examples

```python
# Test: Circle-mate content prioritization
async def test_circle_mate_caption_prioritization():
    # Create 2 players in a Circle
    player1 = await create_test_player()
    player2 = await create_test_player()
    circle = await circle_service.create_circle(session, player1.player_id, "Test Circle")
    await circle_service.add_member(session, circle.circle_id, player2.player_id, player1.player_id)

    # Create image with 5 Circle-mate captions + 5 global captions
    image = await create_test_image()
    circle_captions = [
        await create_caption(image.image_id, player2.player_id) for _ in range(5)
    ]
    global_captions = [
        await create_caption(image.image_id, None) for _ in range(5)  # System captions
    ]

    # Start vote round as player1
    round_data = await game_service.start_vote_round(session, player1.player_id)

    # Verify all 5 shown captions are from Circle-mate
    shown_caption_ids = round_data["caption_ids_shown"]
    circle_caption_ids = {c.caption_id for c in circle_captions}
    assert all(cid in circle_caption_ids for cid in shown_caption_ids)


# Test: System bonus suppression
async def test_system_bonus_suppression_for_circle_mates():
    # Create 2 Circle-mates
    player1 = await create_test_player()
    player2 = await create_test_player()
    circle = await circle_service.create_circle(session, player1.player_id, "Test Circle")
    await circle_service.add_member(session, circle.circle_id, player2.player_id, player1.player_id)

    # Create caption by player2
    image = await create_test_image()
    caption = await create_caption(image.image_id, player2.player_id)

    # Player1 votes for player2's caption
    round = await create_test_vote_round(player1.player_id, image.image_id, [caption.caption_id])
    await vote_service.submit_vote(session, round.round_id, caption.caption_id, player1.player_id)

    # Check player2's transactions
    transactions = await get_transactions(player2.player_id)

    # Base payout should exist: 5 MC
    base_tx = [t for t in transactions if t.type == "mm_caption_payout_wallet"][0]
    assert base_tx.amount == 5

    # System bonus should NOT exist (suppressed)
    bonus_tx = [t for t in transactions if "bonus" in t.type]
    assert len(bonus_tx) == 0
```

---

## Implementation Phases

### Week 1: Database & Models ✅
- [x] Create mm_circles, mm_circle_members, mm_circle_join_requests tables
- [x] Implement SQLAlchemy models
- [x] Create Alembic migration
- [x] Run migration locally and verify schema

### Week 2: Service Layer
- [ ] Implement MMCircleService (CRUD operations)
- [ ] Add `get_circle_mates()` and `is_circle_mate()` utilities
- [ ] Add admin management functions
- [ ] Unit test service layer

### Week 3: Game Logic Integration
- [ ] Modify image selection in MMGameService
- [ ] Modify caption selection in MMGameService
- [ ] Implement system bonus suppression in MMVoteService
- [ ] Integration tests for prioritization logic

### Week 4: API Layer
- [ ] Create Circles router (`/backend/routers/mm/circles.py`)
- [ ] Add Pydantic schemas for requests/responses
- [ ] Integrate with authentication (use existing `get_current_player`)
- [ ] API endpoint tests

### Week 5: Frontend
- [ ] Create Circles page (`/mm_frontend/src/pages/Circles.tsx`)
- [ ] Create CircleDetail page (`/mm_frontend/src/pages/CircleDetail.tsx`)
- [ ] Add API client methods
- [ ] Add Circle badge to VoteRound results
- [ ] Update navigation to include Circles link
- [ ] Frontend integration tests

### Week 6: Testing & Polish
- [ ] End-to-end tests
- [ ] Performance optimization (query tuning)
- [ ] Error handling improvements
- [ ] Documentation updates
- [ ] Beta testing

---

## Rollout Strategy

1. **Phase 1: Backend Only (Internal Testing)**
   - Deploy database migration
   - Deploy backend services
   - Test with Postman/cURL
   - Verify no regressions in existing gameplay

2. **Phase 2: Frontend Alpha (Limited Users)**
   - Deploy frontend
   - Enable for 5-10 beta testers
   - Gather feedback on UX
   - Monitor Circle usage patterns

3. **Phase 3: Public Beta**
   - Open to all users
   - Monitor performance metrics
   - Adjust Circle prioritization weights if needed

4. **Phase 4: Full Launch**
   - Announce feature
   - Create onboarding tutorial
   - Monitor engagement metrics

---

## Performance Considerations

### Database Optimization

1. **Circle-mate Lookup Caching:**
   - Cache `get_circle_mates()` results per player for 5 minutes
   - Invalidate on Circle membership changes

2. **Query Optimization:**
   - Use `EXISTS` subqueries instead of `JOIN` where possible
   - Ensure all foreign keys have indexes
   - Use `EXPLAIN ANALYZE` to verify query plans

3. **Denormalization:**
   - `member_count` on `mm_circles` avoids expensive `COUNT(*)` queries
   - Consider adding `circle_count` to players if needed

### Frontend Optimization

1. **Lazy Loading:**
   - Load Circle details only when viewing detail page
   - Paginate member lists for large Circles

2. **Optimistic Updates:**
   - Update UI immediately for join requests, refresh in background

3. **Smart Polling:**
   - Poll for new join requests only on admin's Circle detail page

---

## Future Enhancements (Post-MVP)

1. **Private Circles:** Invite-only Circles not shown in discovery
2. **Circle Chat:** Built-in messaging for Circle members
3. **Circle Leaderboards:** Aggregate stats for Circle performance
4. **Circle Quests:** Group challenges with shared rewards
5. **Multi-Admin Support:** Allow multiple admins per Circle
6. **Circle Rename:** Admin can rename Circle
7. **Circle Archives:** Deactivate Circle without deleting
8. **Circle Badges:** Custom profile badges for Circle membership
9. **Circle Analytics:** Track engagement, content quality by Circle

---

## Conclusion

This plan provides a complete roadmap for implementing the Circles feature in MemeMint. The phased approach allows for incremental delivery and testing, while the detailed technical specifications enable immediate development.

Key success metrics:
- Circle creation rate
- Average members per Circle
- % of rounds featuring Circle content
- Player retention in Circles
- Engagement uplift for Circle members vs. non-members

Let's build it! 🚀
