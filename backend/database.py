"""Database connection and session management."""
import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine.url import make_url
from backend.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Log database configuration details (mask password for security)
logger.info("=== DATABASE CONFIGURATION DEBUG ===")
logger.info(f"Environment: {settings.environment}")
logger.info(f"Raw DATABASE_URL length: {len(settings.database_url)}")

# Parse URL to examine components
try:
    parsed_url = make_url(settings.database_url)
    logger.info(f"Database driver: {parsed_url.drivername}")
    logger.info(f"Database host: {parsed_url.host}")
    logger.info(f"Database port: {parsed_url.port}")
    logger.info(f"Database name: {parsed_url.database}")
    logger.info(f"Database username: {parsed_url.username}")
    
    # Log password length and first/last few chars (for debugging)
    if parsed_url.password:
        password = parsed_url.password
        logger.info(f"Password length: {len(password)}")
        logger.info(f"Password starts with: {password[:4]}...")
        logger.info(f"Password ends with: ...{password[-4:]}")
        
        # Check for special characters that might need encoding
        import urllib.parse
        encoded_password = urllib.parse.quote(password, safe='')
        if encoded_password != password:
            logger.warning(f"Password contains special characters that might need URL encoding")
            logger.info(f"URL-encoded password length: {len(encoded_password)}")
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
    logger.info("SSL connection enabled (ssl=require)")
else:
    logger.info("SSL connection disabled (local development)")

logger.info(f"Connect args: {connect_args}")

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
    )
    logger.info("Database engine created successfully")
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
