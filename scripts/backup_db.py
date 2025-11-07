#!/usr/bin/env python3
"""
Database backup script.

This script reads all data from the remote database (specified by DATABASE_URL env var)
and creates a local SQLite backup at temp.db with all the data.

Usage:
    python scripts/backup_db.py

Environment Variables:
    DATABASE_URL - Connection string for the source database
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from alembic.config import Config
from alembic import command

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
# Import all models to ensure they're registered with SQLAlchemy
from backend.models import (
    Player, Prompt, Round, Phraseset, Vote,
    Transaction, DailyBonus, ResultView, PlayerAbandonedPrompt,
    PromptFeedback, PhrasesetActivity, RefreshToken,
    Quest, QuestTemplate, SystemConfig, FlaggedPrompt, SurveyResponse
)
from backend.config import get_settings
from backend.database import Base

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Target backup database path
BACKUP_DB_PATH = "quipflip.db"
BACKUP_DB_URL = f"sqlite:///{BACKUP_DB_PATH}"
BACKUP_DB_ASYNC_URL = f"sqlite+aiosqlite:///{BACKUP_DB_PATH}"


def serialize_value(value: Any) -> Any:
    """
    Convert database values to SQLite-compatible types.

    Args:
        value: Value from database row

    Returns:
        SQLite-compatible value
    """
    if isinstance(value, UUID):
        return str(value)
    return value


async def fetch_all_data_from_remote(source_url: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch all data from the remote database.

    Args:
        source_url: Database connection URL

    Returns:
        Dictionary mapping table names to lists of row dictionaries
    """
    logger.info(f"Connecting to source database...")

    # Create async engine for source database
    source_engine = create_async_engine(
        source_url,
        echo=False,
        pool_pre_ping=True,
    )

    # Create session
    AsyncSessionLocal = async_sessionmaker(
        source_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    all_data = {}

    try:
        async with AsyncSessionLocal() as session:
            # Dynamically discover models from the declarative base
            tables_to_backup = []
            for mapper in Base.registry.mappers:
                # Ensure it's a mapped table and not the alembic version table
                if hasattr(mapper.class_, '__tablename__') and mapper.local_table.name != 'alembic_version':
                    tables_to_backup.append((mapper.local_table.name, mapper.class_))

            # Sort by table name for deterministic order, which is good practice.
            tables_to_backup.sort(key=lambda x: x[0])

            for table_name, model in tables_to_backup:
                logger.info(f"Fetching data from table: {table_name}")
                try:
                    # Use SQLAlchemy to fetch all records
                    from sqlalchemy import select
                    result = await session.execute(select(model))
                    rows = result.scalars().all()

                    # Convert to dictionaries with SQLite-compatible types
                    row_dicts = [
                        {column.name: serialize_value(getattr(row, column.name)) for column in model.__table__.columns}
                        for row in rows
                    ]

                    all_data[table_name] = row_dicts
                    logger.info(f"  Fetched {len(row_dicts)} rows from {table_name}")

                except Exception as e:
                    logger.warning(f"  Error fetching from {table_name}: {e}")
                    all_data[table_name] = []

    finally:
        await source_engine.dispose()

    return all_data


def create_backup_database():
    """
    Create a new SQLite database at temp.db using Alembic migrations.
    """
    logger.info(f"Creating backup database at {BACKUP_DB_PATH}")

    # Remove existing backup if it exists
    if os.path.exists(BACKUP_DB_PATH):
        logger.info(f"Removing existing backup database")
        os.remove(BACKUP_DB_PATH)

    # Use Alembic's Python API to create the schema programmatically
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", BACKUP_DB_ASYNC_URL)
    # Set absolute path to migrations directory to avoid path resolution issues
    alembic_cfg.set_main_option("script_location", str(project_root / "backend" / "migrations"))

    # Temporarily set DATABASE_URL so env.py uses the backup database
    # This is necessary because backend/migrations/env.py calls get_settings()
    # which reads DATABASE_URL from the environment, overriding our config
    original_db_url = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = BACKUP_DB_ASYNC_URL

    try:
        # Run alembic upgrade to create all tables
        logger.info("Running Alembic migrations to create schema...")
        command.upgrade(alembic_cfg, "head")

        logger.info("Schema created successfully")

    except Exception:
        logger.error("Alembic migration failed:", exc_info=True)
        raise RuntimeError("Failed to create database schema with Alembic")
    finally:
        # Restore original DATABASE_URL
        if original_db_url:
            os.environ['DATABASE_URL'] = original_db_url
        else:
            os.environ.pop('DATABASE_URL', None)


def insert_data_into_backup(all_data: Dict[str, List[Dict[str, Any]]]):
    """
    Insert all fetched data into the backup database.

    Args:
        all_data: Dictionary mapping table names to lists of row dictionaries
    """
    logger.info(f"Inserting data into backup database...")

    # Create synchronous engine for inserting data
    engine = create_engine(BACKUP_DB_URL, echo=False)

    # Create metadata and reflect tables
    metadata = MetaData()
    metadata.reflect(bind=engine)

    # Chunk size to avoid SQLite's parameter limit (999)
    # Use conservative batch size based on typical column count
    BATCH_SIZE = 50

    with engine.begin() as conn:
        for table_name, rows in all_data.items():
            if not rows:
                logger.info(f"  No data to insert for {table_name}")
                continue

            logger.info(f"  Inserting {len(rows)} rows into {table_name}")

            try:
                # Get table object
                table = metadata.tables.get(table_name)
                if table is None:
                    logger.warning(f"  Table {table_name} not found in backup database, skipping")
                    continue

                # Insert rows in batches to avoid SQLite parameter limit
                for i in range(0, len(rows), BATCH_SIZE):
                    batch = rows[i:i + BATCH_SIZE]
                    conn.execute(table.insert(), batch)
                    if len(rows) > BATCH_SIZE:
                        logger.info(f"    Inserted batch {i//BATCH_SIZE + 1}/{(len(rows) + BATCH_SIZE - 1)//BATCH_SIZE}")

            except Exception as e:
                logger.error(f"  Error inserting into {table_name}: {e}")
                raise

    logger.info("Data insertion completed")


def main():
    """Main backup function."""
    logger.info("=" * 60)
    logger.info("Starting database backup process")
    logger.info("=" * 60)

    # Get source database URL
    settings = get_settings()
    source_url = settings.database_url

    if not source_url or source_url.startswith('sqlite'):
        logger.error("DATABASE_URL environment variable must be set to a remote database URL")
        logger.error("Currently set to: " + (source_url or "None"))
        return 1

    logger.info(f"Source database: {source_url.split('@')[-1] if '@' in source_url else 'SQLite'}")
    logger.info(f"Backup database: {BACKUP_DB_PATH}")

    try:
        # Step 1: Fetch all data from remote database
        logger.info("\nStep 1: Fetching data from source database...")
        # Run async fetch in its own event loop
        all_data = asyncio.run(fetch_all_data_from_remote(source_url))

        total_rows = sum(len(rows) for rows in all_data.values())
        logger.info(f"Total rows fetched: {total_rows}")

        # Step 2: Create backup database with Alembic
        # logger.info("\nStep 2: Creating backup database schema...")
        # Call directly - no async context, so Alembic can use asyncio.run() freely
        # create_backup_database()

        # Step 3: Insert data into backup database
        logger.info("\nStep 3: Inserting data into backup database...")
        insert_data_into_backup(all_data)

        logger.info("\n" + "=" * 60)
        logger.info("Backup completed successfully!")
        logger.info(f"Backup saved to: {os.path.abspath(BACKUP_DB_PATH)}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"\nBackup failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
