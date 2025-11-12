"""Add index to user_activity last_activity column

Revision ID: 91b278d1fb3b
Revises: 963b4bc9eb26
Create Date: 2025-11-12 09:03:26.707031

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91b278d1fb3b'
down_revision: Union[str, None] = '963b4bc9eb26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add index to user_activity.last_activity for efficient querying.

    Uses BRIN index on PostgreSQL (optimal for timestamp columns with monotonic values)
    and regular B-tree index on SQLite for local development compatibility.
    """
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'postgresql':
        # BRIN index is space-efficient for monotonically increasing timestamps
        # Use IF NOT EXISTS to make migration idempotent
        op.execute(
            'CREATE INDEX IF NOT EXISTS ix_user_activity_last_activity '
            'ON user_activity USING brin (last_activity)'
        )
    else:
        # SQLite doesn't support BRIN, use regular B-tree index
        # SQLite supports IF NOT EXISTS in CREATE INDEX
        op.execute(
            'CREATE INDEX IF NOT EXISTS ix_user_activity_last_activity '
            'ON user_activity (last_activity)'
        )


def downgrade() -> None:
    """Remove the index on user_activity.last_activity."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == 'postgresql':
        op.execute('DROP INDEX IF EXISTS ix_user_activity_last_activity')
    else:
        op.execute('DROP INDEX IF EXISTS ix_user_activity_last_activity')
