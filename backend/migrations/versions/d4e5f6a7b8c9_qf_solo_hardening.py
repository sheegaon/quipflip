"""Add QuipFlip solo hardening tables and constraints.

Revision ID: d4e5f6a7b8c9
Revises: c2d3e4f5a6b7
Create Date: 2026-06-22 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, UTC
from typing import Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _qf_rounds_table() -> sa.Table:
    metadata = sa.MetaData()
    uuid_type = sa.String(length=36)
    return sa.Table(
        "qf_rounds",
        metadata,
        sa.Column("round_id", uuid_type, nullable=False),
        sa.Column("player_id", uuid_type, nullable=False),
        sa.Column("round_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("party_round_id", uuid_type, nullable=True),
        sa.Column("prompt_id", uuid_type, nullable=True),
        sa.Column("prompt_text", sa.String(length=500), nullable=True),
        sa.Column("submitted_phrase", sa.String(length=100), nullable=True),
        sa.Column("phraseset_status", sa.String(length=20), nullable=True),
        sa.Column("copy1_player_id", uuid_type, nullable=True),
        sa.Column("copy2_player_id", uuid_type, nullable=True),
        sa.Column("prompt_round_id", uuid_type, nullable=True),
        sa.Column("original_phrase", sa.String(length=100), nullable=True),
        sa.Column("copy_phrase", sa.String(length=100), nullable=True),
        sa.Column("system_contribution", sa.Integer(), nullable=False),
        sa.Column("phraseset_id", uuid_type, nullable=True),
        sa.Column("vote_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("assignment_token", uuid_type, nullable=True),
        sa.Column("command_id", uuid_type, nullable=True),
        sa.Column("copy_slot", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_id"], ["qf_prompts.prompt_id"]),
        sa.ForeignKeyConstraint(["prompt_round_id"], ["qf_rounds.round_id"]),
        sa.ForeignKeyConstraint(["copy1_player_id"], ["players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["copy2_player_id"], ["players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phraseset_id"], ["qf_phrasesets.phraseset_id"]),
        sa.PrimaryKeyConstraint("round_id"),
    )


def _qf_phrasesets_table() -> sa.Table:
    metadata = sa.MetaData()
    uuid_type = sa.String(length=36)
    return sa.Table(
        "qf_phrasesets",
        metadata,
        sa.Column("phraseset_id", uuid_type, nullable=False),
        sa.Column("prompt_round_id", uuid_type, nullable=False),
        sa.Column("copy_round_1_id", uuid_type, nullable=False),
        sa.Column("copy_round_2_id", uuid_type, nullable=False),
        sa.Column("prompt_text", sa.String(length=500), nullable=False),
        sa.Column("original_phrase", sa.String(length=100), nullable=False),
        sa.Column("copy_phrase_1", sa.String(length=100), nullable=False),
        sa.Column("copy_phrase_2", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("vote_count", sa.Integer(), nullable=False),
        sa.Column("third_vote_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fifth_vote_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("total_pool", sa.Integer(), nullable=False),
        sa.Column("vote_contributions", sa.Integer(), nullable=False),
        sa.Column("vote_payouts_paid", sa.Integer(), nullable=False),
        sa.Column("system_contribution", sa.Integer(), nullable=False),
        sa.Column("second_copy_contribution", sa.Integer(), nullable=False),
        sa.Column("finalization_reason", sa.String(length=64), nullable=True),
        sa.Column("payouts_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["prompt_round_id"], ["qf_rounds.round_id"]),
        sa.ForeignKeyConstraint(["copy_round_1_id"], ["qf_rounds.round_id"]),
        sa.ForeignKeyConstraint(["copy_round_2_id"], ["qf_rounds.round_id"]),
        sa.PrimaryKeyConstraint("phraseset_id"),
    )


def _backfill_round_tokens_and_slots(bind: sa.Connection) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT round_id, player_id, round_type, status, created_at, prompt_round_id, party_round_id
            FROM qf_rounds
            ORDER BY created_at ASC, round_id ASC
            """
        )
    ).mappings().all()

    copy_groups: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if row["round_type"] != "copy":
            continue
        if row["party_round_id"] is not None:
            continue
        if row["status"] not in {"active", "submitted"}:
            continue
        if row["prompt_round_id"] is None:
            raise RuntimeError(
                f"Cannot backfill qf_rounds.copy_slot for copy round {row['round_id']}: missing prompt_round_id"
            )
        prompt_round_id = str(row["prompt_round_id"])
        copy_groups.setdefault(prompt_round_id, []).append(dict(row))

    for prompt_round_id, copies in copy_groups.items():
        if len(copies) > 2:
            raise RuntimeError(
                f"Cannot backfill qf_rounds.copy_slot for prompt_round_id={prompt_round_id}: "
                f"{len(copies)} live copy rounds found"
            )
        copies.sort(key=lambda item: (str(item["created_at"]), str(item["round_id"])))
        for slot, row in enumerate(copies, start=1):
            bind.execute(
                sa.text(
                    "UPDATE qf_rounds SET copy_slot = :copy_slot WHERE round_id = :round_id"
                ),
                {"copy_slot": slot, "round_id": row["round_id"]},
            )

    for row in rows:
        if row["party_round_id"] is not None:
            continue
        if row["round_type"] not in {"prompt", "copy", "vote"}:
            continue
        bind.execute(
            sa.text(
                "UPDATE qf_rounds SET assignment_token = :assignment_token WHERE round_id = :round_id"
            ),
            {"assignment_token": uuid4().hex, "round_id": row["round_id"]},
        )


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("qf_rounds", sa.Column("assignment_token", sa.String(length=36), nullable=True))
    op.add_column("qf_rounds", sa.Column("command_id", sa.String(length=36), nullable=True))
    op.add_column("qf_rounds", sa.Column("copy_slot", sa.Integer(), nullable=True))
    op.add_column("qf_phrasesets", sa.Column("finalization_reason", sa.String(length=64), nullable=True))
    op.add_column(
        "qf_phrasesets",
        sa.Column("payouts_completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "qf_command_receipts",
        sa.Column("receipt_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("player_id", sa.String(length=36), sa.ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False),
        sa.Column("command_id", sa.String(length=36), nullable=False),
        sa.Column("command_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.String(length=36), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("player_id", "command_id", name="uq_qf_command_receipts_player_command"),
    )
    op.create_index(
        "ix_qf_command_receipts_player_created",
        "qf_command_receipts",
        ["player_id", "created_at"],
    )

    op.create_table(
        "qf_second_copy_offers",
        sa.Column("offer_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("player_id", sa.String(length=36), sa.ForeignKey("players.player_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_copy_round_id", sa.String(length=36), sa.ForeignKey("qf_rounds.round_id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt_round_id", sa.String(length=36), sa.ForeignKey("qf_rounds.round_id", ondelete="CASCADE"), nullable=False),
        sa.Column("offer_token", sa.String(length=36), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("source_copy_round_id", name="uq_qf_second_copy_offers_source_copy_round"),
    )

    op.create_table(
        "qf_vote_choices",
        sa.Column("choice_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("round_id", sa.String(length=36), sa.ForeignKey("qf_rounds.round_id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("choice_token", sa.String(length=36), nullable=False, unique=True),
        sa.Column("displayed_phrase", sa.String(length=100), nullable=False),
        sa.Column("internal_role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("round_id", "position", name="uq_qf_vote_choices_round_position"),
    )
    op.create_index("ix_qf_vote_choices_round_id", "qf_vote_choices", ["round_id"])

    op.create_table(
        "qf_ai_jobs",
        sa.Column("job_id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint(
            "job_type",
            "target_id",
            "expected_version",
            name="uq_qf_ai_jobs_target_version",
        ),
    )
    op.create_index("ix_qf_ai_jobs_status_created", "qf_ai_jobs", ["status", "created_at"])

    _backfill_round_tokens_and_slots(bind)

    op.create_index(
        "uq_qf_rounds_assignment_token",
        "qf_rounds",
        ["assignment_token"],
        unique=True,
    )
    op.create_index(
        "uq_qf_active_solo_round_per_player",
        "qf_rounds",
        ["player_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active' AND party_round_id IS NULL"),
        postgresql_where=sa.text("status = 'active' AND party_round_id IS NULL"),
    )
    op.create_index(
        "uq_qf_live_copy_slot",
        "qf_rounds",
        ["prompt_round_id", "copy_slot"],
        unique=True,
        sqlite_where=sa.text(
            "round_type = 'copy' AND status IN ('active', 'submitted') AND party_round_id IS NULL"
        ),
        postgresql_where=sa.text(
            "round_type = 'copy' AND status IN ('active', 'submitted') AND party_round_id IS NULL"
        ),
    )
    op.create_index(
        "uq_qf_solo_start_command",
        "qf_rounds",
        ["player_id", "command_id"],
        unique=True,
        sqlite_where=sa.text("command_id IS NOT NULL AND party_round_id IS NULL"),
        postgresql_where=sa.text("command_id IS NOT NULL AND party_round_id IS NULL"),
    )

    with op.batch_alter_table("qf_rounds", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_qf_rounds_copy_slot",
            "copy_slot IN (1, 2) OR copy_slot IS NULL",
        )

    with op.batch_alter_table("qf_phrasesets", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_qf_phrasesets_finalized_timestamp",
            "status != 'finalized' OR finalized_at IS NOT NULL",
        )

    op.execute(sa.text("UPDATE qf_phrasesets SET payouts_completed_at = finalized_at WHERE finalized_at IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_qf_solo_start_command", table_name="qf_rounds")
    op.drop_index("uq_qf_live_copy_slot", table_name="qf_rounds")
    op.drop_index("uq_qf_active_solo_round_per_player", table_name="qf_rounds")
    op.drop_index("uq_qf_rounds_assignment_token", table_name="qf_rounds")
    op.drop_index("ix_qf_ai_jobs_status_created", table_name="qf_ai_jobs")
    op.drop_index("ix_qf_vote_choices_round_id", table_name="qf_vote_choices")
    op.drop_index("ix_qf_command_receipts_player_created", table_name="qf_command_receipts")
    op.drop_table("qf_ai_jobs")
    op.drop_table("qf_vote_choices")
    op.drop_table("qf_second_copy_offers")
    op.drop_table("qf_command_receipts")
    op.drop_column("qf_phrasesets", "payouts_completed_at")
    op.drop_column("qf_phrasesets", "finalization_reason")
    op.drop_column("qf_rounds", "copy_slot")
    op.drop_column("qf_rounds", "command_id")
    op.drop_column("qf_rounds", "assignment_token")
