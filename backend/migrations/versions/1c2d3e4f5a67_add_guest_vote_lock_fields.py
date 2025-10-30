"""add guest vote lock fields

Revision ID: 1c2d3e4f5a67
Revises: 0c5e8a127691
Create Date: 2024-07-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1c2d3e4f5a67"
down_revision = "0c5e8a127691"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("guest_incorrect_vote_streak", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "players",
        sa.Column("guest_vote_locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("players", "guest_vote_locked_until")
    op.drop_column("players", "guest_incorrect_vote_streak")
