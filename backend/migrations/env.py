"""Alembic environment configuration."""
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.engine.url import make_url
from alembic import context
import asyncio
import logging

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Configure additional logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Base and all models
from backend.database import Base
from backend.config import get_settings
# Import all models so Alembic can detect them
from backend.models import (
    Player, Prompt, Round, PhraseSet, Vote,
    Transaction, DailyBonus, ResultView, PlayerAbandonedPrompt
)

# Set database URL from config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    logger.info("=== ALEMBIC MIGRATION DEBUG ===")
    
    # Get configuration section
    configuration = config.get_section(config.config_ini_section, {})
    
    # Get URL and log details
    url = config.get_main_option("sqlalchemy.url")
    logger.info(f"Migration URL length: {len(url) if url else 'None'}")
    
    # Parse URL for debugging
    try:
        if url:
            parsed_url = make_url(url)
            logger.info(f"Migration driver: {parsed_url.drivername}")
            logger.info(f"Migration host: {parsed_url.host}")
            logger.info(f"Migration username: {parsed_url.username}")
            
            if parsed_url.password:
                password = parsed_url.password
                logger.info(f"Migration password length: {len(password)}")
                logger.info(f"Migration password starts: {password[:4]}...")
                logger.info(f"Migration password ends: ...{password[-4:]}")
    except Exception as e:
        logger.error(f"Failed to parse migration URL: {e}")
    
    # Add SSL configuration for Heroku/production if needed
    needs_ssl = url and (
        "heroku" in url or 
        "amazonaws" in url or 
        get_settings().environment == "production"
    )
    
    if needs_ssl:
        configuration["sqlalchemy.connect_args"] = {"ssl": "require"}
        logger.info("Migration SSL enabled (ssl=require)")
    else:
        logger.info("Migration SSL disabled")
    
    logger.info(f"Migration configuration keys: {list(configuration.keys())}")
    
    try:
        connectable = async_engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        logger.info("Migration engine created successfully")
    except Exception as e:
        logger.error(f"Failed to create migration engine: {e}")
        raise

    try:
        async with connectable.connect() as connection:
            logger.info("Migration database connection established")
            await connection.run_sync(do_run_migrations)
            logger.info("Migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration connection/execution failed: {e}")
        raise
    finally:
        await connectable.dispose()
        logger.info("Migration engine disposed")


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
