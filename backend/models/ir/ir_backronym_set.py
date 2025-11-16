"""IR BackronymSet model."""
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Index,
)
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column
from backend.models.ir.enums import IRSetStatus, IRMode


class IRBackronymSet(Base):
    """Represents a backronym set waiting for entries and votes."""

    __tablename__ = "ir_backronym_sets"

    set_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    word = Column(String(5), nullable=False)  # 3-5 letter word
    mode = Column(String(10), nullable=False, default=IRMode.RAPID)  # standard, rapid
    status = Column(
        String(10), nullable=False, default=IRSetStatus.OPEN
    )  # open, voting, finalized
    entry_count = Column(Integer, default=0, nullable=False)
    vote_count = Column(Integer, default=0, nullable=False)
    non_participant_vote_count = Column(Integer, default=0, nullable=False)
    total_pool = Column(Integer, default=0, nullable=False)
    vote_contributions = Column(Integer, default=0, nullable=False)
    non_participant_payouts_paid = Column(Integer, default=0, nullable=False)
    creator_final_pool = Column(Integer, default=0, nullable=False)
    first_participant_joined_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    last_human_entry_at = Column(DateTime(timezone=True), nullable=True)
    last_human_vote_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ir_set_status_created", status, created_at),
        Index("ix_ir_set_mode_status", mode, status),
        Index("ix_ir_set_finalized_at", finalized_at),
        Index("ix_ir_set_word_status", word, status),
        Index("ix_ir_set_last_human_vote", last_human_vote_at),
    )

    # Relationships
    entries = relationship(
        "IRBackronymEntry", back_populates="set", cascade="all, delete-orphan"
    )
    votes = relationship(
        "IRBackronymVote", back_populates="set", cascade="all, delete-orphan"
    )
    observer_guard = relationship(
        "IRBackronymObserverGuard",
        back_populates="set",
        uselist=False,
        cascade="all, delete-orphan",
    )
    result_views = relationship(
        "IRResultView", back_populates="set", cascade="all, delete-orphan"
    )
