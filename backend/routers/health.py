"""Health check endpoint."""
from fastapi import APIRouter
from sqlalchemy import text
from backend.database import engine
from backend.utils import queue_client
from backend.config import get_settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Application version - should match FastAPI app version in main.py
APP_VERSION = "1.3.0"


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    # Check database
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "detail": "Database connection failed"
        }, 503

    # Check queue backend
    queue_status = queue_client.backend

    return {
        "status": "ok",
        "database": db_status,
        "redis": queue_status,
    }


@router.get("/status")
async def game_status():
    """
    Get game status information including version, environment, and phrase validation status.

    This endpoint provides system status information for display on the frontend.
    """
    settings = get_settings()

    # Determine phrase validation mode and health
    validation_mode = "remote" if settings.use_phrase_validator_api else "local"
    validation_healthy = None

    if settings.use_phrase_validator_api:
        # Check remote phrase validation API health
        try:
            from backend.services.phrase_validation_client import get_phrase_validation_client
            client = get_phrase_validation_client()
            validation_healthy = await client.health_check()
        except Exception as e:
            logger.warning(f"Failed to check phrase validation API health: {e}")
            validation_healthy = False
    else:
        # Check local phrase validator
        try:
            from backend.services.phrase_validator import get_phrase_validator
            validator = get_phrase_validator()
            validation_healthy = validator.dictionary is not None and len(validator.dictionary) > 0
        except Exception as e:
            logger.warning(f"Failed to check local phrase validator: {e}")
            validation_healthy = False

    return {
        "version": APP_VERSION,
        "environment": settings.environment,
        "phrase_validation": {
            "mode": validation_mode,
            "healthy": validation_healthy,
        },
    }
