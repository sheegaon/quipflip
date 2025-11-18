"""HTTP cookie helpers."""
from fastapi import Response

from backend.config import get_settings


def set_refresh_cookie(response: Response, token: str, *, expires_days: int | None = None,
                       cookie_name: str | None = None) -> None:
    """Set the refresh token cookie with secure defaults.

    In production, REST API uses Vercel proxy (same-origin with SameSite=Lax), but WebSocket
    requires SameSite=None since Vercel doesn't support WebSocket proxying. We use SameSite=Lax
    for REST compatibility, and WebSocket authentication uses a token exchange pattern.

    In development, frontend (localhost:5173) and backend (localhost:8000) are on different
    ports but browsers treat localhost as same-origin, so SameSite=Lax works fine.

    Args:
        response: FastAPI Response object
        token: The token to set in the cookie
        expires_days: Optional override for token expiration (defaults to configured value)
        cookie_name: Optional override for cookie name (defaults to configured value)
    """

    settings = get_settings()
    days = expires_days or settings.refresh_token_exp_days
    max_age = days * 24 * 60 * 60
    name = cookie_name or settings.refresh_token_cookie_name

    # Use SameSite=Lax for both dev and production (REST API via Vercel proxy)
    # WebSocket uses token exchange pattern (/auth/ws-token) instead of cookies
    samesite_value = "lax"
    # Secure flag: only disable for local development, enable for all other environments
    secure_value = settings.environment != "development"

    response.set_cookie(
        key=name,
        value=token,
        httponly=True,
        secure=secure_value,
        samesite=samesite_value,
        max_age=max_age,
        expires=max_age,
        path="/",
    )


def set_access_token_cookie(response: Response, token: str, *, cookie_name: str | None = None) -> None:
    """Set the access token cookie with secure defaults.

    Access tokens have a shorter lifetime than refresh tokens (hours vs days).
    Uses the same security settings as refresh tokens for consistency.
    WebSocket authentication uses token exchange pattern (/auth/ws-token).

    Args:
        response: FastAPI Response object
        token: The token to set in the cookie
        cookie_name: Optional override for cookie name (defaults to configured value)
    """
    settings = get_settings()
    max_age = settings.access_token_exp_minutes * 60
    name = cookie_name or settings.access_token_cookie_name

    # Use SameSite=Lax for both dev and production (REST API via Vercel proxy)
    # WebSocket uses token exchange pattern (/auth/ws-token) instead of cookies
    samesite_value = "lax"
    # Secure flag: only disable for local development, enable for all other environments
    secure_value = settings.environment != "development"

    response.set_cookie(
        key=name,
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
