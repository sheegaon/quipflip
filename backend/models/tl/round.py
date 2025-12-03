"""ThinkLink round model."""
from sqlalchemy import Column, ForeignKey, String, Integer, DateTime, Float, JSON, CheckConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from backend.database import Base
from backend.models.base import get_uuid_column


class TLRound(Base):
    """ThinkLink round.

    Represents a single round of gameplay for a player on a prompt.
    Snapshot-based: freezes answer corpus at round start.
    """

    __tablename__ = "tl_round"

    round_id = get_uuid_column(primary_key=True)
    player_id = get_uuid_column(
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False
    )
    prompt_id = get_uuid_column(
        ForeignKey("tl_prompt.prompt_id", ondelete="CASCADE"),
        nullable=False
    )

    # Snapshot - frozen at round start
    snapshot_answer_ids = Column(JSON, nullable=False)  # List of answer_ids
    snapshot_cluster_ids = Column(JSON, nullable=False)  # List of cluster_ids
    snapshot_total_weight = Column(Float, nullable=False, default=0.0)  # W_total for scoring

    # Game state
    matched_clusters = Column(JSON, nullable=False, default=[])  # Set of cluster_ids matched during play
    strikes = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default='active', nullable=False)  # active, completed, abandoned

    # Results (set on completion)
    final_coverage = Column(Float, nullable=True)  # 0-1
    gross_payout = Column(Integer, nullable=True)  # 0-300

    # Timing
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # v2 Challenge mode support
    challenge_id = get_uuid_column(
        ForeignKey("tl_challenge.challenge_id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    prompt = relationship("TLPrompt", back_populates="rounds")
    player = relationship("Player", back_populates="tl_rounds")

    __table_args__ = (
        CheckConstraint('strikes >= 0 AND strikes <= 3', name='valid_strikes'),
        CheckConstraint("status IN ('active', 'completed', 'abandoned')", name='valid_status'),
        Index('idx_tl_round_player', 'player_id'),
        Index('idx_tl_round_status', 'status'),
    )

    def __repr__(self):
        return f"<TLRound(round_id={self.round_id}, player_id={self.player_id}, status={self.status})>"
