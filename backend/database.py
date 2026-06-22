"""Database connection and session management."""
from __future__ import annotations

import logging

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from backend.config import get_settings
from backend.utils.sqlite import configure_sqlite_engine, is_sqlite_url
from backend.sqlite import configure_production_sqlite

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
parsed_url = None

# Parse URL to examine components
try:
    parsed_url = make_url(settings.database_url)

    # Log password length and first/last few chars (for debugging)
    if parsed_url.password:
        password = parsed_url.password

        # Check for special characters that might need encoding
        import urllib.parse

        encoded_password = urllib.parse.quote(password, safe="")
        if encoded_password != password:
            logger.warning("Password contains special characters that might need URL encoding")
    else:
        # SQLite doesn't use passwords, so this is expected in development
        if "sqlite" not in parsed_url.drivername:
            logger.warning("No password found in DATABASE_URL!")
        else:
            logger.debug("Using SQLite (no password required)")

except Exception as e:
    logger.error(f"Failed to parse DATABASE_URL: {e}")
    logger.error(f"Raw URL (first 50 chars): {settings.database_url[:50]}...")

is_sqlite = parsed_url.drivername.startswith("sqlite") if parsed_url else False

# Determine if we need SSL for a remote non-SQLite database.
connect_args = {}
needs_ssl = (
    not is_sqlite
    and (
        "amazonaws" in settings.database_url or
        settings.environment == "production"
    )
)

if needs_ssl:
    connect_args["ssl"] = "require"
    logger.debug("SSL connection enabled (ssl=require)")
else:
    logger.debug("SSL connection disabled")

logger.debug(f"Connect args: {connect_args}")

# Configure pool sizing to avoid exhausting limited database connections.
engine_kwargs = {
    "echo": settings.environment == "development",
    "future": True,
    "connect_args": connect_args,
    "pool_pre_ping": True,  # Verify connections before use
    "pool_recycle": 3600,   # Recycle connections every hour
}

if not is_sqlite:
    pool_size = max(1, settings.db_pool_size)
    max_overflow = max(0, settings.db_max_overflow)

    if settings.environment == "production":
        # Keep production connection usage conservative to stay within hobby-tier limits
        pool_size = min(pool_size, 2)
        max_overflow = min(max_overflow, 2)

    engine_kwargs.update({
        "pool_size": pool_size,
        "max_overflow": max_overflow,
    })
else:
    logger.debug("SQLite detected; using default NullPool without pool sizing arguments")

def create_app_engine(database_url: str | None = None):
    """Create an async engine with the production SQLite pragmas applied."""
    url = database_url or settings.database_url
    kwargs = dict(engine_kwargs)
    if not is_sqlite_url(url):
        logger.debug("Creating non-SQLite async engine")
    engine = create_async_engine(url, **kwargs)
    configure_sqlite_engine(engine.sync_engine)
    if is_sqlite_url(url) and settings.environment == "production":
        configure_production_sqlite(engine)
    return engine


# Create async engine
try:
    engine = create_app_engine()
    logger.debug("Database engine created successfully")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base class for models
Base = declarative_base()


# Dependency for FastAPI
async def get_db():
    """FastAPI dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
