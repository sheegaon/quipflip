"""Compatibility alias to the unified refresh token model."""

from backend.models.refresh_token import RefreshToken as TLRefreshToken

__all__ = ["TLRefreshToken"]
