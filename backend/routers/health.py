"""Health and readiness endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.config import get_settings
from backend.database import engine
from backend.runtime.readiness import build_readiness_report
from backend.utils import queue_client
from backend.version import APP_VERSION


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/livez")
async def livez() -> dict[str, str]:
    """Process liveness: only proves the app event loop responds."""

    return {
        "status": "ok",
        "version": APP_VERSION,
    }


@router.get("/readyz")
async def readyz():
    """Production readiness gate."""

    try:
        report = await build_readiness_report()
    except Exception as exc:  # pragma: no cover - defensive fail-closed path
        logger.exception("Readiness evaluation failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "version": APP_VERSION,
                "environment": get_settings().environment,
                "release_id": "",
                "expected_revision": "",
                "checks": [
                    {
                        "name": "readiness",
                        "ok": False,
                        "detail": f"readiness evaluation failed: {exc.__class__.__name__}",
                    }
                ],
            },
        )

    payload = report.to_payload()
    status_code = 200 if report.ready else 503
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/health")
async def health_check():
    """Compatibility health endpoint for existing localhost and smoke checks."""

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "detail": "Database connection failed",
                "database": "disconnected",
                "redis": queue_client.backend,
            },
        )

    return {
        "status": "ok",
        "database": "connected",
        "redis": queue_client.backend,
    }


@router.get("/status")
async def game_status():
    """Human-readable status information used by the existing frontend."""

    settings = get_settings()
    validation_mode = "remote" if settings.use_phrase_validator_api else "local"

    try:
        from backend.services import get_phrase_validator

        validator = get_phrase_validator()
        validation_healthy = validator.dictionary is not None and len(validator.dictionary) > 0
    except ImportError as exc:
        logger.error("Failed to import phrase validator module: %s", exc)
        validation_healthy = False
    except (FileNotFoundError, OSError) as exc:
        logger.error("Dictionary file not found or inaccessible: %s", exc)
        validation_healthy = False
    except Exception as exc:
        logger.warning("Unexpected error checking local phrase validator: %s", exc)
        validation_healthy = False

    return {
        "version": APP_VERSION,
        "environment": settings.environment,
        "phrase_validation": {
            "mode": validation_mode,
            "healthy": validation_healthy,
        },
    }
