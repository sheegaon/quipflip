"""Repair SQLite foreign keys left by player unification and QF renames.

Revision ID: a3f6c8d9e0b1
Revises: tl_003_add_uuid_server_defaults
Create Date: 2026-06-22
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f6c8d9e0b1"
down_revision: Union[str, None] = "tl_003_add_uuid_server_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}
LEGACY_PLAYER_TABLES = {"qf_players", "mm_players", "ir_players"}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return

    existing_tables = set(sa.inspect(bind).get_table_names())
    temporary_parent_tables = LEGACY_PLAYER_TABLES - existing_tables
    for table_name in sorted(temporary_parent_tables):
        op.execute(
            sa.text(
                f'CREATE TABLE "{table_name}" '
                "(player_id VARCHAR(36) PRIMARY KEY)"
            )
        )

    phraseset_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("qf_phrasesets")
    }
    added_legacy_phraseset_column = "wordset_id" not in phraseset_columns
    if added_legacy_phraseset_column:
        op.execute(sa.text("ALTER TABLE qf_phrasesets ADD COLUMN wordset_id VARCHAR(36)"))

    inspector = sa.inspect(bind)
    repairs: dict[str, list[tuple[dict, str, list[str]]]] = {}

    for table_name in inspector.get_table_names():
        for foreign_key in inspector.get_foreign_keys(table_name):
            referred_table = foreign_key["referred_table"]
            referred_columns = foreign_key["referred_columns"]

            if referred_table in LEGACY_PLAYER_TABLES:
                repairs.setdefault(table_name, []).append(
                    (foreign_key, "players", ["player_id"])
                )
            elif referred_table == "qf_phrasesets" and referred_columns == ["wordset_id"]:
                repairs.setdefault(table_name, []).append(
                    (foreign_key, "qf_phrasesets", ["phraseset_id"])
                )

    for table_name, table_repairs in repairs.items():
        with op.batch_alter_table(
            table_name,
            recreate="always",
            naming_convention=NAMING_CONVENTION,
        ) as batch_op:
            for foreign_key, new_table, new_columns in table_repairs:
                constrained_columns = foreign_key["constrained_columns"]
                old_table = foreign_key["referred_table"]
                old_name = (
                    foreign_key.get("name")
                    or f"fk_{table_name}_{constrained_columns[0]}_{old_table}"
                )
                batch_op.drop_constraint(old_name, type_="foreignkey")
                batch_op.create_foreign_key(
                    f"fk_{table_name}_{constrained_columns[0]}_{new_table}",
                    new_table,
                    local_cols=constrained_columns,
                    remote_cols=new_columns,
                    **foreign_key.get("options", {}),
                )

    if added_legacy_phraseset_column:
        op.execute(sa.text("ALTER TABLE qf_phrasesets DROP COLUMN wordset_id"))
    for table_name in sorted(temporary_parent_tables):
        op.drop_table(table_name)


def downgrade() -> None:
    raise NotImplementedError(
        "The invalid SQLite foreign keys cannot be restored safely."
    )
