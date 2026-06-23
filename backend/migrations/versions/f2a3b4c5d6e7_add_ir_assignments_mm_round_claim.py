"""Add durable IR assignments and MM caption round claims.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-23
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

from backend.migrations.util import get_uuid_type


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = get_uuid_type()

    op.create_table(
        "ir_assignments",
        sa.Column("assignment_id", uuid_type, nullable=False),
        sa.Column("assignment_token", uuid_type, nullable=False),
        sa.Column("player_id", uuid_type, nullable=False),
        sa.Column("set_id", uuid_type, nullable=False),
        sa.Column("entry_id", uuid_type, nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint(
            "status IN ('assigned', 'submitting', 'submitted', 'completed', 'expired')",
            name="valid_ir_assignment_status",
        ),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["ir_backronym_entries.entry_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.player_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["set_id"],
            ["ir_backronym_sets.set_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.UniqueConstraint("assignment_token", name="uq_ir_assignments_assignment_token"),
    )
    op.create_index(
        "uq_ir_assignment_active_player",
        "ir_assignments",
        ["player_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('assigned', 'submitting', 'submitted')"),
        postgresql_where=sa.text("status IN ('assigned', 'submitting', 'submitted')"),
    )
    op.create_index(
        "uq_ir_assignment_player_set",
        "ir_assignments",
        ["player_id", "set_id"],
        unique=True,
    )
    op.create_index(
        "ix_ir_assignment_set_status",
        "ir_assignments",
        ["set_id", "status"],
        unique=False,
    )

    with op.batch_alter_table("mm_caption_submissions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("round_id", uuid_type, nullable=True))
        batch_op.create_foreign_key(
            "fk_mm_caption_submissions_round_id",
            "mm_vote_rounds",
            ["round_id"],
            ["round_id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            "uq_mm_caption_submission_round",
            ["round_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("mm_caption_submissions", schema=None) as batch_op:
        batch_op.drop_constraint("uq_mm_caption_submission_round", type_="unique")
        batch_op.drop_constraint(
            "fk_mm_caption_submissions_round_id",
            type_="foreignkey",
        )
        batch_op.drop_column("round_id")

    op.drop_index("ix_ir_assignment_set_status", table_name="ir_assignments")
    op.drop_index("uq_ir_assignment_player_set", table_name="ir_assignments")
    op.drop_index("uq_ir_assignment_active_player", table_name="ir_assignments")
    op.drop_table("ir_assignments")
