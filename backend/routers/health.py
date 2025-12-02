"""Health check endpoint."""
from fastapi import APIRouter
from sqlalchemy import text
from backend.database import engine
from backend.utils import queue_client
from backend.config import get_settings
from backend.version import APP_VERSION
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


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

    # Check local phrase validator
    try:
        from backend.services import get_phrase_validator
        validator = get_phrase_validator()
        validation_healthy = validator.dictionary is not None and len(validator.dictionary) > 0
    except ImportError as e:
        logger.error(f"Failed to import phrase validator module: {e}")
        validation_healthy = False
    except (FileNotFoundError, OSError) as e:
        logger.error(f"Dictionary file not found or inaccessible: {e}")
        validation_healthy = False
    except Exception as e:
        logger.warning(f"Unexpected error checking local phrase validator: {e}")
        validation_healthy = False

    return {
        "version": APP_VERSION,
        "environment": settings.environment,
        "phrase_validation": {
            "mode": validation_mode,
            "healthy": validation_healthy,
        },
    }
