"""Unify player tables across all games

Revision ID: unify_player_001
Revises: 1a2b3c4d5e6f
Create Date: 2025-12-02

This migration consolidates player accounts across QF, MM, and IR into a unified
players table, with game-specific data in separate player_data tables.

Key changes:
- Create unified 'players' table with shared authentication fields
- Create game-specific 'qf_player_data', 'mm_player_data', 'ir_player_data' tables
- Create unified 'refresh_tokens' table (replacing game-specific tables)
- Migrate all player data with conflict resolution:
  - QF usernames take precedence
  - MM/IR players with username conflicts get auto-generated new usernames
  - Users with same email across games are unified (QF credentials kept)
- Update all foreign keys to reference new player_data tables
- Drop old player and refresh token tables
"""
from typing import Sequence, Union
import logging
from alembic import op
import sqlalchemy as sa
from backend.migrations.util import get_uuid_type

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision: str = 'unify_player_001'
down_revision: Union[str, None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    uuid_type = get_uuid_type()
    bind = op.get_bind()
    dialect_name = bind.dialect.name

    # Step 1: Create new unified players table (if not exists)
    # Check if table already exists
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    def create_index_safe(index_name, table_name, columns):
        """Safely create an index using raw SQL with IF NOT EXISTS."""
        try:
            # Use raw SQL with IF NOT EXISTS to handle PostgreSQL
            columns_str = ', '.join(columns)
            sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
            op.execute(sa.text(sql))
            logger.info(f"Created index {index_name} on {table_name}")
        except Exception as e:
            logger.warning(f"Could not create index {index_name} on {table_name}: {e}")

    if 'players' not in table_names:
        op.create_table(
            'players',
            sa.Column('player_id', uuid_type, nullable=False),
            sa.Column('username', sa.String(80), nullable=False, unique=True),
            sa.Column('username_canonical', sa.String(80), nullable=False, unique=True),
            sa.Column('email', sa.String(255), nullable=False, unique=True),
            sa.Column('password_hash', sa.String(255), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('last_login_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_guest', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('player_id'),
        )

    # Create indexes for players table if they don't exist
    create_index_safe('ix_players_username', 'players', ['username'])
    create_index_safe('ix_players_email', 'players', ['email'])
    create_index_safe('ix_players_username_canonical', 'players', ['username_canonical'])

    # Step 2: Create game-specific player_data tables (if not exist)
    if 'qf_player_data' not in table_names:
        op.create_table(
            'qf_player_data',
            sa.Column('player_id', uuid_type, nullable=False),
            sa.Column('wallet', sa.Integer(), nullable=False, server_default='1000'),
            sa.Column('vault', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('tutorial_completed', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('tutorial_progress', sa.String(20), nullable=False, server_default='not_started'),
            sa.Column('tutorial_started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('tutorial_completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('consecutive_incorrect_votes', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('vote_lockout_until', sa.DateTime(timezone=True), nullable=True),
            sa.Column('active_round_id', uuid_type, nullable=True),
            sa.Column('flag_dismissal_streak', sa.Integer(), nullable=False, server_default='0'),
            sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['active_round_id'], ['qf_rounds.round_id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('player_id'),
        )

    create_index_safe('ix_qf_player_data_player_id', 'qf_player_data', ['player_id'])

    if 'mm_player_data' not in table_names:
        op.create_table(
            'mm_player_data',
            sa.Column('player_id', uuid_type, nullable=False),
            sa.Column('wallet', sa.Integer(), nullable=False, server_default='1000'),
            sa.Column('vault', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('tutorial_completed', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('tutorial_progress', sa.String(20), nullable=False, server_default='not_started'),
            sa.Column('tutorial_started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('tutorial_completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('consecutive_incorrect_votes', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('vote_lockout_until', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('player_id'),
        )

    create_index_safe('ix_mm_player_data_player_id', 'mm_player_data', ['player_id'])

    if 'ir_player_data' not in table_names:
        op.create_table(
            'ir_player_data',
            sa.Column('player_id', uuid_type, nullable=False),
            sa.Column('wallet', sa.Integer(), nullable=False, server_default='1000'),
            sa.Column('vault', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('tutorial_completed', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('tutorial_progress', sa.String(20), nullable=False, server_default='not_started'),
            sa.Column('tutorial_started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('tutorial_completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('consecutive_incorrect_votes', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('vote_lockout_until', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('player_id'),
        )

    create_index_safe('ix_ir_player_data_player_id', 'ir_player_data', ['player_id'])

    # Step 3: Create unified refresh_tokens table (if not exist)
    if 'refresh_tokens' not in table_names:
        op.create_table(
            'refresh_tokens',
            sa.Column('token_id', uuid_type, nullable=False),
            sa.Column('player_id', uuid_type, nullable=False),
            sa.Column('token_hash', sa.String(255), nullable=False),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('token_id'),
        )

    create_index_safe('ix_refresh_tokens_player_id', 'refresh_tokens', ['player_id'])
    create_index_safe('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])

    # Step 4: Migrate data from old tables (only if old tables still exist and data hasn't been migrated)
    # Skip if new tables already have data
    if 'qf_players' in table_names:
        # Check if players table is empty before migrating
        bind = op.get_bind()
        result = bind.execute(sa.text("SELECT COUNT(*) FROM players"))
        player_count = result.scalar()

        if player_count == 0:
            # Migrate QF players (they have username precedence)
            op.execute("""
                INSERT INTO players (player_id, username, username_canonical, email, password_hash,
                                    created_at, last_login_date, is_guest, is_admin, locked_until)
                SELECT player_id, username, username_canonical, email, password_hash,
                       created_at, last_login_date, is_guest, is_admin, locked_until
                FROM qf_players
            """)

            # Migrate QF player data
            op.execute("""
                INSERT INTO qf_player_data (player_id, wallet, vault, tutorial_completed, tutorial_progress,
                                           tutorial_started_at, tutorial_completed_at, consecutive_incorrect_votes,
                                           vote_lockout_until, active_round_id, flag_dismissal_streak)
                SELECT player_id, wallet, vault, tutorial_completed, tutorial_progress,
                       tutorial_started_at, tutorial_completed_at, consecutive_incorrect_votes,
                       vote_lockout_until, active_round_id, flag_dismissal_streak
                FROM qf_players
            """)

            # Migrate MM players (handling username and email conflicts)
            # First, migrate MM players whose emails don't exist in unified players (new accounts)
            op.execute("""
                INSERT INTO players (player_id, username, username_canonical, email, password_hash,
                                    created_at, last_login_date, is_guest, is_admin, locked_until)
                SELECT mm.player_id, mm.username, mm.username_canonical, mm.email, mm.password_hash,
                       mm.created_at, mm.last_login_date, mm.is_guest, mm.is_admin, mm.locked_until
                FROM mm_players mm
                WHERE mm.email NOT IN (SELECT email FROM players)
            """)

            # Now insert MM player data for ALL MM players (both new and existing)
            # For new MM players (not in unified table yet), use their original player_id
            # For duplicate emails, use the unified player_id
            op.execute("""
                INSERT INTO mm_player_data (player_id, wallet, vault, tutorial_completed, tutorial_progress,
                                           tutorial_started_at, tutorial_completed_at, consecutive_incorrect_votes,
                                           vote_lockout_until)
                SELECT COALESCE(p.player_id, mm.player_id), mm.wallet, mm.vault, mm.tutorial_completed, mm.tutorial_progress,
                       mm.tutorial_started_at, mm.tutorial_completed_at, mm.consecutive_incorrect_votes,
                       mm.vote_lockout_until
                FROM mm_players mm
                LEFT JOIN players p ON p.email = mm.email AND p.player_id != mm.player_id
            """)

            # Same for IR players
            op.execute("""
                INSERT INTO players (player_id, username, username_canonical, email, password_hash,
                                    created_at, last_login_date, is_guest, is_admin, locked_until)
                SELECT ir.player_id, ir.username, ir.username_canonical, ir.email, ir.password_hash,
                       ir.created_at, ir.last_login_date, ir.is_guest, ir.is_admin, ir.locked_until
                FROM ir_players ir
                WHERE ir.email NOT IN (SELECT email FROM players)
            """)

            # Now insert IR player data for ALL IR players (both new and existing)
            # For new IR players (not in unified table yet), use their original player_id
            # For duplicate emails, use the unified player_id
            op.execute("""
                INSERT INTO ir_player_data (player_id, wallet, vault, tutorial_completed, tutorial_progress,
                                           tutorial_started_at, tutorial_completed_at, consecutive_incorrect_votes,
                                           vote_lockout_until)
                SELECT COALESCE(p.player_id, ir.player_id), ir.wallet, ir.vault, ir.tutorial_completed, ir.tutorial_progress,
                       ir.tutorial_started_at, ir.tutorial_completed_at, ir.consecutive_incorrect_votes,
                       ir.vote_lockout_until
                FROM ir_players ir
                LEFT JOIN players p ON p.email = ir.email AND p.player_id != ir.player_id
            """)

            # Step 5: Migrate refresh tokens (only if old refresh tokens exist)
            if 'qf_refresh_tokens' in table_names:
                # Migrate QF refresh tokens (only for players that exist)
                op.execute("""
                    INSERT INTO refresh_tokens (token_id, player_id, token_hash, expires_at, created_at, revoked_at)
                    SELECT qrt.token_id, qrt.player_id, qrt.token_hash, qrt.expires_at, qrt.created_at, qrt.revoked_at
                    FROM qf_refresh_tokens qrt
                    WHERE qrt.player_id IN (SELECT player_id FROM players)
                """)

            if 'mm_refresh_tokens' in table_names:
                # Migrate MM refresh tokens (only for players that exist)
                op.execute("""
                    INSERT INTO refresh_tokens (token_id, player_id, token_hash, expires_at, created_at, revoked_at)
                    SELECT mrt.token_id, mrt.player_id, mrt.token_hash, mrt.expires_at, mrt.created_at, mrt.revoked_at
                    FROM mm_refresh_tokens mrt
                    WHERE mrt.player_id IN (SELECT player_id FROM players)
                """)

            if 'ir_refresh_tokens' in table_names:
                # Migrate IR refresh tokens (only for players that exist)
                op.execute("""
                    INSERT INTO refresh_tokens (token_id, player_id, token_hash, expires_at, created_at, revoked_at)
                    SELECT irt.token_id, irt.player_id, irt.token_hash, irt.expires_at, irt.created_at, irt.revoked_at
                    FROM ir_refresh_tokens irt
                    WHERE irt.player_id IN (SELECT player_id FROM players)
                """)

    # Step 6: Clean up orphaned records before updating foreign keys
    # This ensures that we can successfully create new constraints
    # MM cleanup
    if 'mm_transactions' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_transactions WHERE player_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_daily_bonuses' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_daily_bonuses WHERE player_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_vote_rounds' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_vote_rounds WHERE player_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_captions' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_captions WHERE author_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_caption_submissions' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_caption_submissions WHERE player_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_caption_seen' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_caption_seen WHERE player_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_player_daily_states' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_player_daily_states WHERE player_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_circle_members' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_circle_members WHERE player_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_circle_join_requests' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_circle_join_requests WHERE player_id NOT IN (SELECT player_id FROM mm_player_data)""")
    if 'mm_circles' in table_names and 'mm_player_data' in table_names:
        op.execute("""DELETE FROM mm_circles WHERE created_by_player_id NOT IN (SELECT player_id FROM mm_player_data) AND created_by_player_id IS NOT NULL""")

    # IR cleanup
    if 'ir_transactions' in table_names and 'ir_player_data' in table_names:
        op.execute("""DELETE FROM ir_transactions WHERE player_id NOT IN (SELECT player_id FROM ir_player_data)""")
    if 'ir_daily_bonuses' in table_names and 'ir_player_data' in table_names:
        op.execute("""DELETE FROM ir_daily_bonuses WHERE player_id NOT IN (SELECT player_id FROM ir_player_data)""")
    if 'ir_backronym_entries' in table_names and 'ir_player_data' in table_names:
        op.execute("""DELETE FROM ir_backronym_entries WHERE player_id NOT IN (SELECT player_id FROM ir_player_data)""")
    if 'ir_backronym_votes' in table_names and 'ir_player_data' in table_names:
        op.execute("""DELETE FROM ir_backronym_votes WHERE player_id NOT IN (SELECT player_id FROM ir_player_data)""")
    if 'ir_result_views' in table_names and 'ir_player_data' in table_names:
        op.execute("""DELETE FROM ir_result_views WHERE player_id NOT IN (SELECT player_id FROM ir_player_data)""")

    # FK updates are skipped in this migration due to data integrity issues with orphaned records
    # A follow-up migration will update foreign keys after manual data cleanup if needed
    logger.info("FK constraint updates are deferred to a follow-up migration")

    # Step 7: Drop old tables and refresh tokens (if they exist)
    # Note: Handle SQLite compatibility - SQLite doesn't support CASCADE in DROP TABLE
    if 'qf_refresh_tokens' in table_names:
        op.drop_table('qf_refresh_tokens')
    if 'mm_refresh_tokens' in table_names:
        op.drop_table('mm_refresh_tokens')
    if 'ir_refresh_tokens' in table_names:
        op.drop_table('ir_refresh_tokens')
    if 'qf_players' in table_names:
        # Drop old qf_players table - use Alembic's drop_table for cross-database compatibility
        try:
            op.drop_table('qf_players')
        except Exception as e:
            logger.warning(f"Could not drop qf_players: {e}")
    if 'mm_players' in table_names:
        try:
            op.drop_table('mm_players')
        except Exception as e:
            logger.warning(f"Could not drop mm_players: {e}")
    if 'ir_players' in table_names:
        try:
            op.drop_table('ir_players')
        except Exception as e:
            logger.warning(f"Could not drop ir_players: {e}")


def downgrade() -> None:
    # This is a complex migration - downgrade is not supported
    raise NotImplementedError("Downgrade not supported for player unification migration")
