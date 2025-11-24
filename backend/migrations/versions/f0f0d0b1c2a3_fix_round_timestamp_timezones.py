"""Convert qf_rounds timestamps to timezone-aware columns.

Ensures Round.created_at/expires_at/vote_submitted_at store actual instants so
timeout logic uses correct UTC comparisons when running against PostgreSQL
databases configured with non-UTC timezones.

Revision ID: f0f0d0b1c2a3
Revises: e8f4a12b3cde
Create Date: 2025-11-24 23:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f0f0d0b1c2a3"
down_revision: Union[str, None] = "e8f4a12b3cde"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROUND_TIMESTAMP_COLUMNS = ("created_at", "expires_at", "vote_submitted_at")


def _get_postgres_timezone(bind) -> str:
    """Return the current PostgreSQL timezone as a safe literal."""
    timezone = bind.execute(sa.text("SHOW TIMEZONE")).scalar()
    if not timezone:
        timezone = "UTC"
    return timezone.replace("'", "''")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite stores datetimes as ISO8601 strings, so no schema changes needed.
        return

    tz_literal = _get_postgres_timezone(bind)

    for column in ROUND_TIMESTAMP_COLUMNS:
        op.execute(
            sa.text(
                f"""
                ALTER TABLE qf_rounds
                ALTER COLUMN {column}
                TYPE TIMESTAMP WITH TIME ZONE
                USING {column} AT TIME ZONE '{tz_literal}'
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for column in ROUND_TIMESTAMP_COLUMNS:
        op.execute(
            sa.text(
                f"""
                ALTER TABLE qf_rounds
                ALTER COLUMN {column}
                TYPE TIMESTAMP WITHOUT TIME ZONE
                USING {column} AT TIME ZONE 'UTC'
                """
            )
        )
