"""Base player router with common authentication and account management endpoints."""
import logging
from abc import ABC, abstractmethod
from typing import Type, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.dependencies import get_current_player, enforce_guest_creation_rate_limit
from backend.config import get_settings
from backend.utils.model_registry import GameType
from backend.services import AuthService, AuthError
from backend.schemas.auth import (
    AuthTokenResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    UsernameLoginRequest,
)
from backend.schemas.player import (
    CreatePlayerResponse,
    CreateGuestResponse,
    UpgradeGuestRequest,
    UpgradeGuestResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    UpdateEmailRequest,
    UpdateEmailResponse,
    ChangeUsernameRequest,
    ChangeUsernameResponse,
    DeleteAccountRequest,
    PlayerBalance,
    ClaimDailyBonusResponse,
)
from backend.utils.cookies import (
    clear_auth_cookies,
    clear_refresh_cookie,
    set_access_token_cookie,
    set_refresh_cookie,
)
from backend.utils.passwords import (
    verify_password,
    validate_password_strength,
    PasswordValidationError,
)
from backend.services.username_service import canonicalize_username
from backend.utils.exceptions import (
    UsernameTakenError,
    InvalidUsernameError,
)

logger = logging.getLogger(__name__)


def _get_guest_message(email: str, password: str) -> str:
    """Get the guest account creation success message."""
    return (
        f"Guest account created! Your temporary credentials are:\n"
        f"Email: {email}\n"
        f"Password: {password}\n\n"
        f"You can upgrade to a full account anytime to choose your own email and password."
    )


class PlayerRouterBase(ABC):
    """Base class for player routers with common authentication endpoints."""

    def __init__(self, game_type: GameType):
        """Initialize the base router with game-specific configuration.
        
        Args:
            game_type: The game type this router serves
        """
        self.game_type = game_type
        self.settings = get_settings()
        self.router = APIRouter()
        self._setup_common_routes()

    def _current_player_dependency(self):
        """Return a dependency that resolves the current player for this game."""

        async def _resolver(
            request: Request,
            authorization: str | None = Header(default=None, alias="Authorization"),
            db: AsyncSession = Depends(get_db),
        ):
            return await get_current_player(request, self.game_type, authorization, db)

        return _resolver

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

    def get_game_name(self) -> str:
        """Get a human-readable name for this game."""
        if self.game_type == GameType.QF:
            return "Quipflip"
        elif self.game_type == GameType.IR:
            return "Initial Reaction"
        elif self.game_type == GameType.MM:
            return "MemeMint"
        return str(self.game_type)

    def _get_create_message(self) -> str:
        """Get the account creation success message."""
        game_name = self.get_game_name()
        game_clause = f" {game_name}" if game_name else ""
        return (
            f"Player created! Your account is ready to play{game_clause}. "
            "An access token and refresh token have been issued for authentication."
        )

    def _setup_common_routes(self):
        """Set up all common authentication and account management routes."""
        
        @self.router.post("", response_model=CreatePlayerResponse, status_code=201)
        async def create_player(
            request: RegisterRequest,
            response: Response,
            db: AsyncSession = Depends(get_db),
        ):
            """Create a new player account and return credentials."""
            return await self._create_player(request, response, db)

        @self.router.post("/guest", response_model=CreateGuestResponse, status_code=201)
        async def create_guest_player(
            response: Response,
            db: AsyncSession = Depends(get_db),
            _rate_limit: None = Depends(enforce_guest_creation_rate_limit),
        ):
            """Create a guest account with auto-generated credentials."""
            return await self._create_guest_player(response, db)

        player_dependency = self._current_player_dependency()

        @self.router.post("/upgrade", response_model=UpgradeGuestResponse)
        async def upgrade_guest_account(
            request: UpgradeGuestRequest,
            response: Response,
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Upgrade a guest account to a full account."""
            return await self._upgrade_guest_account(request, response, player, db)

        @self.router.post("/login", response_model=AuthTokenResponse)
        async def login_player(
            request: UsernameLoginRequest | LoginRequest,
            response: Response,
            db: AsyncSession = Depends(get_db),
        ):
            """Authenticate a player via email/password and issue JWT tokens."""
            return await self._login_player(request, response, db)

        @self.router.post("/refresh", response_model=AuthTokenResponse)
        async def refresh_tokens(
            request: RefreshRequest,
            response: Response,
            refresh_cookie: str | None = Cookie(
                default=None, alias=self.settings.refresh_token_cookie_name
            ),
            db: AsyncSession = Depends(get_db),
        ):
            """Refresh authentication tokens and rotate cookies."""
            return await self._refresh_tokens(request, response, refresh_cookie, db)

        @self.router.post("/logout", status_code=204)
        async def logout_player(
            request: LogoutRequest,
            response: Response,
            refresh_cookie: str | None = Cookie(
                default=None, alias=self.settings.refresh_token_cookie_name
            ),
            db: AsyncSession = Depends(get_db),
        ):
            """Invalidate a refresh token and clear auth cookies."""
            return await self._logout_player(request, response, refresh_cookie, db)

        @self.router.post("/password", response_model=ChangePasswordResponse)
        async def change_password(
            request: ChangePasswordRequest,
            response: Response,
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Allow the current player to change their password."""
            return await self._change_password(request, response, player, db)

        @self.router.patch("/email", response_model=UpdateEmailResponse)
        async def update_email(
            request: UpdateEmailRequest,
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Allow the current player to update their email address."""
            return await self._update_email(request, player, db)

        @self.router.patch("/username", response_model=ChangeUsernameResponse)
        async def change_username(
            request: ChangeUsernameRequest,
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Allow the current player to change their username."""
            return await self._change_username(request, player, db)

        @self.router.delete("/account", status_code=204)
        async def delete_account(
            request: DeleteAccountRequest,
            response: Response,
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Delete the current player's account and related data."""
            return await self._delete_account(request, response, player, db)

        @self.router.get("/me", response_model=PlayerBalance)
        async def get_current_player_info(
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Get current authenticated player information using shared schema."""
            return await self.get_balance(player, db)

        @self.router.get("/balance", response_model=PlayerBalance)
        async def get_balance(
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Get player balance and status."""
            return await self.get_balance(player, db)

        @self.router.post("/claim-daily-bonus", response_model=ClaimDailyBonusResponse)
        async def claim_daily_bonus(
            player=Depends(player_dependency),
            db: AsyncSession = Depends(get_db),
        ):
            """Claim daily login bonus."""
            return await self._claim_daily_bonus(player, db)

    async def _create_player(
        self,
        request: RegisterRequest,
        response: Response,
        db: AsyncSession,
    ) -> CreatePlayerResponse:
        """Create a new player account and return credentials."""
        auth_service = AuthService(db, game_type=self.game_type)
        try:
            player = await auth_service.register_player(
                email=request.email,
                password=request.password,
            )
        except AuthError as exc:
            message = str(exc)
            # Check if this is a password validation error
            if any(keyword in message for keyword in [
                "Password must be at least",
                "Password must include both uppercase and lowercase",
                "Password must include at least one number"
            ]):
                raise HTTPException(status_code=422, detail=message) from exc
            if message == "username_generation_failed":
                raise HTTPException(status_code=500, detail="username_generation_failed") from exc
            if message == "email_taken":
                raise HTTPException(status_code=409, detail="email_taken") from exc
            if message == "invalid_username":
                raise HTTPException(status_code=422, detail="invalid_username") from exc
            raise

        access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
        set_access_token_cookie(response, access_token)
        set_refresh_cookie(response, refresh_token, expires_days=self.settings.refresh_token_exp_days)

        return CreatePlayerResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type="bearer",
            player_id=player.player_id,
            username=player.username,
            wallet=player.wallet,
            vault=player.vault,
            message=self._get_create_message(),
        )

    async def _create_guest_player(
        self,
        response: Response,
        db: AsyncSession,
    ) -> CreateGuestResponse:
        """Create a guest account with auto-generated credentials."""
        auth_service = AuthService(db, game_type=self.game_type)
        try:
            player, guest_password = await auth_service.register_guest()
        except AuthError as exc:
            message = str(exc)
            if message == "username_generation_failed":
                raise HTTPException(status_code=500, detail="username_generation_failed") from exc
            if message == "guest_email_generation_failed":
                raise HTTPException(status_code=500, detail="guest_email_generation_failed") from exc
            raise

        access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
        set_access_token_cookie(response, access_token)
        set_refresh_cookie(response, refresh_token, expires_days=self.settings.refresh_token_exp_days)

        return CreateGuestResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type="bearer",
            player_id=player.player_id,
            username=player.username,
            wallet=player.wallet,
            vault=player.vault,
            email=player.email,
            password=guest_password,
            message=_get_guest_message(player.email, guest_password),
        )

    async def _upgrade_guest_account(
        self,
        request: UpgradeGuestRequest,
        response: Response,
        player: Any,
        db: AsyncSession,
    ) -> UpgradeGuestResponse:
        """Upgrade a guest account to a full account."""
        auth_service = AuthService(db, game_type=self.game_type)
        try:
            upgraded_player = await auth_service.upgrade_guest(player, request.email, request.password)
        except AuthError as exc:
            message = str(exc)
            if message == "not_a_guest":
                raise HTTPException(status_code=400, detail="not_a_guest") from exc
            if message == "email_taken":
                raise HTTPException(status_code=409, detail="email_taken") from exc
            # Check if this is a password validation error
            if any(keyword in message for keyword in [
                "Password must be at least",
                "Password must include both uppercase and lowercase",
                "Password must include at least one number"
            ]):
                raise HTTPException(status_code=422, detail=message) from exc
            if message == "upgrade_failed":
                raise HTTPException(status_code=500, detail="upgrade_failed") from exc
            raise

        # Issue fresh tokens after upgrade
        access_token, refresh_token, expires_in = await auth_service.issue_tokens(upgraded_player)
        set_access_token_cookie(response, access_token)
        set_refresh_cookie(response, refresh_token, expires_days=self.settings.refresh_token_exp_days)

        return UpgradeGuestResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type="bearer",
            player_id=upgraded_player.player_id,
            username=upgraded_player.username,
            message="Account upgraded successfully! You can now log in with your new credentials.",
        )

    async def _login_player(
        self,
        request: UsernameLoginRequest | LoginRequest,
        response: Response,
        db: AsyncSession,
    ) -> AuthTokenResponse:
        """Authenticate a player via email/password and issue JWT tokens."""
        auth_service = AuthService(db, game_type=self.game_type)
        try:
            if isinstance(request, LoginRequest):
                player = await auth_service.authenticate_player(request.email, request.password)
            else:
                player = await auth_service.authenticate_player_by_username(
                    request.username, request.password
                )
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
        set_access_token_cookie(response, access_token)
        set_refresh_cookie(response, refresh_token, expires_days=self.settings.refresh_token_exp_days)

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            player_id=player.player_id,
            username=player.username,
        )

    async def _refresh_tokens(
        self,
        request: RefreshRequest,
        response: Response,
        refresh_cookie: str | None,
        db: AsyncSession,
    ) -> AuthTokenResponse:
        """Refresh authentication tokens and rotate cookies."""
        refresh_token = request.refresh_token or refresh_cookie

        if not refresh_token:
            raise HTTPException(status_code=401, detail="missing_refresh_token")

        auth_service = AuthService(db, game_type=self.game_type)
        try:
            player, access_token, new_refresh_token, expires_in = await auth_service.exchange_refresh_token(
                refresh_token)
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        set_access_token_cookie(response, access_token)
        set_refresh_cookie(response, new_refresh_token, expires_days=self.settings.refresh_token_exp_days)

        return AuthTokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=expires_in,
            player_id=player.player_id,
            username=player.username,
        )

    async def _logout_player(
        self,
        request: LogoutRequest,
        response: Response,
        refresh_cookie: str | None,
        db: AsyncSession,
    ) -> None:
        """Invalidate a refresh token and clear auth cookies."""
        token = request.refresh_token or refresh_cookie
        if token:
            auth_service = AuthService(db, game_type=self.game_type)
            await auth_service.revoke_refresh_token(token)

        clear_auth_cookies(response)
        clear_refresh_cookie(response)
        response.status_code = 204
        return None

    async def _change_password(
        self,
        request: ChangePasswordRequest,
        response: Response,
        player: Any,
        db: AsyncSession,
    ) -> ChangePasswordResponse:
        """Allow the current player to change their password."""
        if not verify_password(request.current_password, player.password_hash):
            raise HTTPException(status_code=401, detail="invalid_current_password")

        if verify_password(request.new_password, player.password_hash):
            raise HTTPException(status_code=400, detail="password_unchanged")

        try:
            validate_password_strength(request.new_password)
        except PasswordValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        player_service = self.player_service_class(db)
        await player_service.update_password(player, request.new_password)

        auth_service = AuthService(db, game_type=self.game_type)
        access_token, refresh_token, expires_in = await auth_service.issue_tokens(player)
        set_access_token_cookie(response, access_token)
        set_refresh_cookie(response, refresh_token, expires_days=self.settings.refresh_token_exp_days)

        return ChangePasswordResponse(
            message="Password updated successfully.",
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    async def _update_email(
        self,
        request: UpdateEmailRequest,
        player: Any,
        db: AsyncSession,
    ) -> UpdateEmailResponse:
        """Allow the current player to update their email address."""
        if not verify_password(request.password, player.password_hash):
            raise HTTPException(status_code=401, detail="invalid_password")

        player_service = self.player_service_class(db)

        if player.email and player.email.lower() == request.new_email.strip().lower():
            return UpdateEmailResponse(email=player.email)

        try:
            updated = await player_service.update_email(player, request.new_email)
        except ValueError as exc:
            message = str(exc)
            if message == "email_taken":
                raise HTTPException(status_code=409, detail="email_taken") from exc
            if message == "invalid_email":
                raise HTTPException(status_code=422, detail="invalid_email") from exc
            raise

        return UpdateEmailResponse(email=updated.email)

    async def _change_username(
        self,
        request: ChangeUsernameRequest,
        player: Any,
        db: AsyncSession,
    ) -> ChangeUsernameResponse:
        """Allow the current player to change their username."""
        if not verify_password(request.password, player.password_hash):
            raise HTTPException(status_code=401, detail="invalid_password")

        player_service = self.player_service_class(db)

        # Check if username is already the same (case-insensitive via canonical comparison)
        new_canonical = canonicalize_username(request.new_username)
        if player.username_canonical == new_canonical:
            return ChangeUsernameResponse(
                username=player.username,
                message="Username unchanged."
            )

        try:
            updated = await player_service.update_username(player, request.new_username)
        except UsernameTakenError as exc:
            raise HTTPException(status_code=409, detail="username_taken") from exc
        except InvalidUsernameError as exc:
            raise HTTPException(status_code=422, detail="invalid_username") from exc

        return ChangeUsernameResponse(
            username=updated.username,
            message="Username updated successfully."
        )

    async def _delete_account(
        self,
        request: DeleteAccountRequest,
        response: Response,
        player: Any,
        db: AsyncSession,
    ) -> None:
        """Delete the current player's account and related data."""
        if not verify_password(request.password, player.password_hash):
            raise HTTPException(status_code=401, detail="invalid_password")

        cleanup_service = self.cleanup_service_class(db)
        await cleanup_service.delete_player(player.player_id)

        clear_auth_cookies(response)
        response.status_code = 204
        return None

    async def _claim_daily_bonus(
        self,
        player: Any,
        db: AsyncSession,
    ) -> ClaimDailyBonusResponse:
        """Claim daily bonus for the player."""
        from backend.services import TransactionService
        from backend.utils.exceptions import DailyBonusNotAvailableError
        
        player_service = self.player_service_class(db)
        transaction_service = TransactionService(db, game_type=self.game_type)

        try:
            amount = await player_service.claim_daily_bonus(player, transaction_service)

            # Refresh player to get updated wallet and vault
            await db.refresh(player)

            # Invalidate cached dashboard data if cache exists
            try:
                from backend.utils.cache import dashboard_cache
                dashboard_cache.invalidate_player_data(player.player_id)
            except ImportError:
                pass  # Cache module may not exist in all games

            return ClaimDailyBonusResponse(
                success=True,
                amount=amount,
                new_wallet=player.wallet,
                new_vault=player.vault,
            )
        except DailyBonusNotAvailableError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except NotImplementedError:
            raise HTTPException(
                status_code=501, 
                detail=f"Daily bonus feature not implemented for {self.get_game_name()}"
            )

    @abstractmethod
    async def get_balance(self, player: Any, db: AsyncSession) -> PlayerBalance:
        """Get player balance and status. Must be implemented by subclasses."""
        pass
