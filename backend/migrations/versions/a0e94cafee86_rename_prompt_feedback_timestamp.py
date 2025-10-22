"""rename prompt feedback timestamp

Revision ID: a0e94cafee86
Revises: d7e8f9a1b2c3
Create Date: 2025-10-12 18:30:44.682925

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0e94cafee86'
down_revision: Union[str, None] = 'd7e8f9a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename created_at column to last_updated_at."""
    with op.batch_alter_table("prompt_feedback", schema=None) as batch_op:
        batch_op.alter_column("created_at", new_column_name="last_updated_at")


def downgrade() -> None:
    """Revert column rename for prompt_feedback."""
    with op.batch_alter_table("prompt_feedback", schema=None) as batch_op:
        batch_op.alter_column("last_updated_at", new_column_name="created_at")
