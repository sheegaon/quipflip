"""Add IR transaction compatibility columns.

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-06-22

This migration brings the ir_transactions table in line with the current
IRTransaction model by adding the IR-specific ledger columns that the service
layer already reads and writes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_uuid_type


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def column_exists(connection, table_name: str, column_name: str) -> bool:
    """Return True when a column already exists on the table."""

    if connection.dialect.name == "sqlite":
        rows = connection.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
        return any(row[1] == column_name for row in rows)

    result = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = :table_name AND column_name = :column_name
            )
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return bool(result.scalar())


def upgrade() -> None:
    """Add the IR-specific transaction columns if they are missing."""

    uuid = get_uuid_type()
    connection = op.get_context().connection

    needs_transaction_type = not column_exists(connection, "ir_transactions", "transaction_type")
    needs_vault_contribution = not column_exists(connection, "ir_transactions", "vault_contribution")
    needs_entry_id = not column_exists(connection, "ir_transactions", "entry_id")
    needs_set_id = not column_exists(connection, "ir_transactions", "set_id")

    if not any(
        (
            needs_transaction_type,
            needs_vault_contribution,
            needs_entry_id,
            needs_set_id,
        )
    ):
        return

    with op.batch_alter_table("ir_transactions", schema=None) as batch_op:
        if needs_transaction_type:
            batch_op.add_column(
                sa.Column("transaction_type", sa.String(length=50), nullable=True)
            )
        if needs_vault_contribution:
            batch_op.add_column(
                sa.Column(
                    "vault_contribution",
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text("0"),
                )
            )
        if needs_entry_id:
            batch_op.add_column(sa.Column("entry_id", uuid, nullable=True))
        if needs_set_id:
            batch_op.add_column(sa.Column("set_id", uuid, nullable=True))
            batch_op.create_foreign_key(
                "fk_ir_transactions_set_id",
                "ir_backronym_sets",
                ["set_id"],
                ["set_id"],
                ondelete="SET NULL",
            )

        if needs_transaction_type:
            batch_op.create_index(
                "ix_ir_transactions_transaction_type",
                ["transaction_type"],
                unique=False,
            )

    if needs_transaction_type:
        op.execute(
            sa.text(
                """
                UPDATE ir_transactions
                SET transaction_type = "type"
                WHERE transaction_type IS NULL
                """
            )
        )


def downgrade() -> None:
    """Remove the IR-specific transaction columns."""

    connection = op.get_context().connection

    has_transaction_type = column_exists(connection, "ir_transactions", "transaction_type")
    has_vault_contribution = column_exists(connection, "ir_transactions", "vault_contribution")
    has_entry_id = column_exists(connection, "ir_transactions", "entry_id")
    has_set_id = column_exists(connection, "ir_transactions", "set_id")

    if not any(
        (
            has_transaction_type,
            has_vault_contribution,
            has_entry_id,
            has_set_id,
        )
    ):
        return

    with op.batch_alter_table("ir_transactions", schema=None) as batch_op:
        if has_set_id:
            batch_op.drop_constraint("fk_ir_transactions_set_id", type_="foreignkey")
            batch_op.drop_column("set_id")
        if has_entry_id:
            batch_op.drop_column("entry_id")
        if has_vault_contribution:
            batch_op.drop_column("vault_contribution")
        if has_transaction_type:
            batch_op.drop_index("ix_ir_transactions_transaction_type")
            batch_op.drop_column("transaction_type")
