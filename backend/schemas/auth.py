"""Authentication schema definitions."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, constr

from backend.utils.model_registry import GameType


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
    player: "GlobalPlayerInfo"
    game_type: Optional[GameType] = None
    game_data: Optional["GamePlayerSnapshot"] = None
    legacy_wallet: Optional[int] = None
    legacy_vault: Optional[int] = None
    legacy_tutorial_completed: Optional[bool] = None


class GamePlayerSnapshot(BaseModel):
    game_type: GameType
    wallet: Optional[int] = None
    vault: Optional[int] = None
    tutorial_completed: Optional[bool] = None


class GlobalPlayerInfo(BaseModel):
    player_id: UUID
    username: str
    email: Optional[str] = None
    is_guest: bool
    is_admin: bool
    created_at: datetime
    last_login_date: Optional[datetime] = None


class AuthSessionResponse(BaseModel):
    """Session lookup response for cookie/header-based auth checks."""

    player_id: UUID
    username: str
    player: GlobalPlayerInfo
    game_type: Optional[GameType] = None
    game_data: Optional[GamePlayerSnapshot] = None
    legacy_wallet: Optional[int] = None
    legacy_vault: Optional[int] = None
    legacy_tutorial_completed: Optional[bool] = None


class LoginRequest(BaseModel):
    """Login payload."""

    email: EmailLike
    password: PasswordStr


class UsernameLoginRequest(BaseModel):
    """Login payload using username instead of email."""

    username: UsernameStr
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
