"""Add username support to players.

Revision ID: 1b7f94ab2cba
Revises: b4259daa4cd5
Create Date: 2025-10-21 15:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from backend.scripts.username_pool import USERNAME_POOL

# revision identifiers, used by Alembic.
revision: str = "1b7f94ab2cba"
down_revision: Union[str, None] = "b4259daa4cd5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize(name: str) -> str:
    return " ".join(name.split())


def _canonicalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _username_generator(taken: set[str]):
    seen = set(taken)
    suffix_counts: dict[str, int] = {}

    for base in USERNAME_POOL:
        display = _normalize(base)
        canonical = _canonicalize(display)
        if not canonical:
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        suffix_counts[canonical] = 1
        yield display, canonical

    while True:
        for base in USERNAME_POOL:
            display = _normalize(base)
            base_canonical = _canonicalize(display)
            if not base_canonical:
                continue

            count = suffix_counts.get(base_canonical, 1) + 1
            suffix_counts[base_canonical] = count

            candidate_display = f"{display} {count}"
            canonical = _canonicalize(candidate_display)
            if not canonical or canonical in seen:
                continue

            seen.add(canonical)
            yield candidate_display, canonical


def upgrade() -> None:
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=80), nullable=True))
        batch_op.add_column(
            sa.Column("username_canonical", sa.String(length=80), nullable=True)
        )

    bind = op.get_bind()
    result = bind.execute(sa.text("SELECT username_canonical FROM players"))
    existing = {row[0] for row in result if row[0]}
    generator = _username_generator(existing)

    players = bind.execute(
        sa.text("SELECT player_id FROM players ORDER BY created_at")
    ).fetchall()

    for (player_id,) in players:
        username, canonical = next(generator)
        bind.execute(
            sa.text(
                "UPDATE players "
                "SET username = :username, username_canonical = :canonical "
                "WHERE player_id = :player_id"
            ),
            {"username": username, "canonical": canonical, "player_id": str(player_id)},
        )

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.alter_column(
            "username",
            existing_type=sa.String(length=80),
            nullable=False,
        )
        batch_op.alter_column(
            "username_canonical",
            existing_type=sa.String(length=80),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_players_username", ["username"]
        )
        batch_op.create_unique_constraint(
            "uq_players_username_canonical", ["username_canonical"]
        )


def downgrade() -> None:
    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.drop_constraint("uq_players_username_canonical", type_="unique")
        batch_op.drop_constraint("uq_players_username", type_="unique")
        batch_op.drop_column("username_canonical")
        batch_op.drop_column("username")

