"""add wallet and vault balances

Revision ID: def456abc123
Revises: 91b278d1fb3b
Create Date: 2025-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'def456abc123'
down_revision: Union[str, None] = '91b278d1fb3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add wallet and vault columns to players table and transaction tracking.

    This migration:
    1. Adds wallet and vault columns to players table
    2. Migrates existing balance to wallet (grandfathering)
    3. Adds wallet_type, wallet_balance_after, vault_balance_after to transactions table
    """

    # Add wallet and vault columns to players table
    # Default wallet to 1000 for new players, vault to 0
    op.add_column('players', sa.Column('wallet', sa.Integer(), nullable=False, server_default=1000))
    op.add_column('players', sa.Column('vault', sa.Integer(), nullable=False, server_default=0))

    # Migrate existing balances: balance -> wallet, vault = 0
    # This grandfathers all existing users by putting their current balance into wallet
    op.execute('UPDATE players SET wallet = balance, vault = 0')

    # Add transaction tracking columns
    op.add_column('transactions', sa.Column('wallet_type', sa.String(20), nullable=False, server_default='wallet'))
    op.add_column('transactions', sa.Column('wallet_balance_after', sa.Integer(), nullable=True))
    op.add_column('transactions', sa.Column('vault_balance_after', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove wallet and vault columns."""

    # Remove transaction tracking columns
    op.drop_column('transactions', 'vault_balance_after')
    op.drop_column('transactions', 'wallet_balance_after')
    op.drop_column('transactions', 'wallet_type')

    # Remove wallet and vault columns from players
    op.drop_column('players', 'vault')
    op.drop_column('players', 'wallet')
