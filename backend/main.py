"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime

from backend.services.phrase_validator import get_phrase_validator
from backend.services.prompt_seeder import auto_seed_prompts_if_empty

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Set up log file path
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
log_file = logs_dir / f"quipflip_{timestamp}.log"

# Print log file location to console immediately
print(f"Logging to: {log_file.absolute()}")

# Configure logging with both console and file handlers
# Force=True ensures we override any existing configuration (e.g., from uvicorn)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Console handler (stdout)
        logging.StreamHandler(),
        # File handler (logs/quipflip.log)
        logging.FileHandler(log_file),
    ],
    force=True,
)

logger = logging.getLogger(__name__)

# Add the file handler to the root logger explicitly
root_logger = logging.getLogger()
if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    root_logger.addHandler(file_handler)

# Configure Uvicorn's access logger to also write to our log file
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.INFO)
# Add file handler to uvicorn access logger if it doesn't have one
if not any(isinstance(h, logging.FileHandler) for h in uvicorn_access_logger.handlers):
    access_file_handler = logging.FileHandler(log_file)
    access_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    uvicorn_access_logger.addHandler(access_file_handler)

# Test that logging is working
logger.info("Logging system initialized")

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

    try:
        yield
    finally:
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
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative React dev server
        "http://127.0.0.1:5173",  # Alternative localhost format
        "http://127.0.0.1:3000",  # Alternative localhost format
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Import and register routers
from backend.routers import health, player, rounds, phrasesets, prompt_feedback, auth, quests

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
