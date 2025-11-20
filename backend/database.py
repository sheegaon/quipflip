"""Database connection and session management."""
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine.url import make_url
from backend.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Parse URL to examine components
try:
    parsed_url = make_url(settings.database_url)

    # Log password length and first/last few chars (for debugging)
    if parsed_url.password:
        password = parsed_url.password

        # Check for special characters that might need encoding
        import urllib.parse
        encoded_password = urllib.parse.quote(password, safe='')
        if encoded_password != password:
            logger.warning(f"Password contains special characters that might need URL encoding")
    else:
        # SQLite doesn't use passwords, so this is expected in development
        if 'sqlite' not in parsed_url.drivername:
            logger.warning("No password found in DATABASE_URL!")
        else:
            logger.debug("Using SQLite (no password required)")

except Exception as e:
    logger.error(f"Failed to parse DATABASE_URL: {e}")
    logger.error(f"Raw URL (first 50 chars): {settings.database_url[:50]}...")

# Determine if we need SSL (for Heroku or other cloud databases)
connect_args = {}
needs_ssl = (
    "heroku" in settings.database_url or
    "amazonaws" in settings.database_url or
    settings.environment == "production"
)

if needs_ssl:
    connect_args["ssl"] = "require"
    logger.debug("SSL connection enabled (ssl=require)")
else:
    logger.debug("SSL connection disabled (local development)")

logger.debug(f"Connect args: {connect_args}")

# Configure pool sizing to avoid exhausting limited database connections (e.g., on Heroku)
pool_size = max(1, settings.db_pool_size)
max_overflow = max(0, settings.db_max_overflow)

if settings.environment == "production":
    # Keep production connection usage conservative to stay within hobby-tier limits
    pool_size = min(pool_size, 2)
    max_overflow = min(max_overflow, 2)

# Create async engine
try:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.environment == "development",
        future=True,
        connect_args=connect_args,
        # Add connection pool settings for debugging
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,   # Recycle connections every hour
        pool_size=pool_size,
        max_overflow=max_overflow,
    )
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
