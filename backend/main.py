"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from contextlib import asynccontextmanager

from backend.config import get_settings
from backend.services.phrase_validator import get_phrase_validator
from backend.services.prompt_seeder import auto_seed_prompts_if_empty
from backend.routers import health, player, rounds, phrasesets, prompt_feedback, auth, quests

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Set up log file path (no timestamp - using rotation instead)
log_file = logs_dir / "quipflip.log"

# Print log file location to console immediately
print(f"Logging to: {log_file.absolute()}")

# Create rotating file handler (1MB max size, keep 10 backup files)
rotating_handler = RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=10)  # 1 MB
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
            if any(keyword in message for keyword in ['ROLLBACK', 'BEGIN', 'generated in']):
                return False
            
            # Remove line breaks from SELECT statements but keep the message
            if 'SELECT' in message:
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown tasks."""
    logger.info("=" * 60)
    logger.info("Quipflip API Starting")
    logger.info(f"Environment: {settings.environment}")
    logger.info(
        f"Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'SQLite'}"
    )
    logger.info(f"Redis: {'Enabled' if settings.redis_url else 'In-Memory Fallback'}")
    logger.info("=" * 60)

    # Initialize phrase validator
    try:
        validator = get_phrase_validator()
        logger.info(f"Phrase validator initialized with {len(validator.dictionary)} words")
    except Exception as e:
        logger.error(f"Failed to initialize phrase validator: {e}")
        logger.error("Run: python3 scripts/download_dictionary.py")

    # Auto-seed prompts if database is empty
    await auto_seed_prompts_if_empty()

    # Start AI backup cycle background task
    ai_backup_task = None
    try:
        import asyncio
        from backend.database import AsyncSessionLocal
        from backend.services.ai_service import AIService
        
        async def ai_backup_cycle():
            """Background task to run AI backup cycles."""
            while True:
                # Wait before first cycle
                await asyncio.sleep(settings.ai_backup_sleep_seconds)

                try:
                    async with AsyncSessionLocal() as db:
                        ai_service = AIService(db, validator)
                        
                        stats = await ai_service.run_backup_cycle()
                        if stats["copies_generated"] > 0 or stats["errors"] > 0:
                            logger.info(f"AI backup cycle completed: {stats}")
                        
                except Exception as e:
                    logger.error(f"AI backup cycle error: {e}")

        ai_backup_task = asyncio.create_task(ai_backup_cycle())
        logger.info(f"AI backup cycle task started (runs every {settings.ai_backup_sleep_seconds} seconds)")
        
    except Exception as e:
        logger.error(f"Failed to start AI backup cycle: {e}")

    try:
        yield
    finally:
        # Cancel AI backup task on shutdown
        if ai_backup_task:
            ai_backup_task.cancel()
            try:
                await ai_backup_task
            except asyncio.CancelledError:
                logger.info("AI backup cycle task cancelled")
        
        logger.info("Quipflip API Shutting Down")


# Create FastAPI app
app = FastAPI(
    title="Quipflip API",
    description="Phase 2 MVP - Phrase association game backend",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS middleware with environment-based origins
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not allowed_origins or allowed_origins == [""]:
    # Default origins for development + production fallback
    allowed_origins = [
        "https://quipflip-amber.vercel.app",  # Your production frontend
        "http://localhost:5173",              # Vite dev server
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
