"""add_action_category_to_user_activity

Revision ID: 963b4bc9eb26
Revises: b2c3d4e5f8a9
Create Date: 2025-11-10 16:52:03.271180

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '963b4bc9eb26'
down_revision: Union[str, None] = 'b2c3d4e5f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_action_category column to user_activity table."""
    # Add the new column with a default value
    op.add_column('user_activity', sa.Column('last_action_category', sa.String(length=50), nullable=False, server_default='other'))


def downgrade() -> None:
    """Remove last_action_category column from user_activity table."""
    op.drop_column('user_activity', 'last_action_category')
