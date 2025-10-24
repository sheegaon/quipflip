"""FastAPI application entry point."""
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from contextlib import asynccontextmanager

from backend.config import get_settings
from backend.services.prompt_seeder import sync_prompts_with_database
from backend.routers import health, player, rounds, phrasesets, prompt_feedback, auth, quests
from backend.middleware.deduplication import deduplication_middleware

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Set up log file path (no timestamp - using rotation instead)
log_file = logs_dir / "quipflip.log"

# Print log file location to console immediately
print(f"Logging to: {log_file.absolute()}")

# Create rotating file handler (1MB max size, keep 10 backup files)
rotating_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=10)  # 1 MB
rotating_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure logging with both console and rotating file handlers
# Force=True ensures we override any existing configuration (e.g., from uvicorn)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Console handler (stdout)
        logging.StreamHandler(),
        # Rotating file handler
        rotating_handler,
    ],
    force=True,
)

logger = logging.getLogger(__name__)

# Add the rotating file handler to the root logger explicitly
root_logger = logging.getLogger()
if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
    root_logger.addHandler(rotating_handler)

# Configure Uvicorn's access logger to also write to our rotating log file
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.INFO)
# Add rotating file handler to uvicorn access logger if it doesn't have one
if rotating_handler not in uvicorn_access_logger.handlers:
    uvicorn_access_logger.addHandler(rotating_handler)

# Test that logging is working
logger.info("=" * 100)
logger.info("*" * 36 + " Logging system initialized " + "*" * 36)
logger.info("=" * 100)


class SQLTransactionFilter(logging.Filter):
    def filter(self, record):
        # Only filter INFO level messages
        if record.levelno == logging.INFO and hasattr(record, 'getMessage'):
            message = record.getMessage()

            # Filter out ROLLBACK, BEGIN, and "generated in" messages completely
            if any(keyword in message for keyword in ['ROLLBACK', 'BEGIN', 'COMMIT', 'generated in']):
                return False

            # Remove line breaks from SELECT, DELETE, INSERT statements but keep the message
            if any([kw in message for kw in ['SELECT', 'DELETE', 'INSERT']]):
                # Replace newlines and multiple spaces with single spaces
                clean_message = ' '.join(message.split())
                # Modify the record's message
                record.msg = clean_message
                record.args = ()

        return True


# Apply the filter to SQLAlchemy engine logger
sqlalchemy_logger = logging.getLogger("sqlalchemy.engine.Engine")
sqlalchemy_logger.addFilter(SQLTransactionFilter())

settings = get_settings()


async def initialize_phrase_validation():
    try:
        if settings.use_phrase_validator_api:
            # Use remote phrase validation service
            from backend.services.phrase_validation_client import get_phrase_validation_client
            client = get_phrase_validation_client()

            # Perform health check
            is_healthy = await client.health_check()
            if is_healthy:
                logger.info(f"Phrase validation API health check passed at {settings.phrase_validator_url}")
            else:
                logger.error(f"Phrase validation API health check failed at {settings.phrase_validator_url}")
                logger.error("Phrase validation will fail until the API service is available")
        else:
            # Use local phrase validator
            from backend.services.phrase_validator import get_phrase_validator
            validator = get_phrase_validator()
            logger.info(f"Local phrase validator initialized with {len(validator.dictionary)} words")
    except Exception as e:
        if settings.use_phrase_validator_api:
            logger.error(f"Failed to connect to phrase validation API: {e}")
            logger.error("Phrase validation will fail until the API service is available")
        else:
            logger.error(f"Failed to initialize local phrase validator: {e}")
            logger.error("Run: python3 scripts/download_dictionary.py")
        raise e


async def ai_backup_cycle():
    """
    Background task to run AI backup cycles.

    Includes startup delay to ensure all services (especially phrase validator)
    are ready before attempting AI operations.
    """
    from backend.database import AsyncSessionLocal
    from backend.services.ai.ai_service import AIService

    # Verify phrase validator is ready before starting
    try:
        if settings.use_phrase_validator_api:
            from backend.services.phrase_validation_client import get_phrase_validation_client
            client = get_phrase_validation_client()
            if not await client.health_check():
                logger.warning("Phrase validator API not healthy yet, AI backup may experience issues")
        else:
            from backend.services.phrase_validator import get_phrase_validator
            validator = get_phrase_validator()
            if not validator.dictionary:
                logger.warning("Local phrase validator dictionary not loaded, AI backup may experience issues")
    except Exception as e:
        logger.warning(f"Could not verify phrase validator health: {e}")

    # Initial startup delay
    startup_delay = 180
    logger.info(f"AI backup cycle starting in {startup_delay}s")
    await asyncio.sleep(startup_delay)

    logger.info("AI backup cycle starting main loop")

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await AIService(db).run_backup_cycle()

        except Exception as e:
            logger.error(f"AI backup cycle error: {e}")

        # Wait before next cycle
        await asyncio.sleep(settings.ai_backup_sleep_seconds)


async def cleanup_cycle():
    """
    Background task to run database cleanup tasks.

    Runs periodically to clean up:
    - Orphaned refresh tokens
    - Expired refresh tokens
    - Old revoked tokens
    """
    from backend.database import AsyncSessionLocal
    from backend.services.cleanup_service import CleanupService

    # Initial startup delay
    startup_delay = 120
    logger.info(f"Cleanup cycle starting in {startup_delay}s")
    await asyncio.sleep(startup_delay)

    logger.info("Cleanup cycle starting main loop")

    # Run cleanup every 6 hours (21600 seconds)
    cleanup_interval = 6 * 60 * 60

    while True:
        try:
            async with AsyncSessionLocal() as db:
                cleanup_service = CleanupService(db)
                await cleanup_service.run_all_cleanup_tasks()

        except Exception as e:
            logger.error(f"Cleanup cycle error: {e}")

        # Wait before next cycle
        await asyncio.sleep(cleanup_interval)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Manage application startup and shutdown tasks."""
    logger.info("=" * 60)
    logger.info("Quipflip API Starting")
    logger.info(f"Environment: {settings.environment}")
    logger.info(
        f"Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'SQLite'}"
    )
    logger.info(f"Redis: {'Enabled' if settings.redis_url else 'In-Memory Fallback'}")
    logger.info("=" * 60)

    # Initialize phrase validation service using either local or remote API
    await initialize_phrase_validation()

    # Synchronize prompts between file and database
    await sync_prompts_with_database()

    # Start background tasks
    ai_backup_task = None
    cleanup_task = None

    try:
        ai_backup_task = asyncio.create_task(ai_backup_cycle())
        logger.info(f"AI backup cycle task started (runs every {settings.ai_backup_sleep_seconds} seconds)")
    except Exception as e:
        logger.error(f"Failed to start AI backup cycle: {e}")

    try:
        cleanup_task = asyncio.create_task(cleanup_cycle())
        logger.info("Cleanup cycle task started (runs every 6 hours)")
    except Exception as e:
        logger.error(f"Failed to start cleanup cycle: {e}")

    try:
        yield
    finally:
        # Cancel background tasks on shutdown
        if ai_backup_task:
            ai_backup_task.cancel()
            try:
                await ai_backup_task
            except asyncio.CancelledError:
                logger.info("AI backup cycle task cancelled")

        if cleanup_task:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                logger.info("Cleanup cycle task cancelled")

        # Cleanup phrase validation client session
        if settings.use_phrase_validator_api:
            try:
                from backend.services.phrase_validation_client import get_phrase_validation_client
                client = get_phrase_validation_client()
                await client.close()
                logger.info("Phrase validation client session closed")
            except Exception as e:
                logger.error(f"Error closing phrase validation client: {e}")

        logger.info("Quipflip API Shutting Down... Goodbye!")


# Create FastAPI app
app = FastAPI(
    title="Quipflip API",
    description="Phase 2 - Phrase association game backend",
    version="1.2.0",
    lifespan=lifespan,
)


# CORS middleware with environment-based origins
def get_local_ip():
    """Get the local IP address."""
    import socket
    try:
        # Connect to a remote address (doesn't actually send data)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not allowed_origins or allowed_origins == [""]:
    # Default origins for development + production fallback
    allowed_origins = [
        settings.frontend_url,                # Your production frontend
        "http://localhost:5173",              # Vite dev server
        f"http://{get_local_ip()}:5173/",     # Alternative dev server
        "http://localhost:3000",              # Alternative React dev server
        "http://127.0.0.1:5173",              # Alternative localhost format
        "http://127.0.0.1:3000",              # Alternative localhost format
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add request deduplication middleware to prevent rapid-fire duplicate requests
app.middleware("http")(deduplication_middleware)

# Import and register routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(player.router, prefix="/player", tags=["player"])
app.include_router(rounds.router, prefix="/rounds", tags=["rounds"])
app.include_router(prompt_feedback.router, prefix="/rounds", tags=["prompt_feedback"])
app.include_router(phrasesets.router, prefix="/phrasesets", tags=["phrasesets"])
app.include_router(quests.router, prefix="/quests", tags=["quests"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Quipflip API - Phase 2 MVP",
        "version": "1.1.0",
        "environment": settings.environment,
        "docs": "/docs",
    }
