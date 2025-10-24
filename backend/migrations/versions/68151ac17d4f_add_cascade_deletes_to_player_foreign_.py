"""add_cascade_deletes_to_player_foreign_keys

Revision ID: 68151ac17d4f
Revises: f0703498ff94
Create Date: 2025-10-24 08:29:02.866612

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68151ac17d4f'
down_revision: Union[str, None] = 'f0703498ff94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add CASCADE delete to all foreign keys referencing players.player_id.

    This migration recreates constraints to add ON DELETE CASCADE,
    which allows the database to automatically delete dependent records
    when a player is deleted, simplifying cleanup operations.

    Affected tables:
    - daily_bonuses
    - player_abandoned_prompts
    - phraseset_activity
    - votes
    - rounds (player_id, copy1_player_id, copy2_player_id)
    - quests
    - result_views
    - transactions
    """
    # Detect database type
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        # PostgreSQL: Drop and recreate constraints with CASCADE
        # Note: Constraint names follow SQLAlchemy's naming convention

        # daily_bonuses
        op.drop_constraint("daily_bonuses_player_id_fkey", "daily_bonuses", type_="foreignkey")
        op.create_foreign_key(
            "daily_bonuses_player_id_fkey",
            "daily_bonuses", "players",
            ["player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # player_abandoned_prompts
        op.drop_constraint("player_abandoned_prompts_player_id_fkey", "player_abandoned_prompts", type_="foreignkey")
        op.create_foreign_key(
            "player_abandoned_prompts_player_id_fkey",
            "player_abandoned_prompts", "players",
            ["player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # phraseset_activity
        op.drop_constraint("phraseset_activity_player_id_fkey", "phraseset_activity", type_="foreignkey")
        op.create_foreign_key(
            "phraseset_activity_player_id_fkey",
            "phraseset_activity", "players",
            ["player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # votes
        op.drop_constraint("votes_player_id_fkey", "votes", type_="foreignkey")
        op.create_foreign_key(
            "votes_player_id_fkey",
            "votes", "players",
            ["player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # rounds - player_id
        op.drop_constraint("rounds_player_id_fkey", "rounds", type_="foreignkey")
        op.create_foreign_key(
            "rounds_player_id_fkey",
            "rounds", "players",
            ["player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # rounds - copy1_player_id
        op.drop_constraint("rounds_copy1_player_id_fkey", "rounds", type_="foreignkey")
        op.create_foreign_key(
            "rounds_copy1_player_id_fkey",
            "rounds", "players",
            ["copy1_player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # rounds - copy2_player_id
        op.drop_constraint("rounds_copy2_player_id_fkey", "rounds", type_="foreignkey")
        op.create_foreign_key(
            "rounds_copy2_player_id_fkey",
            "rounds", "players",
            ["copy2_player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # quests
        op.drop_constraint("quests_player_id_fkey", "quests", type_="foreignkey")
        op.create_foreign_key(
            "quests_player_id_fkey",
            "quests", "players",
            ["player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # result_views
        op.drop_constraint("result_views_player_id_fkey", "result_views", type_="foreignkey")
        op.create_foreign_key(
            "result_views_player_id_fkey",
            "result_views", "players",
            ["player_id"], ["player_id"],
            ondelete="CASCADE"
        )

        # transactions
        op.drop_constraint("transactions_player_id_fkey", "transactions", type_="foreignkey")
        op.create_foreign_key(
            "transactions_player_id_fkey",
            "transactions", "players",
            ["player_id"], ["player_id"],
            ondelete="CASCADE"
        )

    elif dialect_name == "sqlite":
        # SQLite doesn't support modifying foreign keys directly
        # For SQLite, the constraints are enforced at the model level
        # and will be applied on table recreation or in new databases
        # This is a no-op for existing SQLite databases
        pass


def downgrade() -> None:
    """
    Remove CASCADE delete from player foreign keys.

    This would revert the foreign keys to not cascade deletes,
    requiring manual deletion of dependent records.
    """
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    if dialect_name == "postgresql":
        # PostgreSQL: Revert to non-CASCADE constraints

        # daily_bonuses
        op.drop_constraint("daily_bonuses_player_id_fkey", "daily_bonuses", type_="foreignkey")
        op.create_foreign_key(
            "daily_bonuses_player_id_fkey",
            "daily_bonuses", "players",
            ["player_id"], ["player_id"]
        )

        # player_abandoned_prompts
        op.drop_constraint("player_abandoned_prompts_player_id_fkey", "player_abandoned_prompts", type_="foreignkey")
        op.create_foreign_key(
            "player_abandoned_prompts_player_id_fkey",
            "player_abandoned_prompts", "players",
            ["player_id"], ["player_id"]
        )

        # phraseset_activity
        op.drop_constraint("phraseset_activity_player_id_fkey", "phraseset_activity", type_="foreignkey")
        op.create_foreign_key(
            "phraseset_activity_player_id_fkey",
            "phraseset_activity", "players",
            ["player_id"], ["player_id"]
        )

        # votes
        op.drop_constraint("votes_player_id_fkey", "votes", type_="foreignkey")
        op.create_foreign_key(
            "votes_player_id_fkey",
            "votes", "players",
            ["player_id"], ["player_id"]
        )

        # rounds - player_id
        op.drop_constraint("rounds_player_id_fkey", "rounds", type_="foreignkey")
        op.create_foreign_key(
            "rounds_player_id_fkey",
            "rounds", "players",
            ["player_id"], ["player_id"]
        )

        # rounds - copy1_player_id
        op.drop_constraint("rounds_copy1_player_id_fkey", "rounds", type_="foreignkey")
        op.create_foreign_key(
            "rounds_copy1_player_id_fkey",
            "rounds", "players",
            ["copy1_player_id"], ["player_id"]
        )

        # rounds - copy2_player_id
        op.drop_constraint("rounds_copy2_player_id_fkey", "rounds", type_="foreignkey")
        op.create_foreign_key(
            "rounds_copy2_player_id_fkey",
            "rounds", "players",
            ["copy2_player_id"], ["player_id"]
        )

        # quests
        op.drop_constraint("quests_player_id_fkey", "quests", type_="foreignkey")
        op.create_foreign_key(
            "quests_player_id_fkey",
            "quests", "players",
            ["player_id"], ["player_id"]
        )

        # result_views
        op.drop_constraint("result_views_player_id_fkey", "result_views", type_="foreignkey")
        op.create_foreign_key(
            "result_views_player_id_fkey",
            "result_views", "players",
            ["player_id"], ["player_id"]
        )

        # transactions
        op.drop_constraint("transactions_player_id_fkey", "transactions", type_="foreignkey")
        op.create_foreign_key(
            "transactions_player_id_fkey",
            "transactions", "players",
            ["player_id"], ["player_id"]
        )

    elif dialect_name == "sqlite":
        # No-op for SQLite (constraints are at model level)
        pass
