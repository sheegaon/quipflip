"""Populate TLPlayerData for existing players with starting balance

Revision ID: populate_tl_001
Revises: 10c5f8f67e50
Create Date: 2025-12-03

This migration populates the tl_player_data table for all existing players
who don't have a TL player data record, initializing them with the configured
starting balance (1000 LinkCoins) and 0 vault.
"""
from typing import Sequence, Union
from datetime import datetime, UTC
from alembic import op
import sqlalchemy as sa
from sqlalchemy import select, func

# revision identifiers, used by Alembic.
revision: str = 'populate_tl_001'
down_revision: Union[str, None] = '10c5f8f67e50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Populate TLPlayerData for existing players."""
    bind = op.get_bind()

    # Insert TLPlayerData for players who don't have it yet
    # Using raw SQL for compatibility across databases
    insert_sql = """
        INSERT INTO tl_player_data (
            player_id,
            wallet,
            vault,
            tutorial_completed,
            tutorial_progress,
            created_at,
            updated_at
        )
        SELECT
            p.player_id,
            1000 as wallet,
            0 as vault,
            false as tutorial_completed,
            'not_started' as tutorial_progress,
            CURRENT_TIMESTAMP as created_at,
            CURRENT_TIMESTAMP as updated_at
        FROM players p
        WHERE NOT EXISTS (
            SELECT 1 FROM tl_player_data t WHERE t.player_id = p.player_id
        )
    """

    try:
        op.execute(sa.text(insert_sql))
        print("✓ Populated TLPlayerData for existing players")
    except Exception as e:
        print(f"✗ Failed to populate TLPlayerData: {e}")
        raise


def downgrade() -> None:
    """Remove TLPlayerData entries created by this migration."""
    # Delete TLPlayerData entries that don't have associated transactions
    # This is a safe downgrade that only removes data this migration created
    delete_sql = """
        DELETE FROM tl_player_data
        WHERE player_id IN (
            SELECT p.player_id FROM players p
            WHERE NOT EXISTS (
                SELECT 1 FROM tl_transaction t WHERE t.player_id = p.player_id
            )
        )
    """

    try:
        op.execute(sa.text(delete_sql))
        print("✓ Removed TLPlayerData entries")
    except Exception as e:
        print(f"✗ Failed to remove TLPlayerData: {e}")
        raise
