"""IR ResultView model."""
from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class IRResultView(Base):
    """Result viewing tracking for prize claiming."""

    __tablename__ = "ir_result_views"

    view_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    set_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id = get_uuid_column(
        ForeignKey("ir_players.player_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    result_viewed = Column(Boolean, default=False, nullable=False, index=True)
    payout_amount = Column(Integer, nullable=False)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    first_viewed_at = Column(DateTime(timezone=True), nullable=True)
    result_viewed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("player_id", "set_id", name="uq_ir_result_view_player_set"),
        Index("ix_ir_result_view_set", set_id),
        Index("ix_ir_result_view_player", player_id),
        Index("ix_ir_result_view_result_viewed", result_viewed),
    )

    # Relationships
    set = relationship("IRBackronymSet", back_populates="result_views")
    player = relationship("IRPlayer", back_populates="result_views")
