from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base
from backend.models.base import get_uuid_column

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
