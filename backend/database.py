"""Database connection and session management."""
import logging
import ssl
from typing import Optional

from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from backend.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


def _parse_database_url(url: str) -> Optional[URL]:
    """Parse the database URL and log debugging information."""
    try:
        parsed = make_url(url)

        if parsed.password:
            password = parsed.password
            import urllib.parse

            encoded_password = urllib.parse.quote(password, safe="")
            if encoded_password != password:
                logger.warning("Password contains special characters that might need URL encoding")
        else:
            if "sqlite" not in parsed.drivername:
                logger.warning("No password found in DATABASE_URL!")
            else:
                logger.debug("Using SQLite (no password required)")

        return parsed
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(f"Failed to parse DATABASE_URL: {exc}")
        logger.error(f"Raw URL (first 50 chars): {url[:50]}...")
        return None


parsed_url = _parse_database_url(settings.database_url)

# Determine if we need SSL (for Heroku or other cloud databases)
connect_args: dict = {}
needs_ssl = (
    "heroku" in settings.database_url
    or "amazonaws" in settings.database_url
    or settings.environment == "production"
)


def _create_ssl_context(url: Optional[URL]) -> ssl.SSLContext:
    """Return an SSL context that honours common Postgres sslmode values."""

    ssl_context = ssl.create_default_context()

    sslmode = None
    if url is not None:
        sslmode = url.query.get("sslmode") if hasattr(url, "query") else None

    if sslmode and sslmode.lower() in {"require", "allow", "prefer"}:
        # These modes request encryption but typically skip certificate validation
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        logger.debug("SSL context configured without certificate verification (sslmode=%s)", sslmode)
    else:
        logger.debug("SSL context will use default certificate verification")

    return ssl_context


if needs_ssl:
    connect_args["ssl"] = _create_ssl_context(parsed_url)
    logger.debug("SSL connection enabled for asyncpg")
else:
    logger.debug("SSL connection disabled (local development)")

logger.debug(f"Connect args: {connect_args}")

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
