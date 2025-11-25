"""Base admin router with common administrative endpoints."""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Type, Any, Optional, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, constr
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.auth import EmailLike
from backend.services import SystemConfigService, AuthService
from backend.utils.model_registry import GameType
from backend.utils.passwords import generate_temporary_password

logger = logging.getLogger(__name__)


class AdminPlayerSummary(BaseModel):
    """Summary information for a player returned in admin search."""
    player_id: UUID
    username: str
    email: EmailLike
    wallet: int
    created_at: datetime
    outstanding_prompts: int


class AdminDeletePlayerResponse(BaseModel):
    """Response after deleting a player from admin panel."""
    deleted_player_id: UUID
    deleted_username: str
    deleted_email: EmailLike
    deletion_counts: dict[str, int]


class AdminPlayerRequest(BaseModel):
    """Request model for admin password reset."""
    player_id: Optional[UUID] = None
    email: Optional[EmailLike] = None
    username: Optional[str] = None


class AdminDeletePlayerRequest(AdminPlayerRequest):
    """Request model for deleting a player via admin panel."""
    confirmation: constr(pattern=r"^DELETE$", min_length=6, max_length=6)


class AdminResetPasswordResponse(BaseModel):
    """Response model for admin password reset."""
    player_id: UUID
    username: str
    email: EmailLike
    generated_password: str
    message: str


class UpdateConfigRequest(BaseModel):
    """Request model for updating configuration."""
    key: str
    value: Any


class UpdateConfigResponse(BaseModel):
    """Response model for configuration update."""
    success: bool
    key: str
    value: Any
    message: Optional[str] = None


async def _update_config(request: UpdateConfigRequest, player: Any, session: AsyncSession) -> UpdateConfigResponse:
    """Update a configuration value."""
    try:
        service = SystemConfigService(session)

        # Update the configuration
        config_entry = await service.set_config_value(request.key, request.value, updated_by=str(player.player_id))

        return UpdateConfigResponse(
            success=True,
            key=request.key,
            value=service.deserialize_value(config_entry.value, config_entry.value_type),
            message=f"Configuration '{request.key}' updated successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


class AdminRouterBase(ABC):
    """Base class for admin routers with common administrative endpoints."""

    def __init__(self, game_type: GameType, prefix: str = "/admin"):
        """Initialize the base admin router.
        
        Args:
            game_type: The game type this router serves
            prefix: The URL prefix for admin routes
        """
        self.game_type = game_type
        self.router = APIRouter(prefix=prefix, tags=["admin"])
        self._setup_common_routes()

    @property
    @abstractmethod
    def player_service_class(self) -> Type[Any]:
        """Return the player service class for this game."""
        pass

    @property
    @abstractmethod
    def cleanup_service_class(self) -> Type[Any]:
        """Return the cleanup service class for this game."""
        pass

    @property
    @abstractmethod
    def admin_player_dependency(self):
        """Return the admin player dependency for this game."""
        pass

    def _setup_common_routes(self):
        """Set up all common administrative routes."""

        @self.router.get("/players/search", response_model=AdminPlayerSummary)
        async def search_player(
            session: Annotated[AsyncSession, Depends(get_db)],
            email: Optional[EmailLike] = Query(None),
            username: Optional[str] = Query(None),
        ):
            """Search for a player by email or username."""
            return await self._search_player(session, email, username)

        @self.router.delete("/players", response_model=AdminDeletePlayerResponse)
        async def delete_player_admin(
            request: AdminDeletePlayerRequest,
            session: Annotated[AsyncSession, Depends(get_db)],
        ):
            """Delete a player account and associated data via admin panel."""
            return await self._delete_player_admin(request, session)

        @self.router.post("/players/reset-password", response_model=AdminResetPasswordResponse)
        async def reset_player_password(request: AdminPlayerRequest, session: Annotated[AsyncSession, Depends(get_db)]):
            """Admin endpoint to reset a user's password."""
            return await self._reset_player_password(request, session)

        @self.router.patch("/config", response_model=UpdateConfigResponse)
        async def update_config(
            request: UpdateConfigRequest,
            session: Annotated[AsyncSession, Depends(get_db)],
            player=Depends(self.admin_player_dependency),
        ):
            """Update a configuration value."""
            return await _update_config(request, player, session)

    async def _search_player(
        self,
        session: AsyncSession,
        email: Optional[EmailLike],
        username: Optional[str],
    ) -> AdminPlayerSummary:
        """Search for a player by email or username."""
        if not email and not username:
            raise HTTPException(status_code=400, detail="missing_identifier")

        player_service = self.player_service_class(session)
        target_player = None

        if email:
            target_player = await player_service.get_player_by_email(email)
        elif username:
            target_player = await player_service.get_player_by_username(username)

        if not target_player:
            raise HTTPException(status_code=404, detail="player_not_found")

        outstanding = await player_service.get_outstanding_prompts_count(target_player.player_id)

        return AdminPlayerSummary(
            player_id=target_player.player_id,
            username=target_player.username,
            email=target_player.email,
            wallet=target_player.wallet,
            created_at=target_player.created_at,
            outstanding_prompts=outstanding,
        )

    async def _get_target_player(self, request: AdminPlayerRequest, session: AsyncSession):
        identifier = request.player_id or request.email or request.username
        if not identifier:
            raise HTTPException(status_code=400, detail="missing_identifier")

        player_service = self.player_service_class(session)
        target_player = None

        if request.player_id:
            target_player = await player_service.get_player_by_id(request.player_id)
        elif request.email:
            target_player = await player_service.get_player_by_email(request.email)
        elif request.username:
            target_player = await player_service.get_player_by_username(request.username)

        if not target_player:
            raise HTTPException(status_code=404, detail="player_not_found")

    async def _delete_player_admin(self, request: AdminDeletePlayerRequest, session: AsyncSession
                                   ) -> AdminDeletePlayerResponse:
        """Delete a player account and associated data via admin panel."""
        target_player = await self._get_target_player(request, session)
        cleanup_service = self.cleanup_service_class(session)
        deletion_counts = await cleanup_service.delete_player(target_player.player_id)

        return AdminDeletePlayerResponse(
            deleted_player_id=target_player.player_id,
            deleted_username=target_player.username,
            deleted_email=target_player.email,
            deletion_counts=deletion_counts,
        )

    async def _reset_player_password(self, request: AdminPlayerRequest, session: AsyncSession
                                     ) -> AdminResetPasswordResponse:
        """Admin endpoint to reset a user's password."""
        target_player = await self._get_target_player(request, session)

        # Generate temporary password
        generated_password = generate_temporary_password(length=8)

        # Update password
        player_service = self.player_service_class(session)
        await player_service.update_password(target_player, generated_password)

        # Revoke all refresh tokens to force re-login
        auth_service = AuthService(session, game_type=self.game_type)
        await auth_service.revoke_all_refresh_tokens(target_player.player_id)

        return AdminResetPasswordResponse(
            player_id=target_player.player_id,
            username=target_player.username,
            email=target_player.email,
            generated_password=generated_password,
            message=f"Password reset successfully for {target_player.username}",
        )

    # Abstract methods for game-specific functionality
    @abstractmethod
    def get_game_config_response_model(self) -> Type[BaseModel]:
        """Return the game-specific config response model."""
        pass

    @abstractmethod
    async def get_game_config(self, player: Any, session: AsyncSession) -> BaseModel:
        """Get game-specific configuration."""
        pass
