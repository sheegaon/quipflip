from datetime import datetime, timezone
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base
from backend.models.base import get_uuid_column

if TYPE_CHECKING:
    from .player import MMPlayer
    from .circle_member import MMCircleMember
    from .circle_join_request import MMCircleJoinRequest


class MMCircle(Base):
    """MemeMint Circle - persistent social group"""
    __tablename__ = "mm_circles"

    circle_id: Mapped[str] = get_uuid_column(primary_key=True, default=uuid.uuid4)
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
