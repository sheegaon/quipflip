"""AI quip cache models for storing validated prompt responses."""

import uuid
from datetime import datetime, UTC

from sqlalchemy import Column, DateTime, ForeignKey, String, Index
from sqlalchemy.orm import relationship

from backend.database import Base
from backend.models.base import get_uuid_column


class QFAIQuipCache(Base):
    """Caches validated AI prompt (quip) responses for reuse."""

    __tablename__ = "qf_ai_quip_cache"

    cache_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    prompt_id = get_uuid_column(ForeignKey("qf_prompts.prompt_id", ondelete="SET NULL"), nullable=True)
    prompt_text = Column(String(500), nullable=False, index=True)

    generation_provider = Column(String(50), nullable=False)
    generation_model = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    phrases = relationship(
        "QFAIQuipPhrase",
        back_populates="cache",
        cascade="all, delete-orphan",
        order_by="QFAIQuipPhrase.created_at",
    )

    __table_args__ = (
        Index("ix_quip_cache_prompt_text_provider", "prompt_text", "generation_provider"),
    )

    def __repr__(self) -> str:
        return f"<QFAIQuipCache(cache_id={self.cache_id}, prompt_text={self.prompt_text})>"


class QFAIQuipPhrase(Base):
    """Individual validated quip phrases tied to an AI quip cache."""

    __tablename__ = "qf_ai_quip_phrase"

    phrase_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    cache_id = get_uuid_column(ForeignKey("qf_ai_quip_cache.cache_id", ondelete="CASCADE"), nullable=False, index=True)
    phrase_text = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    cache = relationship("QFAIQuipCache", back_populates="phrases")
    usages = relationship("QFAIQuipPhraseUsage", back_populates="phrase", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<QFAIQuipPhrase(phrase_id={self.phrase_id}, cache_id={self.cache_id})>"


class QFAIQuipPhraseUsage(Base):
    """Tracks where cached quip phrases are consumed."""

    __tablename__ = "qf_ai_quip_phrase_usage"

    usage_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    phrase_id = get_uuid_column(
        ForeignKey("qf_ai_quip_phrase.phrase_id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_round_id = get_uuid_column(ForeignKey("qf_rounds.round_id", ondelete="SET NULL"), nullable=True, index=True)
    used_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    phrase = relationship("QFAIQuipPhrase", back_populates="usages")
    prompt_round = relationship("Round")

    __table_args__ = (
        Index("ix_quip_phrase_usage_round", "prompt_round_id"),
    )

    def __repr__(self) -> str:
        return f"<QFAIQuipPhraseUsage(usage_id={self.usage_id}, phrase_id={self.phrase_id})>"
