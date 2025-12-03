"""ThinkLink challenge model (v2 - stub structure).

This model provides the data structure for head-to-head challenge mode
in ThinkLink v2. v1 implementation focuses on solo play only.

Challenge mode: Two players compete simultaneously on the same prompt
with a shared snapshot of answers, racing against a 5-minute timer.
"""
from sqlalchemy import Column, ForeignKey, String, Integer, DateTime, Float, CheckConstraint
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class TLChallenge(Base):
    """ThinkLink head-to-head challenge (v2 feature).

    NOTE: This table structure is created for v2 support but no logic
    is implemented in v1. v1 focuses on solo gameplay only.
    """

    __tablename__ = "tl_challenge"

    challenge_id = get_uuid_column(primary_key=True)
    prompt_id = get_uuid_column(
        ForeignKey("tl_prompt.prompt_id", ondelete="CASCADE"),
        nullable=False
    )
    initiator_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False
    )
    opponent_player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False
    )
    initiator_round_id = get_uuid_column(
        ForeignKey("tl_round.round_id", ondelete="SET NULL"),
        nullable=True
    )
    opponent_round_id = get_uuid_column(
        ForeignKey("tl_round.round_id", ondelete="SET NULL"),
        nullable=True
    )

    status = Column(String(20), default='pending', nullable=False)  # pending, active, completed, cancelled, expired
    time_limit_seconds = Column(Integer, default=300, nullable=False)  # 5 minutes default

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Results
    winner_player_id = get_uuid_column(nullable=True)  # NULL for ties or double-bust
    initiator_final_coverage = Column(Float, nullable=True)
    opponent_final_coverage = Column(Float, nullable=True)
    initiator_gross_payout = Column(Integer, nullable=True)
    opponent_gross_payout = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'cancelled', 'expired')",
            name='valid_challenge_status'
        ),
    )

    def __repr__(self):
        return (f"<TLChallenge(challenge_id={self.challenge_id}, "
                f"status={self.status})>")
