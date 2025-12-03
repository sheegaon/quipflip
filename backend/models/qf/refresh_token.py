"""Compatibility alias to the unified refresh token model."""

from backend.models.refresh_token import RefreshToken as QFRefreshToken

__all__ = ["QFRefreshToken"]
