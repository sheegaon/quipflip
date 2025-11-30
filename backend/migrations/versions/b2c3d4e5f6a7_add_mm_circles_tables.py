"""Add Meme Mint Circles tables for social groups.

Revision ID: b2c3d4e5f6a7
Revises: a0b1c2d3e4f5
Create Date: 2025-11-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.migrations.util import get_uuid_type, get_timestamp_default

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid = get_uuid_type()
    timestamp_default = get_timestamp_default()

    # Create mm_circles table
    op.create_table(
        "mm_circles",
        sa.Column("circle_id", uuid, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_player_id", uuid, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(
            ["created_by_player_id"],
            ["mm_players.player_id"],
            name=op.f("fk_mm_circles_created_by_player_id_mm_players"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("circle_id", name=op.f("pk_mm_circles")),
        sa.UniqueConstraint("name", name=op.f("uq_mm_circles_name")),
    )
    op.create_index(op.f("ix_mm_circles_created_by_player_id"), "mm_circles", ["created_by_player_id"], unique=False)
    op.create_index(op.f("ix_mm_circles_status"), "mm_circles", ["status"], unique=False)

    # Create mm_circle_members table
    op.create_table(
        "mm_circle_members",
        sa.Column("circle_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.ForeignKeyConstraint(
            ["circle_id"],
            ["mm_circles.circle_id"],
            name=op.f("fk_mm_circle_members_circle_id_mm_circles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["mm_players.player_id"],
            name=op.f("fk_mm_circle_members_player_id_mm_players"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("circle_id", "player_id", name=op.f("pk_mm_circle_members"))

    )
    op.create_index(op.f("ix_mm_circle_members_player_id"), "mm_circle_members", ["player_id"], unique=False)

    # Create mm_circle_join_requests table
    op.create_table(
        "mm_circle_join_requests",
        sa.Column("request_id", uuid, nullable=False),
        sa.Column("circle_id", uuid, nullable=False),
        sa.Column("player_id", uuid, nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=timestamp_default),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_player_id", uuid, nullable=True),
        sa.ForeignKeyConstraint(
            ["circle_id"],
            ["mm_circles.circle_id"],
            name=op.f("fk_mm_circle_join_requests_circle_id_mm_circles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["mm_players.player_id"],
            name=op.f("fk_mm_circle_join_requests_player_id_mm_players"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_player_id"],
            ["mm_players.player_id"],
            name=op.f("fk_mm_circle_join_requests_resolved_by_player_id_mm_players"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("request_id", name=op.f("pk_mm_circle_join_requests")),
        sa.UniqueConstraint("circle_id", "player_id", name="uq_mm_circle_join_request"),
    )
    op.create_index(
        op.f("ix_mm_circle_join_requests_circle_id"),
        "mm_circle_join_requests",
        ["circle_id"],
        unique=False
    )
    op.create_index(
        op.f("ix_mm_circle_join_requests_player_id"),
        "mm_circle_join_requests",
        ["player_id"],
        unique=False
    )
    op.create_index(
        op.f("ix_mm_circle_join_requests_status"),
        "mm_circle_join_requests",
        ["status"],
        unique=False
    )


def downgrade() -> None:
    # Drop tables in reverse order to respect foreign keys
    op.drop_table("mm_circle_join_requests")
    op.drop_table("mm_circle_members")
    op.drop_table("mm_circles")
