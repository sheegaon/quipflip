"""add guest vote lockout fields

Revision ID: guest_lockout_001
Revises: fc8705dc196e
Create Date: 2025-10-30

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'guest_lockout_001'
down_revision = 'fc8705dc196e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if we're using SQLite or PostgreSQL
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # Add consecutive_incorrect_votes column with appropriate server_default
    if dialect_name == 'sqlite':
        # SQLite: Use string literal for server_default
        op.add_column('players', sa.Column('consecutive_incorrect_votes', sa.Integer(), nullable=False, server_default='0'))
    else:
        # PostgreSQL: Use text() for server_default
        op.add_column('players', sa.Column('consecutive_incorrect_votes', sa.Integer(), nullable=False, server_default=sa.text('0')))

    # Add vote_lockout_until column (works the same for both)
    op.add_column('players', sa.Column('vote_lockout_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove columns (works the same for both SQLite and PostgreSQL)
    op.drop_column('players', 'vote_lockout_until')
    op.drop_column('players', 'consecutive_incorrect_votes')
