"""rename payout_claimed to result_viewed

Revision ID: 810c1bfc5a57
Revises: fc8705dc196e
Create Date: 2025-10-27 11:11:35.826810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '810c1bfc5a57'
down_revision: Union[str, None] = 'fc8705dc196e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rename payout_claimed to result_viewed in result_views table.
    This migration is compatible with both SQLite and PostgreSQL.
    """
    # Drop the existing index first
    op.drop_index("ix_result_views_payout_claimed", table_name="result_views")
    
    # Rename columns using batch operations for SQLite compatibility
    with op.batch_alter_table("result_views", schema=None) as batch_op:
        # Rename payout_claimed to result_viewed
        batch_op.alter_column("payout_claimed", new_column_name="result_viewed")
        # Rename payout_claimed_at to result_viewed_at
        batch_op.alter_column("payout_claimed_at", new_column_name="result_viewed_at")
    
    # Create new index with the updated column name
    op.create_index(
        "ix_result_views_result_viewed",
        "result_views",
        ["result_viewed"],
        unique=False,
    )


def downgrade() -> None:
    """
    Revert result_viewed back to payout_claimed.
    """
    # Drop the new index
    op.drop_index("ix_result_views_result_viewed", table_name="result_views")
    
    # Rename columns back using batch operations for SQLite compatibility
    with op.batch_alter_table("result_views", schema=None) as batch_op:
        # Rename result_viewed_at back to payout_claimed_at
        batch_op.alter_column("result_viewed_at", new_column_name="payout_claimed_at")
        # Rename result_viewed back to payout_claimed
        batch_op.alter_column("result_viewed", new_column_name="payout_claimed")
    
    # Recreate the original index
    op.create_index(
        "ix_result_views_payout_claimed",
        "result_views",
        ["payout_claimed"],
        unique=False,
    )
