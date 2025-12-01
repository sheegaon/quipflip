"""Model for caching phrase embeddings."""

from datetime import datetime, UTC
import uuid

from sqlalchemy import Column, String, DateTime, JSON, UniqueConstraint

from backend.database import Base
from backend.models.base import get_uuid_column


class PhraseEmbedding(Base):
    """Stores cached embeddings for phrases used in similarity checks."""

    __tablename__ = "phrase_embeddings"

    embedding_id = get_uuid_column(primary_key=True, default=uuid.uuid4)
    phrase = Column(String(255), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    provider = Column(String(50), nullable=False, index=True, default="openai")
    embedding = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("phrase", "model", name="uq_phrase_embeddings_phrase_model"),
    )

