"""Add phrase embedding cache table.

Revision ID: 1a2b3c4d5e6f
Revises: b2c3d4e5f8a9
Create Date: 2025-12-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_timestamp_default, get_uuid_type


# revision identifiers, used by Alembic.
revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "b2c3d4e5f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_column():
    """Return JSON column compatible with SQLite and Postgres."""

    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"

    if dialect_name == "postgresql":
        return sa.JSON()

    # SQLite stores JSON as TEXT but SQLAlchemy will handle serialization
    return sa.JSON().with_variant(sa.Text(), "sqlite")


def upgrade() -> None:
    uuid = get_uuid_type()
    json_type = _json_column()

    op.create_table(
        "phrase_embeddings",
        sa.Column("embedding_id", uuid, nullable=False),
        sa.Column("phrase", sa.String(length=255), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default=sa.text("'openai'")),
        sa.Column("embedding", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=get_timestamp_default(),
        ),
        sa.PrimaryKeyConstraint("embedding_id"),
        sa.UniqueConstraint("phrase", "model", name="uq_phrase_embeddings_phrase_model"),
    )

    op.create_index("ix_phrase_embeddings_phrase", "phrase_embeddings", ["phrase"], unique=False)
    op.create_index("ix_phrase_embeddings_model", "phrase_embeddings", ["model"], unique=False)
    op.create_index(
        "ix_phrase_embeddings_provider",
        "phrase_embeddings",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "ix_phrase_embeddings_created_at",
        "phrase_embeddings",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_phrase_embeddings_created_at", table_name="phrase_embeddings")
    op.drop_index("ix_phrase_embeddings_provider", table_name="phrase_embeddings")
    op.drop_index("ix_phrase_embeddings_model", table_name="phrase_embeddings")
    op.drop_index("ix_phrase_embeddings_phrase", table_name="phrase_embeddings")
    op.drop_table("phrase_embeddings")

