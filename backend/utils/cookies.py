"""HTTP cookie helpers."""
from fastapi import Response

from backend.config import get_settings


def set_refresh_cookie(response: Response, token: str, *, expires_days: int | None = None) -> None:
    """Set the refresh token cookie with secure defaults.

    Note: In development with frontend (localhost:5173) and backend (localhost:8000)
    on different ports, browsers treat them as same-origin since both are localhost.
    SameSite=Lax works fine for this scenario and doesn't require HTTPS.

    For true cross-origin scenarios (different domains), you would need:
    - SameSite=None with Secure=True (requires HTTPS)
    - Or serve both frontend and backend from the same origin
    """

    settings = get_settings()
    days = expires_days or settings.refresh_token_exp_days
    max_age = days * 24 * 60 * 60

    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=token,
        httponly=True,
        secure=settings.environment != "development",  # HTTPS in production only
        samesite="lax",  # Lax works for localhost:port1 -> localhost:port2
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
