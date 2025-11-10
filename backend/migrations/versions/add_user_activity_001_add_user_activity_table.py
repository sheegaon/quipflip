"""Add user_activity table for online users tracking

Revision ID: add_user_activity_001
Revises: guest_lockout_001
Create Date: 2025-11-10 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_user_activity_001'
down_revision: Union[str, None] = 'guest_lockout_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_activity table for tracking online users."""
    op.create_table(
        'user_activity',
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('last_action', sa.String(length=100), nullable=False),
        sa.Column('last_action_path', sa.Text(), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('player_id')
    )

    # Create index on last_activity for efficient queries
    op.create_index(
        'ix_user_activity_last_activity',
        'user_activity',
        ['last_activity'],
        unique=False
    )


def downgrade() -> None:
    """Drop user_activity table."""
    op.drop_index('ix_user_activity_last_activity', table_name='user_activity')
    op.drop_table('user_activity')
