"""HTTP cookie helpers."""
from fastapi import Response

from backend.config import get_settings


def set_refresh_cookie(response: Response, token: str, *, expires_days: int | None = None) -> None:
    """Set the refresh token cookie with secure defaults.

    Note: In development with frontend (localhost:5173) and backend (localhost:8000)
    on different ports, browsers treat them as same-origin since both are localhost.
    SameSite=Lax works fine for this scenario and doesn't require HTTPS.

    For production cross-origin scenarios (different domains like quipflip.xyz and herokuapp.com),
    we use SameSite=None with Secure=True (requires HTTPS).
    """

    settings = get_settings()
    days = expires_days or settings.refresh_token_exp_days
    max_age = days * 24 * 60 * 60

    # Use SameSite=None for production (cross-origin) and Lax for development (same localhost)
    samesite_value = "none" if settings.environment == "production" else "lax"
    # Secure flag: only disable for local development, enable for all other environments
    secure_value = settings.environment != "development"

    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=token,
        httponly=True,
        secure=secure_value,
        samesite=samesite_value,
        max_age=max_age,
        expires=max_age,
        path="/",
    )


def set_access_token_cookie(response: Response, token: str) -> None:
    """Set the access token cookie with secure defaults.

    Access tokens have a shorter lifetime than refresh tokens (hours vs days).
    Uses the same security settings as refresh tokens for consistency.
    """
    settings = get_settings()
    max_age = settings.access_token_exp_minutes * 60

    # Use SameSite=None for production (cross-origin) and Lax for development (same localhost)
    samesite_value = "none" if settings.environment == "production" else "lax"
    # Secure flag: only disable for local development, enable for all other environments
    secure_value = settings.environment != "development"

    response.set_cookie(
        key=settings.access_token_cookie_name,
        value=token,
        httponly=True,
        secure=secure_value,
        samesite=samesite_value,
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


def clear_access_token_cookie(response: Response) -> None:
    """Remove the access token cookie from the client."""

    settings = get_settings()
    response.delete_cookie(
        key=settings.access_token_cookie_name,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Remove both access and refresh token cookies from the client."""

    clear_access_token_cookie(response)
    clear_refresh_cookie(response)
