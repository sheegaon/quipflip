"""add guest vote lockout fields

Revision ID: d3ddc9470e6d
Revises: guest_lockout_001
Create Date: 2025-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3ddc9470e6d'
down_revision: Union[str, None] = 'guest_lockout_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add lockout tracking fields to the players table."""

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {column["name"] for column in inspector.get_columns("players")}

    if "consecutive_incorrect_votes" not in existing_columns:
        if conn.dialect.name == "sqlite":
            server_default = "0"
        else:
            server_default = sa.text("0")

        op.add_column(
            "players",
            sa.Column(
                "consecutive_incorrect_votes",
                sa.Integer(),
                nullable=False,
                server_default=server_default,
            ),
        )

    if "vote_lockout_until" not in existing_columns:
        op.add_column(
            "players",
            sa.Column(
                "vote_lockout_until",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )


def downgrade() -> None:
    # Remove columns (works the same for both SQLite and PostgreSQL)
    op.drop_column("players", "vote_lockout_until")
    op.drop_column("players", "consecutive_incorrect_votes")
