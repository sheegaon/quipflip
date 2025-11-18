"""IR BackronymObserverGuard model."""
from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base
from backend.models.base import get_uuid_column


class BackronymObserverGuard(Base):
    """Eligibility snapshot for non-participant voters."""

    __tablename__ = "ir_backronym_observer_guards"

    set_id = get_uuid_column(
        ForeignKey("ir_backronym_sets.set_id", ondelete="CASCADE"),
        primary_key=True,
    )
    first_participant_created_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    set = relationship("BackronymSet", back_populates="observer_guard")
