from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base
from backend.models.base import get_uuid_column

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
        ForeignKey("players.player_id", ondelete="CASCADE"),
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
