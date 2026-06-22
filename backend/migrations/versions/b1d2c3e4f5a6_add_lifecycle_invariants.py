"""Add lifecycle invariants.

Revision ID: b1d2c3e4f5a6
Revises: tl_003_add_uuid_server_defaults
Create Date: 2026-06-22 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

from backend.utils.idempotency import build_idempotency_key


# revision identifiers, used by Alembic.
revision: str = "b1d2c3e4f5a6"
down_revision: Union[str, None] = "tl_003_add_uuid_server_defaults"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_idempotency_keys(table_name: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"SELECT * FROM {table_name}")).mappings().all()
    for row in rows:
        values = dict(row)
        key = build_idempotency_key(table_name, values)
        bind.execute(
            sa.text(
                f"UPDATE {table_name} "
                "SET idempotency_key = :idempotency_key "
                "WHERE transaction_id = :transaction_id"
            ),
            {
                "idempotency_key": key,
                "transaction_id": values["transaction_id"],
            },
        )


def _set_version_default(table_name: str) -> None:
    op.execute(sa.text(f"UPDATE {table_name} SET version = 1 WHERE version IS NULL"))


def _qf_rounds_copy_table() -> sa.Table:
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
        sa.ForeignKeyConstraint(["player_id"], ["players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_id"], ["qf_prompts.prompt_id"]),
        sa.ForeignKeyConstraint(["prompt_round_id"], ["qf_rounds.round_id"]),
        sa.ForeignKeyConstraint(["copy1_player_id"], ["players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["copy2_player_id"], ["players.player_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phraseset_id"], ["qf_phrasesets.phraseset_id"]),
        sa.PrimaryKeyConstraint("round_id"),
        sa.Index("ix_rounds_created_at", "created_at"),
        sa.Index("ix_rounds_expires_at", "expires_at"),
        sa.Index("ix_rounds_player_id", "player_id"),
        sa.Index("ix_rounds_prompt_round_id", "prompt_round_id"),
        sa.Index("ix_rounds_status_created", "status", "created_at"),
        sa.Index("ix_rounds_wordset_id", "phraseset_id"),
        sa.Index("ix_rounds_phraseset_status", "phraseset_status"),
        sa.Index("ix_rounds_copy1_player_id", "copy1_player_id"),
        sa.Index("ix_rounds_copy2_player_id", "copy2_player_id"),
        sa.Index("ix_rounds_player_type_status", "player_id", "round_type", "status"),
        sa.Index("ix_qf_rounds_party_round_id", "party_round_id"),
    )


def upgrade() -> None:
    # Versioned lifecycle aggregates.
    op.add_column(
        "qf_rounds",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "qf_phrasesets",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "party_sessions",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "mm_vote_rounds",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "ir_backronym_sets",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "tl_round",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )

    for table_name in (
        "qf_rounds",
        "qf_phrasesets",
        "party_sessions",
        "mm_vote_rounds",
        "ir_backronym_sets",
        "tl_round",
    ):
        _set_version_default(table_name)

    if op.get_bind().dialect.name == "sqlite":
        op.create_table(
            "qf_players",
            sa.Column("player_id", sa.String(length=36), nullable=False),
            sa.PrimaryKeyConstraint("player_id"),
        )
        op.create_table(
            "mm_players",
            sa.Column("player_id", sa.String(length=36), nullable=False),
            sa.PrimaryKeyConstraint("player_id"),
        )
        op.create_table(
            "ir_players",
            sa.Column("player_id", sa.String(length=36), nullable=False),
            sa.PrimaryKeyConstraint("player_id"),
        )
        op.execute(sa.text("PRAGMA foreign_keys=OFF"))
        try:
            with op.batch_alter_table("qf_rounds", schema=None, copy_from=_qf_rounds_copy_table()) as batch_op:
                batch_op.create_check_constraint(
                    "valid_round_type",
                    "round_type IN ('prompt', 'copy', 'vote')",
                )
                batch_op.create_check_constraint(
                    "valid_round_status",
                    "status IN ('active', 'submitted', 'completed', 'expired', 'abandoned')",
                )
                batch_op.create_check_constraint(
                    "valid_phraseset_status",
                    "phraseset_status IN ('waiting_copies', 'waiting_copy1', 'active', 'finalized', 'abandoned', 'flagged_pending', 'flagged_removed', 'closed', 'closing', 'voting') OR phraseset_status IS NULL",
                )
        finally:
            op.execute(sa.text("PRAGMA foreign_keys=ON"))
    else:
        with op.batch_alter_table("qf_rounds", schema=None) as batch_op:
            batch_op.create_check_constraint(
                "valid_round_type",
                "round_type IN ('prompt', 'copy', 'vote')",
            )
            batch_op.create_check_constraint(
                "valid_round_status",
                "status IN ('active', 'submitted', 'completed', 'expired', 'abandoned')",
            )
            batch_op.create_check_constraint(
                "valid_phraseset_status",
                "phraseset_status IN ('waiting_copies', 'waiting_copy1', 'active', 'finalized', 'abandoned', 'flagged_pending', 'flagged_removed', 'closed', 'closing', 'voting') OR phraseset_status IS NULL",
            )
    op.create_index(
        "uq_qf_rounds_active_player",
        "qf_rounds",
        ["player_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    with op.batch_alter_table("qf_phrasesets", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "valid_phraseset_status",
            "status IN ('open', 'active', 'voting', 'closing', 'closed', 'finalized', 'abandoned')",
        )
        batch_op.create_unique_constraint(
            "uq_phrasesets_prompt_round_id",
            ["prompt_round_id"],
        )

    with op.batch_alter_table("party_sessions", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "valid_party_session_status",
            "status IN ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'ABANDONED')",
        )
        batch_op.create_check_constraint(
            "valid_party_session_phase",
            "current_phase IN ('LOBBY', 'PROMPT', 'COPY', 'VOTE', 'RESULTS', 'COMPLETED')",
        )

    with op.batch_alter_table("mm_vote_rounds", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "valid_mm_vote_round_abandoned",
            "abandoned IN (0, 1)",
        )
    op.create_index(
        "uq_mm_vote_round_active_player",
        "mm_vote_rounds",
        ["player_id"],
        unique=True,
        sqlite_where=sa.text("abandoned = 0 AND result_finalized_at IS NULL"),
        postgresql_where=sa.text("abandoned = false AND result_finalized_at IS NULL"),
    )

    with op.batch_alter_table("ir_backronym_sets", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "valid_ir_set_status",
            "status IN ('open', 'voting', 'finalized')",
        )
        batch_op.create_check_constraint(
            "valid_ir_set_mode",
            "mode IN ('standard', 'rapid')",
        )

    op.create_index(
        "uq_tl_round_active_player",
        "tl_round",
        ["player_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    # Ledger idempotency keys.
    op.add_column(
        "qf_transactions",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "mm_transactions",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ir_transactions",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tl_transaction",
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
    )

    for table_name in (
        "qf_transactions",
        "mm_transactions",
        "ir_transactions",
        "tl_transaction",
    ):
        _backfill_idempotency_keys(table_name)

    with op.batch_alter_table("qf_transactions", schema=None) as batch_op:
        batch_op.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_qf_transactions_idempotency_key",
            ["idempotency_key"],
        )

    with op.batch_alter_table("mm_transactions", schema=None) as batch_op:
        batch_op.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_mm_transactions_idempotency_key",
            ["idempotency_key"],
        )

    with op.batch_alter_table("ir_transactions", schema=None) as batch_op:
        batch_op.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_ir_transactions_idempotency_key",
            ["idempotency_key"],
        )

    with op.batch_alter_table("tl_transaction", schema=None) as batch_op:
        batch_op.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_tl_transaction_idempotency_key",
            ["idempotency_key"],
        )

    if op.get_bind().dialect.name == "sqlite":
        for replica_table in ("qf_players", "mm_players", "ir_players"):
            op.execute(
                sa.text(
                    f"INSERT OR IGNORE INTO {replica_table} (player_id) "
                    "SELECT player_id FROM players"
                )
            )
            op.execute(
                sa.text(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {replica_table}_ai
                    AFTER INSERT ON players
                    BEGIN
                        INSERT OR IGNORE INTO {replica_table} (player_id)
                        VALUES (NEW.player_id);
                    END
                    """
                )
            )
            op.execute(
                sa.text(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS {replica_table}_ad
                    AFTER DELETE ON players
                    BEGIN
                        DELETE FROM {replica_table}
                        WHERE player_id = OLD.player_id;
                    END
                    """
                )
            )


def downgrade() -> None:
    op.drop_constraint("uq_tl_transaction_idempotency_key", "tl_transaction", type_="unique")
    op.drop_constraint("uq_ir_transactions_idempotency_key", "ir_transactions", type_="unique")
    op.drop_constraint("uq_mm_transactions_idempotency_key", "mm_transactions", type_="unique")
    op.drop_constraint("uq_qf_transactions_idempotency_key", "qf_transactions", type_="unique")

    op.drop_index("uq_tl_round_active_player", table_name="tl_round")
    op.drop_index("uq_mm_vote_round_active_player", table_name="mm_vote_rounds")
    op.drop_index("uq_qf_rounds_active_player", table_name="qf_rounds")

    with op.batch_alter_table("ir_backronym_sets", schema=None) as batch_op:
        batch_op.drop_constraint("valid_ir_set_mode", type_="check")
        batch_op.drop_constraint("valid_ir_set_status", type_="check")

    with op.batch_alter_table("mm_vote_rounds", schema=None) as batch_op:
        batch_op.drop_constraint("valid_mm_vote_round_abandoned", type_="check")

    with op.batch_alter_table("party_sessions", schema=None) as batch_op:
        batch_op.drop_constraint("valid_party_session_phase", type_="check")
        batch_op.drop_constraint("valid_party_session_status", type_="check")

    with op.batch_alter_table("qf_phrasesets", schema=None) as batch_op:
        batch_op.drop_constraint("uq_phrasesets_prompt_round_id", type_="unique")
        batch_op.drop_constraint("valid_phraseset_status", type_="check")

    with op.batch_alter_table("qf_rounds", schema=None) as batch_op:
        batch_op.drop_constraint("valid_phraseset_status", type_="check")
        batch_op.drop_constraint("valid_round_status", type_="check")
        batch_op.drop_constraint("valid_round_type", type_="check")

    op.drop_column("tl_transaction", "idempotency_key")
    op.drop_column("ir_transactions", "idempotency_key")
    op.drop_column("mm_transactions", "idempotency_key")
    op.drop_column("qf_transactions", "idempotency_key")

    op.drop_column("tl_round", "version")
    op.drop_column("ir_backronym_sets", "version")
    op.drop_column("mm_vote_rounds", "version")
    op.drop_column("party_sessions", "version")
    op.drop_column("qf_phrasesets", "version")
    op.drop_column("qf_rounds", "version")