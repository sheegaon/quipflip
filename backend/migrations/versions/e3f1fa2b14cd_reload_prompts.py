"""reload_prompts

Revision ID: e3f1fa2b14cd
Revises: d7e8f9a1b2c3
Create Date: 2025-10-12 19:00:00.000000

"""
from collections.abc import Sequence
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa

from backend.services.prompt_seeder import load_prompts_from_csv


# revision identifiers, used by Alembic.
revision: str = "e3f1fa2b14cd"
down_revision: str | None = "d7e8f9a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Flush existing prompts and reload from prompt_seeder CSV file."""
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    if dialect_name == "postgresql":
        from sqlalchemy.dialects import postgresql

        uuid_column_type = postgresql.UUID(as_uuid=True)
        uuid_factory = uuid.uuid4
    else:
        uuid_column_type = sa.String(length=36)
        uuid_factory = lambda: str(uuid.uuid4())

    # Clear dependent references to avoid FK violations
    conn.execute(sa.text("UPDATE rounds SET prompt_id = NULL WHERE prompt_id IS NOT NULL"))

    # Remove existing prompt feedback (cascades automatically, but ensures consistency)
    conn.execute(sa.text("DELETE FROM prompt_feedback"))

    # Remove existing prompts
    conn.execute(sa.text("DELETE FROM prompts"))

    prompt_table = sa.table(
        "prompts",
        sa.column("prompt_id", uuid_column_type),
        sa.column("text", sa.String()),
        sa.column("category", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("usage_count", sa.Integer()),
        sa.column("avg_copy_quality", sa.Float()),
        sa.column("enabled", sa.Boolean()),
    )

    # Load prompts from CSV file
    prompts_data = load_prompts_from_csv()

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        prompt_table,
        [
            {
                "prompt_id": uuid_factory(),
                "text": text,
                "category": category,
                "created_at": now,
                "usage_count": 0,
                "avg_copy_quality": None,
                "enabled": True,
            }
            for text, category in prompts_data
        ],
    )


def downgrade() -> None:
    """Downgrade for this data migration is a no-op as it's not safely reversible."""
    pass
