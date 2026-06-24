"""Guest-account save and magic-link account recovery helpers."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.account import Account
from backend.models.magic_link import MagicLink
from backend.models.player import Player
from backend.services.auth_service import AuthService
from backend.services.player_service import PlayerService

logger = logging.getLogger(__name__)


class AccountServiceError(RuntimeError):
    """Raised when account-linking operations fail."""


class MagicLinkError(AccountServiceError):
    """Raised when magic-link verification or resolution fails."""


@dataclass(slots=True)
class MagicLinkRequestResult:
    """Result returned after requesting a magic link."""

    magic_link_id: uuid.UUID
    email: str
    expires_at: datetime


@dataclass(slots=True)
class MagicLinkSessionResult:
    """Result returned after consuming or resolving a magic link."""

    status: Literal["authenticated", "merge_required"]
    magic_link_id: uuid.UUID
    player: Player | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    guest_player: Player | None = None
    saved_player: Player | None = None


class AccountService:
    """Service for creating and recovering recoverable accounts."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        auth_service: AuthService | None = None,
        player_service: PlayerService | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.player_service = player_service or PlayerService(db)
        self.auth_service = auth_service or AuthService(db, player_service=self.player_service)

    def _normalize_email(self, email: str) -> str:
        normalized = email.strip().lower()
        if not normalized:
            raise MagicLinkError("invalid_email")
        return normalized

    def _normalize_redirect_path(self, redirect_path: str | None) -> str | None:
        if redirect_path is None:
            return None

        normalized = redirect_path.strip()
        if not normalized:
            return None
        if not normalized.startswith("/") or normalized.startswith("//") or "://" in normalized:
            raise MagicLinkError("invalid_redirect_path")
        return normalized

    async def _get_player_by_id(self, player_id: uuid.UUID | str) -> Player | None:
        result = await self.db.execute(
            select(Player).where(Player.player_id == player_id)
        )
        return result.scalar_one_or_none()

    async def _get_player_by_email(self, email: str) -> Player | None:
        result = await self.db.execute(select(Player).where(Player.email == email))
        return result.scalar_one_or_none()

    async def _get_account_by_email(self, email: str) -> Account | None:
        result = await self.db.execute(select(Account).where(Account.primary_email == email))
        return result.scalar_one_or_none()

    async def _get_account_for_email(self, email: str) -> Account | None:
        account = await self._get_account_by_email(email)
        if account:
            return account

        player = await self._get_player_by_email(email)
        if not player:
            return None

        account = Account(
            primary_email=email,
            primary_player_id=player.player_id,
            email_verified_at=datetime.now(UTC),
        )
        self.db.add(account)
        await self.db.flush()

        player.account = account
        player.account_id = account.account_id
        player.is_guest = False
        logger.info("Created recoverable account for legacy player %s", player.player_id)
        return account

    async def _ensure_account_for_player(self, player: Player, email: str) -> Account:
        account = await self._get_account_by_email(email)
        if account:
            return account

        account = Account(
            primary_email=email,
            primary_player_id=player.player_id,
            email_verified_at=datetime.now(UTC),
        )
        self.db.add(account)
        await self.db.flush()

        player.account = account
        player.account_id = account.account_id
        player.is_guest = False
        logger.info("Created account %s for player %s", account.account_id, player.player_id)
        return account

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def request_magic_link(
        self,
        *,
        email: str,
        guest_player_id: uuid.UUID | str | None = None,
        redirect_path: str | None = None,
    ) -> MagicLinkRequestResult:
        normalized_email = self._normalize_email(email)
        normalized_redirect_path = self._normalize_redirect_path(redirect_path)

        guest_player: Player | None = None
        if guest_player_id is not None:
            guest_player = await self._get_player_by_id(guest_player_id)
            if guest_player is None:
                raise MagicLinkError("guest_player_not_found")

        raw_token = secrets.token_urlsafe(48)
        link = MagicLink(
            magic_link_id=uuid.uuid4(),
            email=normalized_email,
            token_hash=self._token_hash(raw_token),
            guest_player_id=guest_player.player_id if guest_player else None,
            redirect_path=normalized_redirect_path,
            expires_at=datetime.now(UTC) + timedelta(minutes=self.settings.magic_link_exp_minutes),
        )
        self.db.add(link)
        await self.db.commit()

        logger.info(
            "Requested magic link %s for %s (guest=%s)",
            link.magic_link_id,
            normalized_email,
            bool(guest_player_id),
        )

        return MagicLinkRequestResult(
            magic_link_id=link.magic_link_id,
            email=normalized_email,
            expires_at=link.expires_at,
        )

    async def consume_magic_link(
        self,
        token: str,
    ) -> MagicLinkSessionResult:
        token_hash = self._token_hash(token)
        result = await self.db.execute(
            select(MagicLink).where(MagicLink.token_hash == token_hash)
        )
        magic_link = result.scalar_one_or_none()
        if not magic_link or not magic_link.is_active():
            raise MagicLinkError("magic_link_invalid_or_expired")
        if magic_link.verified_at is not None or magic_link.consumed_at is not None:
            raise MagicLinkError("magic_link_already_used")

        saved_account = await self._get_account_for_email(magic_link.email)
        guest_player = magic_link.guest_player

        magic_link.verified_at = datetime.now(UTC)
        if saved_account:
            magic_link.account_id = saved_account.account_id

        if guest_player and saved_account and saved_account.primary_player_id != guest_player.player_id:
            saved_player = await self._get_player_by_id(saved_account.primary_player_id)
            if saved_player is None:
                raise MagicLinkError("account_player_missing")
            await self.db.commit()
            logger.info(
                "Magic link %s requires merge confirmation for guest %s and account %s",
                magic_link.magic_link_id,
                guest_player.player_id,
                saved_account.account_id,
            )
            return MagicLinkSessionResult(
                status="merge_required",
                magic_link_id=magic_link.magic_link_id,
                guest_player=guest_player,
                saved_player=saved_player,
            )

        if guest_player and saved_account is None:
            saved_account = await self._ensure_account_for_player(guest_player, magic_link.email)
            magic_link.account_id = saved_account.account_id
            magic_link.consumed_at = datetime.now(UTC)
            await self.db.commit()
            guest_player.last_login_date = datetime.now(UTC)
            access_token, refresh_token, expires_in = await self.auth_service.issue_tokens(
                guest_player
            )
            return MagicLinkSessionResult(
                status="authenticated",
                magic_link_id=magic_link.magic_link_id,
                player=guest_player,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
            )

        if not saved_account:
            raise MagicLinkError("account_not_found")

        saved_player = await self._get_player_by_id(saved_account.primary_player_id)
        if saved_player is None:
            raise MagicLinkError("account_player_missing")

        magic_link.consumed_at = datetime.now(UTC)
        await self.db.commit()
        saved_player.last_login_date = datetime.now(UTC)
        access_token, refresh_token, expires_in = await self.auth_service.issue_tokens(
            saved_player
        )
        return MagicLinkSessionResult(
            status="authenticated",
            magic_link_id=magic_link.magic_link_id,
            player=saved_player,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    async def resolve_magic_link(
        self,
        magic_link_id: uuid.UUID | str,
        *,
        merge_guest: bool,
    ) -> MagicLinkSessionResult:
        result = await self.db.execute(
            select(MagicLink).where(MagicLink.magic_link_id == magic_link_id)
        )
        magic_link = result.scalar_one_or_none()
        if not magic_link:
            raise MagicLinkError("magic_link_not_found")
        if magic_link.verified_at is None or magic_link.consumed_at is not None:
            raise MagicLinkError("magic_link_not_ready")
        if not magic_link.is_active():
            raise MagicLinkError("magic_link_invalid_or_expired")

        saved_account = await self._get_account_for_email(magic_link.email)
        if not saved_account:
            raise MagicLinkError("account_not_found")

        saved_player = await self._get_player_by_id(saved_account.primary_player_id)
        if saved_player is None:
            raise MagicLinkError("account_player_missing")

        guest_player = magic_link.guest_player
        if merge_guest:
            if guest_player is None:
                raise MagicLinkError("guest_player_not_found")
            guest_player.account = saved_account
            guest_player.account_id = saved_account.account_id
            guest_player.is_guest = False
            player_for_session = guest_player
        else:
            player_for_session = saved_player

        magic_link.account_id = saved_account.account_id
        magic_link.consumed_at = datetime.now(UTC)
        await self.db.commit()

        if merge_guest and guest_player is not None:
            await self.auth_service.revoke_all_refresh_tokens(guest_player.player_id)

        player_for_session.last_login_date = datetime.now(UTC)
        access_token, refresh_token, expires_in = await self.auth_service.issue_tokens(
            player_for_session
        )
        return MagicLinkSessionResult(
            status="authenticated",
            magic_link_id=magic_link.magic_link_id,
            player=player_for_session,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
