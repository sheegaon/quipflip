"""make_balance_after_nullable

Revision ID: 37c3bd779d3e
Revises: add_ir_006
Create Date: 2025-11-18 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '37c3bd779d3e'
down_revision: Union[str, None] = 'add_ir_006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table using dialect-aware inspection."""
    dialect = connection.dialect.name

    if dialect == 'postgresql':
        result = connection.execute(
            sa.text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = :table_name AND column_name = :column_name
                )
            """),
            {"table_name": table_name, "column_name": column_name}
        )
        return result.scalar()
    elif dialect == 'sqlite':
        result = connection.execute(
            sa.text(f"PRAGMA table_info({table_name})")
        )
        columns = [row[1] for row in result.fetchall()]
        return column_name in columns
    return False


def upgrade() -> None:
    """Make balance_after column nullable in qf_transactions.

    This column is deprecated and no longer populated by the code.
    Uses dialect-aware approach for PostgreSQL and SQLite compatibility.
    """
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Check if column exists before attempting to modify it
    if not column_exists(bind, 'qf_transactions', 'balance_after'):
        # Column doesn't exist, skip migration
        return

    if dialect == 'postgresql':
        # PostgreSQL supports ALTER COLUMN directly
        op.alter_column('qf_transactions', 'balance_after',
                       existing_type=sa.Integer(),
                       nullable=True)
    elif dialect == 'sqlite':
        # SQLite requires batch mode for column modifications
        with op.batch_alter_table('qf_transactions', schema=None) as batch_op:
            batch_op.alter_column('balance_after',
                       existing_type=sa.Integer(),
                       nullable=True)


def downgrade() -> None:
    """Restore balance_after as NOT NULL.

    Uses dialect-aware approach for PostgreSQL and SQLite compatibility.
    Note: This may fail if there are NULL values in the column.
    """
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Check if column exists before attempting to modify it
    if not column_exists(bind, 'qf_transactions', 'balance_after'):
        # Column doesn't exist, skip migration
        return

    if dialect == 'postgresql':
        # PostgreSQL supports ALTER COLUMN directly
        op.alter_column('qf_transactions', 'balance_after',
                       existing_type=sa.Integer(),
                       nullable=False)
    elif dialect == 'sqlite':
        # SQLite requires batch mode for column modifications
        with op.batch_alter_table('qf_transactions', schema=None) as batch_op:
            batch_op.alter_column('balance_after',
                       existing_type=sa.Integer(),
                       nullable=False)
