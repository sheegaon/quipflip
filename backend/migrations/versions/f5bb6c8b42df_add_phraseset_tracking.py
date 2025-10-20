"""add phraseset activity tracking

Revision ID: f5bb6c8b42df
Revises: a0e94cafee86
Create Date: 2025-10-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f5bb6c8b42df"
down_revision: Union[str, None] = "a0e94cafee86"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_column():
    """Utility to get portable UUID column."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"
    if dialect_name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(length=36)


def _json_column():
    """Return a JSON-capable column that works on SQLite and Postgres."""
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"
    if dialect_name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON().with_variant(sa.Text(), "sqlite")


def upgrade() -> None:
    uuid = _uuid_column()
    metadata_type = _json_column()

    # Create phraseset_activity table
    op.create_table(
        "phraseset_activity",
        sa.Column("activity_id", uuid, nullable=False),
        sa.Column("phraseset_id", uuid, nullable=True),
        sa.Column("prompt_round_id", uuid, nullable=True),
        sa.Column("activity_type", sa.String(length=50), nullable=False),
        sa.Column("player_id", uuid, nullable=True),
        sa.Column("metadata", metadata_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["phraseset_id"], ["phrasesets.phraseset_id"]),
        sa.ForeignKeyConstraint(["prompt_round_id"], ["rounds.round_id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.player_id"]),
        sa.PrimaryKeyConstraint("activity_id"),
    )
    op.create_index(
        "ix_phraseset_activity_phraseset_id_created",
        "phraseset_activity",
        ["phraseset_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_phraseset_activity_prompt_round_id_created",
        "phraseset_activity",
        ["prompt_round_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_phraseset_activity_player_id_created",
        "phraseset_activity",
        ["player_id", "created_at"],
        unique=False,
    )

    # Update rounds table with status tracking
    with op.batch_alter_table("rounds", schema=None) as batch_op:
        batch_op.add_column(sa.Column("phraseset_status", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("copy1_player_id", uuid, nullable=True))
        batch_op.add_column(sa.Column("copy2_player_id", uuid, nullable=True))
        batch_op.create_foreign_key(
            "fk_rounds_copy1_player_id",
            "players",
            ["copy1_player_id"],
            ["player_id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_rounds_copy2_player_id",
            "players",
            ["copy2_player_id"],
            ["player_id"],
            ondelete="SET NULL",
        )

    op.create_index(
        "ix_rounds_copy1_player_id",
        "rounds",
        ["copy1_player_id"],
        unique=False,
    )
    op.create_index(
        "ix_rounds_copy2_player_id",
        "rounds",
        ["copy2_player_id"],
        unique=False,
    )
    op.create_index(
        "ix_rounds_phraseset_status",
        "rounds",
        ["phraseset_status"],
        unique=False,
    )

    # Update result_views table for claim tracking
    op.drop_index("ix_result_views_payout_collected", table_name="result_views")
    with op.batch_alter_table("result_views", schema=None) as batch_op:
        batch_op.add_column(sa.Column("first_viewed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("payout_claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column("payout_collected", new_column_name="payout_claimed")
    op.create_index(
        "ix_result_views_payout_claimed",
        "result_views",
        ["payout_claimed"],
        unique=False,
    )

    # Backfill claim timestamps
    op.execute(
        """
        UPDATE result_views
        SET first_viewed_at = viewed_at,
            payout_claimed_at = CASE WHEN payout_claimed THEN viewed_at ELSE NULL END
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind else "postgresql"
    true_literal = "TRUE" if dialect_name == "postgresql" else "1"

    # Revert result_views changes
    op.execute(
        f"""
        UPDATE result_views
        SET payout_claimed = CASE WHEN payout_claimed_at IS NOT NULL THEN {true_literal} ELSE payout_claimed END,
            payout_claimed_at = NULL,
            first_viewed_at = NULL
        """
    )
    op.drop_index("ix_result_views_payout_claimed", table_name="result_views")
    with op.batch_alter_table("result_views", schema=None) as batch_op:
        batch_op.alter_column("payout_claimed", new_column_name="payout_collected")
        batch_op.drop_column("payout_claimed_at")
        batch_op.drop_column("first_viewed_at")
    op.create_index(
        "ix_result_views_payout_collected",
        "result_views",
        ["payout_collected"],
        unique=False,
    )

    # Drop new indexes on rounds
    op.drop_index("ix_rounds_phraseset_status", table_name="rounds")
    op.drop_index("ix_rounds_copy2_player_id", table_name="rounds")
    op.drop_index("ix_rounds_copy1_player_id", table_name="rounds")

    with op.batch_alter_table("rounds", schema=None) as batch_op:
        batch_op.drop_constraint("fk_rounds_copy2_player_id", type_="foreignkey")
        batch_op.drop_constraint("fk_rounds_copy1_player_id", type_="foreignkey")
        batch_op.drop_column("copy2_player_id")
        batch_op.drop_column("copy1_player_id")
        batch_op.drop_column("phraseset_status")

    # Drop phraseset_activity table
    op.drop_index("ix_phraseset_activity_player_id_created", table_name="phraseset_activity")
    op.drop_index("ix_phraseset_activity_prompt_round_id_created", table_name="phraseset_activity")
    op.drop_index("ix_phraseset_activity_phraseset_id_created", table_name="phraseset_activity")
    op.drop_table("phraseset_activity")
