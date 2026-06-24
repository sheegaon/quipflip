"""Guest-account save and magic-link account recovery helpers."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from collections.abc import Iterable
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import bindparam, inspect, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.models.account import Account
from backend.models.magic_link import MagicLink
from backend.models.player import Player
from backend.models.refresh_token import RefreshToken
from backend.services.auth_service import AuthService
from backend.services.magic_link_mailer import MagicLinkMailer, MagicLinkMailerError
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
        mailer: MagicLinkMailer | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.player_service = player_service or PlayerService(db)
        self.auth_service = auth_service or AuthService(db, player_service=self.player_service)
        self.mailer = mailer or MagicLinkMailer(self.settings)

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

    async def _revoke_refresh_tokens_for_player(self, player_id: uuid.UUID) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.player_id == player_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    @staticmethod
    def _pick_latest_datetime(*values: datetime | None) -> datetime | None:
        candidates = [value for value in values if value is not None]
        return max(candidates) if candidates else None

    @staticmethod
    def _pick_earliest_datetime(*values: datetime | None) -> datetime | None:
        candidates = [value for value in values if value is not None]
        return min(candidates) if candidates else None

    @staticmethod
    def _pick_more_advanced_progress(current: str | None, incoming: str | None) -> str | None:
        progress_rank = {
            "not_started": 0,
            "in_progress": 1,
            "completed": 2,
        }
        if current is None:
            return incoming
        if incoming is None:
            return current

        return incoming if progress_rank.get(incoming, 0) > progress_rank.get(current, 0) else current

    def _merge_player_data_rows(self, source_data: object, target_data: object) -> None:
        if hasattr(target_data, "wallet"):
            target_data.wallet = int(getattr(target_data, "wallet", 0) or 0) + int(getattr(source_data, "wallet", 0) or 0)
        if hasattr(target_data, "vault"):
            target_data.vault = int(getattr(target_data, "vault", 0) or 0) + int(getattr(source_data, "vault", 0) or 0)

        if hasattr(target_data, "tutorial_completed"):
            target_data.tutorial_completed = bool(
                getattr(target_data, "tutorial_completed", False)
                or getattr(source_data, "tutorial_completed", False)
            )
        if hasattr(target_data, "tutorial_progress"):
            target_data.tutorial_progress = self._pick_more_advanced_progress(
                getattr(target_data, "tutorial_progress", None),
                getattr(source_data, "tutorial_progress", None),
            ) or "not_started"
        if hasattr(target_data, "tutorial_started_at"):
            target_data.tutorial_started_at = self._pick_earliest_datetime(
                getattr(target_data, "tutorial_started_at", None),
                getattr(source_data, "tutorial_started_at", None),
            )
        if hasattr(target_data, "tutorial_completed_at"):
            target_data.tutorial_completed_at = self._pick_latest_datetime(
                getattr(target_data, "tutorial_completed_at", None),
                getattr(source_data, "tutorial_completed_at", None),
            )

        if hasattr(target_data, "consecutive_incorrect_votes"):
            target_data.consecutive_incorrect_votes = max(
                int(getattr(target_data, "consecutive_incorrect_votes", 0) or 0),
                int(getattr(source_data, "consecutive_incorrect_votes", 0) or 0),
            )
        if hasattr(target_data, "vote_lockout_until"):
            target_data.vote_lockout_until = self._pick_latest_datetime(
                getattr(target_data, "vote_lockout_until", None),
                getattr(source_data, "vote_lockout_until", None),
            )
        if hasattr(target_data, "active_round_id") and getattr(target_data, "active_round_id", None) is None:
            target_data.active_round_id = getattr(source_data, "active_round_id", None)
        if hasattr(target_data, "flag_dismissal_streak"):
            target_data.flag_dismissal_streak = max(
                int(getattr(target_data, "flag_dismissal_streak", 0) or 0),
                int(getattr(source_data, "flag_dismissal_streak", 0) or 0),
            )
        if hasattr(target_data, "free_captions_used"):
            target_data.free_captions_used = int(
                getattr(target_data, "free_captions_used", 0) or 0
            ) + int(getattr(source_data, "free_captions_used", 0) or 0)

        if hasattr(target_data, "created_at"):
            target_data.created_at = self._pick_earliest_datetime(
                getattr(target_data, "created_at", None),
                getattr(source_data, "created_at", None),
            )
        if hasattr(target_data, "updated_at"):
            target_data.updated_at = datetime.now(UTC)

    async def _merge_single_row_models(
        self,
        models: Iterable[type[object]],
        source_player_id: uuid.UUID,
        target_player_id: uuid.UUID,
    ) -> None:
        for model in models:
            source_result = await self.db.execute(
                select(model).where(model.player_id == source_player_id)  # type: ignore[attr-defined]
            )
            source_row = source_result.scalar_one_or_none()
            if source_row is None:
                continue

            target_result = await self.db.execute(
                select(model).where(model.player_id == target_player_id)  # type: ignore[attr-defined]
            )
            target_row = target_result.scalar_one_or_none()
            if target_row is None:
                target_row = model(player_id=target_player_id)  # type: ignore[call-arg]
                self.db.add(target_row)

            self._merge_player_data_rows(source_row, target_row)
            await self.db.delete(source_row)

    async def _merge_daily_bonus_rows(
        self,
        models: Iterable[type[object]],
        source_player_id: uuid.UUID,
        target_player_id: uuid.UUID,
    ) -> None:
        for model in models:
            source_result = await self.db.execute(
                select(model).where(model.player_id == source_player_id)  # type: ignore[attr-defined]
            )
            source_rows = list(source_result.scalars().all())
            if not source_rows:
                continue

            target_result = await self.db.execute(
                select(model).where(model.player_id == target_player_id)  # type: ignore[attr-defined]
            )
            target_rows = list(target_result.scalars().all())
            target_by_date = {row.date: row for row in target_rows}

            for source_row in source_rows:
                target_row = target_by_date.get(source_row.date)
                if target_row is None:
                    target_row = model(  # type: ignore[call-arg]
                        player_id=target_player_id,
                        date=source_row.date,
                    )
                    self.db.add(target_row)
                    target_by_date[source_row.date] = target_row

                target_row.amount = int(getattr(target_row, "amount", 0) or 0) + int(
                    getattr(source_row, "amount", 0) or 0
                )
                if hasattr(target_row, "claimed_at"):
                    target_row.claimed_at = self._pick_earliest_datetime(
                        getattr(target_row, "claimed_at", None),
                        getattr(source_row, "claimed_at", None),
                    )
                if hasattr(target_row, "updated_at"):
                    target_row.updated_at = datetime.now(UTC)
                await self.db.delete(source_row)

    async def _merge_daily_state_rows(
        self,
        models: Iterable[type[object]],
        source_player_id: uuid.UUID,
        target_player_id: uuid.UUID,
    ) -> None:
        for model in models:
            source_result = await self.db.execute(
                select(model).where(model.player_id == source_player_id)  # type: ignore[attr-defined]
            )
            source_rows = list(source_result.scalars().all())
            if not source_rows:
                continue

            target_result = await self.db.execute(
                select(model).where(model.player_id == target_player_id)  # type: ignore[attr-defined]
            )
            target_rows = list(target_result.scalars().all())
            target_by_date = {row.date: row for row in target_rows}

            for source_row in source_rows:
                target_row = target_by_date.get(source_row.date)
                if target_row is None:
                    target_row = model(  # type: ignore[call-arg]
                        player_id=target_player_id,
                        date=source_row.date,
                    )
                    self.db.add(target_row)
                    target_by_date[source_row.date] = target_row

                target_row.free_captions_used = int(
                    getattr(target_row, "free_captions_used", 0) or 0
                ) + int(getattr(source_row, "free_captions_used", 0) or 0)
                if hasattr(target_row, "created_at"):
                    target_row.created_at = self._pick_earliest_datetime(
                        getattr(target_row, "created_at", None),
                        getattr(source_row, "created_at", None),
                    )
                if hasattr(target_row, "updated_at"):
                    target_row.updated_at = datetime.now(UTC)
                await self.db.delete(source_row)

    async def _reassign_player_foreign_keys(
        self,
        source_player_id: uuid.UUID,
        target_player_id: uuid.UUID,
    ) -> None:
        """Move player-owned history rows from a guest to the saved account."""

        skipped_tables = {
            "accounts",
            "magic_links",
            "refresh_tokens",
            "qf_daily_bonuses",
            "mm_daily_bonuses",
            "ir_daily_bonuses",
            "tl_daily_bonuses",
            "mm_player_daily_states",
            "tl_player_daily_states",
        }

        def _sync_reassign(sync_session) -> None:
            conn = sync_session.connection()
            inspector = inspect(conn)
            player_id_type = Player.__table__.c.player_id.type

            for table_name in inspector.get_table_names():
                if table_name in skipped_tables or table_name.endswith("_player_data"):
                    continue

                for fk in inspector.get_foreign_keys(table_name):
                    if fk.get("referred_table") != "players":
                        continue

                    for column_name in fk.get("constrained_columns", []):
                        statement = text(
                            f'UPDATE "{table_name}" '
                            f'SET "{column_name}" = :target_player_id '
                            f'WHERE "{column_name}" = :source_player_id'
                        ).bindparams(
                            bindparam("target_player_id", type_=player_id_type),
                            bindparam("source_player_id", type_=player_id_type),
                        )
                        sync_session.execute(
                            statement,
                            {
                                "target_player_id": target_player_id,
                                "source_player_id": source_player_id,
                            },
                        )

        await self.db.run_sync(_sync_reassign)

    async def _merge_guest_into_saved_player(
        self,
        source_player: Player,
        target_player: Player,
    ) -> None:
        """Move the guest's game data onto the saved account before issuing tokens."""

        if source_player.player_id == target_player.player_id:
            return

        from backend.models.ir.daily_bonus import IRDailyBonus
        from backend.models.ir.player_data import IRPlayerData
        from backend.models.mm.daily_bonus import MMDailyBonus
        from backend.models.mm.player_data import MMPlayerData
        from backend.models.mm.player_daily_state import MMPlayerDailyState
        from backend.models.qf.daily_bonus import QFDailyBonus
        from backend.models.qf.player_data import QFPlayerData
        from backend.models.tl.daily_bonus import TLDailyBonus
        from backend.models.tl.player_data import TLPlayerData
        from backend.models.tl.player_daily_state import TLPlayerDailyState

        await self._merge_single_row_models(
            [QFPlayerData, MMPlayerData, IRPlayerData, TLPlayerData],
            source_player.player_id,
            target_player.player_id,
        )
        await self._merge_daily_bonus_rows(
            [QFDailyBonus, MMDailyBonus, IRDailyBonus, TLDailyBonus],
            source_player.player_id,
            target_player.player_id,
        )
        await self._merge_daily_state_rows(
            [MMPlayerDailyState, TLPlayerDailyState],
            source_player.player_id,
            target_player.player_id,
        )
        await self.db.flush()
        await self._reassign_player_foreign_keys(source_player.player_id, target_player.player_id)

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

    def _build_magic_link_url(self, frontend_origin: str, redirect_path: str | None, token: str) -> str:
        normalized_origin = frontend_origin.strip().rstrip("/")
        if not normalized_origin:
            raise MagicLinkError("invalid_frontend_origin")

        relative_path = redirect_path or "/magic-link"
        parsed_path = urlsplit(relative_path)
        query_pairs = list(parse_qsl(parsed_path.query, keep_blank_values=True))
        query_pairs.append(("token", token))
        rebuilt_relative = urlunsplit(
            (
                "",
                "",
                parsed_path.path or "/magic-link",
                urlencode(query_pairs),
                parsed_path.fragment,
            )
        )

        return f"{normalized_origin}{rebuilt_relative}"

    async def request_magic_link(
        self,
        *,
        email: str,
        guest_player_id: uuid.UUID | str | None = None,
        redirect_path: str | None = None,
        frontend_origin: str | None = None,
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
        await self.db.flush()

        if frontend_origin is None:
            await self.db.rollback()
            raise MagicLinkError("invalid_frontend_origin")

        link_url = self._build_magic_link_url(frontend_origin, normalized_redirect_path, raw_token)

        try:
            await self.mailer.send_magic_link(
                to_email=normalized_email,
                link_url=link_url,
                expires_at=link.expires_at,
            )
        except MagicLinkMailerError as exc:
            await self.db.rollback()
            raise MagicLinkError("magic_link_email_failed") from exc

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
        if magic_link.consumed_at is not None:
            raise MagicLinkError("magic_link_already_used")

        saved_account = await self._get_account_for_email(magic_link.email)
        guest_player = magic_link.guest_player

        if magic_link.verified_at is None:
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
            await self._revoke_refresh_tokens_for_player(guest_player.player_id)
            magic_link.consumed_at = datetime.now(UTC)
            guest_player.last_login_date = datetime.now(UTC)
            await self.db.commit()
            access_token, refresh_token, expires_in = await self.auth_service.issue_tokens(
                guest_player,
                rotate_existing=False,
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

        if guest_player and guest_player.player_id == saved_player.player_id:
            await self._revoke_refresh_tokens_for_player(guest_player.player_id)

        magic_link.consumed_at = datetime.now(UTC)
        saved_player.last_login_date = datetime.now(UTC)
        await self.db.commit()
        access_token, refresh_token, expires_in = await self.auth_service.issue_tokens(
            saved_player,
            rotate_existing=False,
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
        token: str,
        *,
        merge_guest: bool,
    ) -> MagicLinkSessionResult:
        token_hash = self._token_hash(token)
        result = await self.db.execute(
            select(MagicLink).where(MagicLink.token_hash == token_hash)
        )
        magic_link = result.scalar_one_or_none()
        if not magic_link:
            raise MagicLinkError("magic_link_invalid_or_expired")
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
            await self._merge_guest_into_saved_player(guest_player, saved_player)
            guest_player.account_id = saved_account.account_id
            guest_player.is_guest = False
            saved_account.updated_at = datetime.now(UTC)
            player_for_session = saved_player
        else:
            player_for_session = saved_player

        magic_link.account_id = saved_account.account_id
        if guest_player is not None:
            await self._revoke_refresh_tokens_for_player(guest_player.player_id)
        magic_link.consumed_at = datetime.now(UTC)
        player_for_session.last_login_date = datetime.now(UTC)
        await self.db.commit()

        access_token, refresh_token, expires_in = await self.auth_service.issue_tokens(
            player_for_session,
            rotate_existing=False,
        )
        return MagicLinkSessionResult(
            status="authenticated",
            magic_link_id=magic_link.magic_link_id,
            player=player_for_session,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
