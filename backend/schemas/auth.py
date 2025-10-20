"""Authentication schema definitions."""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, constr


UsernameStr = constr(min_length=3, max_length=80)
PasswordStr = constr(min_length=8, max_length=128)
EmailLike = constr(pattern=r"[^@\s]+@[^@\s]+\.[^@\s]+", min_length=5, max_length=255)


class RegisterRequest(BaseModel):
    """Payload for creating a new player account."""

    email: EmailLike
    password: PasswordStr


class AuthTokenResponse(BaseModel):
    """Standard response containing JWT credentials."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    player_id: UUID
    username: str


class LoginRequest(BaseModel):
    """Login payload."""

    email: EmailLike
    password: PasswordStr


class SuggestUsernameResponse(BaseModel):
    """Response containing a suggested username."""

    suggested_username: str


class RefreshRequest(BaseModel):
    """Refresh payload (optional when using cookies)."""

    refresh_token: Optional[str] = None


class LogoutRequest(BaseModel):
    """Logout payload requiring the refresh token to revoke."""

    refresh_token: Optional[str] = None
