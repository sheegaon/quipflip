"""add_tutorial_fields_to_ir_players

Revision ID: add_ir_006
Revises: add_ir_005
Create Date: 2025-11-18 04:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_ir_006'
down_revision: Union[str, None] = 'add_ir_005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tutorial tracking columns to ir_players table
    # These fields are inherited from PlayerBase and need to be added to IR tables
    op.add_column('ir_players', sa.Column('tutorial_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('ir_players', sa.Column('tutorial_progress', sa.String(length=20), nullable=False, server_default='not_started'))
    op.add_column('ir_players', sa.Column('tutorial_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('ir_players', sa.Column('tutorial_completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove tutorial columns
    op.drop_column('ir_players', 'tutorial_completed_at')
    op.drop_column('ir_players', 'tutorial_started_at')
    op.drop_column('ir_players', 'tutorial_progress')
    op.drop_column('ir_players', 'tutorial_completed')
