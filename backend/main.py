"""FastAPI application entry point."""
import asyncio
import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from contextlib import asynccontextmanager

from backend.config import get_settings
from backend.services.prompt_seeder import sync_prompts_with_database
from backend.routers import health, player, rounds, phrasesets, prompt_feedback, auth, quests, admin, feedback
from backend.middleware.deduplication import deduplication_middleware

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Set up log file paths
log_file = logs_dir / "quipflip.log"
sql_log_file = logs_dir / "quipflip_sql.log"
api_log_file = logs_dir / "quipflip_api.log"

# Print log file locations to console immediately
print(f"General logging to: {log_file.absolute()}")
print(f"SQL logging to: {sql_log_file.absolute()}")
print(f"API requests logging to: {api_log_file.absolute()}")

# Create rotating file handler for general logs (1MB max size, keep 5 backup files)
rotating_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5)  # 1 MB
rotating_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Create rotating file handler for SQL logs (1MB max size, keep 5 backup files)
sql_rotating_handler = RotatingFileHandler(sql_log_file, maxBytes=1024 * 1024, backupCount=5)  # 1 MB
sql_rotating_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Create rotating file handler for API request logs (2MB max size, keep 15 backup files)
api_rotating_handler = RotatingFileHandler(api_log_file, maxBytes=2 * 1024 * 1024, backupCount=15, encoding='utf-8')  # 2 MB
api_rotating_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

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

# Create dedicated API request logger
api_logger = logging.getLogger("quipflip.api")
api_logger.handlers.clear()  # Remove any existing handlers
api_logger.addHandler(api_rotating_handler)
api_logger.setLevel(logging.INFO)
api_logger.propagate = False  # Prevent propagation to root logger

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

# Configure SQLAlchemy engine logger to write to separate SQL log file
sqlalchemy_logger = logging.getLogger("sqlalchemy.engine.Engine")
sqlalchemy_logger.handlers.clear()  # Remove any existing handlers
sqlalchemy_logger.addHandler(sql_rotating_handler)
sqlalchemy_logger.setLevel(logging.INFO)
sqlalchemy_logger.propagate = False  # Prevent propagation to root logger to avoid duplication

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


async def initialize_missing_player_quests():
    """Ensure all players have their starter quests."""
    from backend.scripts.initialize_quests import initialize_quests_for_all_players

    try:
        logger.info(
            "Running quest initialization script to align all players with starter quests."
        )
        await initialize_quests_for_all_players()
    except Exception as e:
        logger.error(f"Failed to initialize player quests: {e}")
        raise


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
        await asyncio.sleep(settings.ai_backup_sleep_minutes * 60)


async def ai_stale_handler_cycle():
    """Background task that runs the stale AI handler on a schedule."""

    from backend.database import AsyncSessionLocal
    from backend.services.ai.stale_ai_service import StaleAIService

    if not settings.ai_stale_handler_enabled:
        logger.info("Stale AI handler is disabled, not starting cycle")
        return

    try:
        if settings.use_phrase_validator_api:
            from backend.services.phrase_validation_client import get_phrase_validation_client
            client = get_phrase_validation_client()
            if not await client.health_check():
                logger.warning("Phrase validator API not healthy yet, stale AI may experience issues")
        else:
            from backend.services.phrase_validator import get_phrase_validator
            validator = get_phrase_validator()
            if not validator.dictionary:
                logger.warning("Local phrase validator dictionary not loaded, stale AI may experience issues")
    except Exception as exc:
        logger.warning(f"Could not verify phrase validator health: {exc}")

    startup_delay = 180
    logger.info(f"Stale AI handler cycle starting in {startup_delay}s")
    await asyncio.sleep(startup_delay)

    logger.info("Stale AI handler cycle starting main loop")

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await StaleAIService(db).run_stale_cycle()

        except Exception as exc:
            logger.error(f"Stale AI handler cycle error: {exc}")

        sleep_seconds = settings.ai_stale_check_interval_hours * 3600
        logger.info(
            "Stale AI handler sleeping for %s hours",
            settings.ai_stale_check_interval_hours,
        )
        await asyncio.sleep(sleep_seconds)


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

    # Initialize quests for any players who don't have them yet
    await initialize_missing_player_quests()

    # Start background tasks
    ai_backup_task = None
    stale_handler_task = None
    cleanup_task = None

    try:
        ai_backup_task = asyncio.create_task(ai_backup_cycle())
        logger.info(
            "AI backup cycle task started (runs every %s minutes)",
            settings.ai_backup_sleep_minutes,
        )
    except Exception as e:
        logger.error(f"Failed to start AI backup cycle: {e}")

    try:
        stale_handler_task = asyncio.create_task(ai_stale_handler_cycle())
        logger.info(
            "Stale AI handler task started (runs every %s hours)",
            settings.ai_stale_check_interval_hours,
        )
    except Exception as exc:
        logger.error(f"Failed to start stale AI handler cycle: {exc}")

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

        if stale_handler_task:
            stale_handler_task.cancel()
            try:
                await stale_handler_task
            except asyncio.CancelledError:
                logger.info("Stale AI handler task cancelled")

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
    version="1.3.0",
    lifespan=lifespan,
)


# Comprehensive API Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Comprehensive request logging middleware that captures all API requests and responses.
    Logs to dedicated API log file with detailed information including timing, status codes,
    client info, and request/response details.
    """
    start_time = time.time()
    
    # Extract client information
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # Extract request details
    method = request.method
    url = str(request.url)
    path = request.url.path
    query_params = str(request.query_params) if request.query_params else ""
    
    # Log request start
    request_id = f"{method}:{path}:{int(start_time * 1000) % 100000}"  # Simple request ID
    
    api_logger.info(f">> {request_id} | START | {method} {path} | IP: {client_ip} | UA: {user_agent[:50]}...")
    
    # Add query params if present
    if query_params:
        api_logger.info(f">> {request_id} | QUERY | {query_params}")
    
    # Process request and measure response time
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log successful response
        api_logger.info(
            f"<< {request_id} | COMPLETE | {method} {path} | "
            f"Status: {response.status_code} | "
            f"Time: {process_time:.3f}s | "
            f"IP: {client_ip}"
        )
        
        # Add response headers for debugging if needed
        if response.status_code >= 400:
            content_type = response.headers.get("content-type", "unknown")
            api_logger.warning(
                f"<< {request_id} | ERROR_RESPONSE | "
                f"Content-Type: {content_type}"
            )
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        
        # Log exception
        api_logger.error(
            f"<< {request_id} | EXCEPTION | {method} {path} | "
            f"Error: {str(e)[:100]} | "
            f"Time: {process_time:.3f}s | "
            f"IP: {client_ip}"
        )
        
        # Re-raise the exception
        raise


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
app.include_router(admin.router, tags=["admin"])
app.include_router(feedback.router, tags=["feedback"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Quipflip API - Phase 3 Beta",
        "version": "1.2.0",
        "environment": settings.environment,
        "docs": "/docs",
    }
