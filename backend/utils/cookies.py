"""HTTP cookie helpers."""
from fastapi import Response

from backend.config import get_settings


def set_refresh_cookie(response: Response, token: str, *, expires_days: int | None = None) -> None:
    """Set the refresh token cookie with secure defaults.

    In development, we use SameSite=None to allow cross-origin requests
    between localhost:5173 (frontend) and localhost:8000 (backend).
    """

    settings = get_settings()
    days = expires_days or settings.refresh_token_exp_days
    max_age = days * 24 * 60 * 60

    # In development, allow cross-origin cookie sharing (frontend/backend on different ports)
    # In production, use strict same-site policy
    is_dev = settings.environment == "development"

    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=token,
        httponly=True,
        secure=not is_dev,  # Must be False in dev for SameSite=None to work over HTTP
        samesite="none" if is_dev else "lax",  # None allows cross-origin in dev
        max_age=max_age,
        expires=max_age,
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    """Remove the refresh token cookie from the client."""

    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_token_cookie_name,
        path="/",
    )
