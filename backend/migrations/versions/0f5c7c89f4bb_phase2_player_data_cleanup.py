"""phase2_player_data_cleanup

Move remaining game-specific player columns into qf_player_data and
remove implicit defaults from the global players table.

Revision ID: 0f5c7c89f4bb
Revises: a0e94cafee86
Create Date: 2026-01-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from backend.migrations.util import get_uuid_type

# revision identifiers, used by Alembic.
revision: str = "0f5c7c89f4bb"
down_revision: Union[str, None] = "a0e94cafee86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Dialect-aware helpers follow guidance from HEROKU_MIGRATION_LESSONS.
def _column_exists(bind, table_name: str, column_name: str) -> bool:
    dialect = bind.dialect.name

    if dialect == "postgresql":
        result = bind.execute(
            sa.text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.columns
                    WHERE table_name = :table_name AND column_name = :column_name
                )
                """
            ).bindparams(table_name=table_name, column_name=column_name)
        )
        return bool(result.scalar())

    if dialect == "sqlite":
        result = bind.execute(sa.text(f"PRAGMA table_info({table_name})"))
        return column_name in [row[1] for row in result.fetchall()]

    return False


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _build_players_select(bind) -> str:
    columns = {
        "wallet": "COALESCE(p.wallet, 1000)",
        "vault": "COALESCE(p.vault, 0)",
        "tutorial_completed": "COALESCE(p.tutorial_completed, false)",
        "tutorial_progress": "COALESCE(p.tutorial_progress, 'not_started')",
        "tutorial_started_at": "p.tutorial_started_at",
        "tutorial_completed_at": "p.tutorial_completed_at",
        "consecutive_incorrect_votes": "COALESCE(p.consecutive_incorrect_votes, 0)",
        "vote_lockout_until": "p.vote_lockout_until",
        "active_round_id": "p.active_round_id",
        "flag_dismissal_streak": "COALESCE(p.flag_dismissal_streak, 0)",
    }

    bind_text = "SELECT p.player_id"

    for column, expr in columns.items():
        if _column_exists(bind, "players", column):
            bind_text += f", {expr} AS {column}"
        else:
            # Use safe defaults when the column is absent to keep the insert valid
            default_expr = {
                "wallet": "1000",
                "vault": "0",
                "consecutive_incorrect_votes": "0",
                "flag_dismissal_streak": "0",
                "tutorial_completed": "false",
                "tutorial_progress": "'not_started'",
            }.get(column, "NULL")
            bind_text += f", {default_expr} AS {column}"

    bind_text += " FROM players p"
    bind_text += " LEFT JOIN qf_player_data q ON q.player_id = p.player_id"
    bind_text += " WHERE q.player_id IS NULL"
    return bind_text


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "qf_player_data"):
        uuid = get_uuid_type()
        op.create_table(
            "qf_player_data",
            sa.Column("player_id", uuid, nullable=False),
            sa.Column("wallet", sa.Integer(), nullable=False, server_default="1000"),
            sa.Column("vault", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tutorial_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("tutorial_progress", sa.String(length=20), nullable=False, server_default="not_started"),
            sa.Column("tutorial_started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tutorial_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("consecutive_incorrect_votes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("vote_lockout_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("active_round_id", uuid, nullable=True),
            sa.Column("flag_dismissal_streak", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["player_id"], ["players.player_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("player_id"),
        )

    # Backfill qf_player_data rows for any players missing a per-game record.
    insert_sql = _build_players_select(bind)
    op.execute(
        sa.text(
            """
            INSERT INTO qf_player_data (
                player_id,
                wallet,
                vault,
                tutorial_completed,
                tutorial_progress,
                tutorial_started_at,
                tutorial_completed_at,
                consecutive_incorrect_votes,
                vote_lockout_until,
                active_round_id,
                flag_dismissal_streak
            )
            """
            + insert_sql
        )
    )

    # Drop migrated columns from players if they still exist
    columns_to_drop = [
        "wallet",
        "vault",
        "tutorial_completed",
        "tutorial_progress",
        "tutorial_started_at",
        "tutorial_completed_at",
        "consecutive_incorrect_votes",
        "vote_lockout_until",
        "active_round_id",
        "flag_dismissal_streak",
    ]

    for column in columns_to_drop:
        if _column_exists(bind, "players", column):
            op.drop_column("players", column)


def downgrade() -> None:
    bind = op.get_bind()

    # Recreate columns with reasonable defaults if they were removed
    if not _column_exists(bind, "players", "wallet"):
        op.add_column("players", sa.Column("wallet", sa.Integer(), nullable=False, server_default="1000"))
    if not _column_exists(bind, "players", "vault"):
        op.add_column("players", sa.Column("vault", sa.Integer(), nullable=False, server_default="0"))
    if not _column_exists(bind, "players", "tutorial_completed"):
        op.add_column(
            "players",
            sa.Column("tutorial_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _column_exists(bind, "players", "tutorial_progress"):
        op.add_column(
            "players",
            sa.Column("tutorial_progress", sa.String(length=20), nullable=False, server_default="not_started"),
        )
    if not _column_exists(bind, "players", "tutorial_started_at"):
        op.add_column("players", sa.Column("tutorial_started_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "players", "tutorial_completed_at"):
        op.add_column("players", sa.Column("tutorial_completed_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "players", "consecutive_incorrect_votes"):
        op.add_column("players", sa.Column("consecutive_incorrect_votes", sa.Integer(), nullable=False, server_default="0"))
    if not _column_exists(bind, "players", "vote_lockout_until"):
        op.add_column("players", sa.Column("vote_lockout_until", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(bind, "players", "active_round_id"):
        uuid = get_uuid_type()
        op.add_column("players", sa.Column("active_round_id", uuid, nullable=True))
    if not _column_exists(bind, "players", "flag_dismissal_streak"):
        op.add_column("players", sa.Column("flag_dismissal_streak", sa.Integer(), nullable=False, server_default="0"))

    # Backfill players table from qf_player_data when available
    if _table_exists(bind, "qf_player_data"):
        op.execute(
            sa.text(
                """
                UPDATE players
                SET
                    wallet = (SELECT q.wallet FROM qf_player_data q WHERE q.player_id = players.player_id),
                    vault = (SELECT q.vault FROM qf_player_data q WHERE q.player_id = players.player_id),
                    tutorial_completed = (SELECT q.tutorial_completed FROM qf_player_data q WHERE q.player_id = players.player_id),
                    tutorial_progress = (SELECT q.tutorial_progress FROM qf_player_data q WHERE q.player_id = players.player_id),
                    tutorial_started_at = (SELECT q.tutorial_started_at FROM qf_player_data q WHERE q.player_id = players.player_id),
                    tutorial_completed_at = (SELECT q.tutorial_completed_at FROM qf_player_data q WHERE q.player_id = players.player_id),
                    consecutive_incorrect_votes = (SELECT q.consecutive_incorrect_votes FROM qf_player_data q WHERE q.player_id = players.player_id),
                    vote_lockout_until = (SELECT q.vote_lockout_until FROM qf_player_data q WHERE q.player_id = players.player_id),
                    active_round_id = (SELECT q.active_round_id FROM qf_player_data q WHERE q.player_id = players.player_id),
                    flag_dismissal_streak = (SELECT q.flag_dismissal_streak FROM qf_player_data q WHERE q.player_id = players.player_id)
                WHERE EXISTS (
                    SELECT 1 FROM qf_player_data q WHERE q.player_id = players.player_id
                )
                """
            )
        )
