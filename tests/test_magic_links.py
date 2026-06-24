"""Tests for guest-save magic-link flows."""
from __future__ import annotations

import hashlib
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.models.account import Account
from backend.models.magic_link import MagicLink
from backend.models.player import Player
from backend.models.qf.player_data import QFPlayerData


API_BASE_URL = "http://test/qf"


async def _capture_magic_link_send(captured: list[dict], *args, **kwargs):
    captured.append(
        {
            "to_email": kwargs["to_email"],
            "link_url": kwargs["link_url"],
            "expires_at": kwargs["expires_at"],
        }
    )


class _MagicLinkSecretStub:
    """Deterministic token source for magic-link tests without affecting refresh tokens."""

    def __init__(self, token: str):
        self._token = token

    def token_urlsafe(self, _n: int) -> str:
        return self._token


@pytest.mark.asyncio
async def test_magic_link_creates_account_for_guest(test_app, db_session, monkeypatch):
    """A guest can save progress to a new account through a magic link."""

    token = "guest-save-token"
    sent_links: list[dict] = []
    monkeypatch.setattr(
        "backend.services.account_service.secrets",
        _MagicLinkSecretStub(token),
    )
    monkeypatch.setattr(
        "backend.services.magic_link_mailer.MagicLinkMailer.send_magic_link",
        lambda self, **kwargs: _capture_magic_link_send(sent_links, **kwargs),
    )

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        guest_response = await client.post("/player/guest")
        assert guest_response.status_code == 201
        guest_data = guest_response.json()
        guest_refresh_token = guest_data["refresh_token"]

        request_response = await client.post(
            "/auth/magic-links",
            json={
                "email": "tal.saved@example.com",
                "guest_player_id": guest_data["player_id"],
            },
        )

        assert request_response.status_code == 202
        request_data = request_response.json()
        assert request_data["email"] == "tal.saved@example.com"
        assert "magic_link_id" not in request_data
        assert sent_links and sent_links[0]["to_email"] == "tal.saved@example.com"
        assert token in sent_links[0]["link_url"]

        magic_link = await db_session.scalar(
            select(MagicLink).where(MagicLink.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest())
        )
        assert magic_link is not None
        assert magic_link.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
        assert magic_link.consumed_at is None

        consume_response = await client.post(
            "/auth/magic-links/consume",
            json={"token": token},
        )

        assert consume_response.status_code == 200
        consume_data = consume_response.json()
        assert consume_data["status"] == "authenticated"
        assert consume_data["auth"]["player"]["account_id"] is not None
        assert consume_data["auth"]["player"]["is_guest"] is False

        refresh_after_upgrade = await client.post(
            "/auth/refresh",
            json={"refresh_token": guest_refresh_token},
            params={"game_type": "qf"},
        )
        assert refresh_after_upgrade.status_code == 401

        account = await db_session.scalar(
            select(Account).where(Account.primary_email == "tal.saved@example.com")
        )
        assert account is not None
        assert account.primary_player_id == UUID(guest_data["player_id"])

        db_session.expire_all()
        linked_player = await db_session.scalar(
            select(Player).where(Player.player_id == UUID(guest_data["player_id"]))
        )
        assert linked_player is not None
        assert linked_player.account_id == account.account_id
        assert linked_player.is_guest is False

        refreshed_link = await db_session.scalar(
            select(MagicLink).where(MagicLink.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest())
        )
        assert refreshed_link is not None
        assert refreshed_link.consumed_at is not None

        second_consume = await client.post(
            "/auth/magic-links/consume",
            json={"token": token},
        )
        assert second_consume.status_code == 401


@pytest.mark.asyncio
async def test_magic_link_collision_prompts_for_merge(test_app, db_session, monkeypatch):
    """A magic-link collision should surface merge vs sign-in choices."""

    token = "collision-token"
    sent_links: list[dict] = []
    monkeypatch.setattr(
        "backend.services.account_service.secrets",
        _MagicLinkSecretStub(token),
    )
    monkeypatch.setattr(
        "backend.services.magic_link_mailer.MagicLinkMailer.send_magic_link",
        lambda self, **kwargs: _capture_magic_link_send(sent_links, **kwargs),
    )

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        existing_response = await client.post(
            "/player",
            json={
                "username": "tal_saved",
                "email": "tal.collision@example.com",
                "password": "Password123!",
            },
        )
        assert existing_response.status_code == 201
        existing_data = existing_response.json()

        guest_response = await client.post("/player/guest")
        assert guest_response.status_code == 201
        guest_data = guest_response.json()
        guest_refresh_token = guest_data["refresh_token"]

        existing_qf_data = await db_session.scalar(
            select(QFPlayerData).where(QFPlayerData.player_id == UUID(existing_data["player_id"]))
        )
        guest_qf_data = await db_session.scalar(
            select(QFPlayerData).where(QFPlayerData.player_id == UUID(guest_data["player_id"]))
        )
        assert existing_qf_data is not None
        assert guest_qf_data is not None
        expected_wallet = existing_qf_data.wallet + guest_qf_data.wallet
        expected_vault = existing_qf_data.vault + guest_qf_data.vault

        request_response = await client.post(
            "/auth/magic-links",
            json={
                "email": "tal.collision@example.com",
                "guest_player_id": guest_data["player_id"],
            },
        )
        assert request_response.status_code == 202
        assert "magic_link_id" not in request_response.json()
        assert sent_links and token in sent_links[0]["link_url"]

        consume_response = await client.post(
            "/auth/magic-links/consume",
            json={"token": token},
        )
        assert consume_response.status_code == 200
        consume_data = consume_response.json()
        assert consume_data["status"] == "merge_required"
        assert consume_data["guest_player"]["player_id"] == guest_data["player_id"]
        assert consume_data["saved_player"]["player_id"] == existing_data["player_id"]

        resolve_response = await client.post(
            "/auth/magic-links/resolve",
            json={"token": token, "merge_guest": True},
        )
        assert resolve_response.status_code == 200
        resolve_data = resolve_response.json()
        assert resolve_data["status"] == "authenticated"
        assert resolve_data["auth"]["player"]["player_id"] == existing_data["player_id"]
        assert resolve_data["auth"]["player"]["username"] == existing_data["username"]

        refresh_after_upgrade = await client.post(
            "/auth/refresh",
            json={"refresh_token": guest_refresh_token},
            params={"game_type": "qf"},
        )
        assert refresh_after_upgrade.status_code == 401

        account = await db_session.scalar(
            select(Account).where(Account.primary_email == "tal.collision@example.com")
        )
        assert account is not None
        assert resolve_data["auth"]["player"]["account_id"] == str(account.account_id)
        assert account.primary_player_id == UUID(existing_data["player_id"])

        db_session.expire_all()
        saved_qf_data = await db_session.scalar(
            select(QFPlayerData).where(QFPlayerData.player_id == UUID(existing_data["player_id"]))
        )
        assert saved_qf_data is not None
        assert saved_qf_data.wallet == expected_wallet
        assert saved_qf_data.vault == expected_vault

        merged_guest = await db_session.scalar(
            select(Player).where(Player.player_id == UUID(guest_data["player_id"]))
        )
        assert merged_guest is not None
        assert merged_guest.account_id == account.account_id
        assert merged_guest.is_guest is False

        saved_player = await db_session.scalar(
            select(Player).where(Player.player_id == UUID(existing_data["player_id"]))
        )
        assert saved_player is not None
        assert saved_player.account_id == account.account_id


@pytest.mark.asyncio
async def test_magic_link_collision_can_sign_in_without_merging(test_app, db_session, monkeypatch):
    """A collision can authenticate the existing account without merging guest history."""

    token = "collision-signin-token"
    sent_links: list[dict] = []
    monkeypatch.setattr(
        "backend.services.account_service.secrets",
        _MagicLinkSecretStub(token),
    )
    monkeypatch.setattr(
        "backend.services.magic_link_mailer.MagicLinkMailer.send_magic_link",
        lambda self, **kwargs: _capture_magic_link_send(sent_links, **kwargs),
    )

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        existing_response = await client.post(
            "/player",
            json={
                "username": "tal_saved_again",
                "email": "tal.collision.signin@example.com",
                "password": "Password123!",
            },
        )
        assert existing_response.status_code == 201
        existing_data = existing_response.json()

        guest_response = await client.post("/player/guest")
        assert guest_response.status_code == 201
        guest_data = guest_response.json()
        guest_refresh_token = guest_data["refresh_token"]

        request_response = await client.post(
            "/auth/magic-links",
            json={
                "email": "tal.collision.signin@example.com",
                "guest_player_id": guest_data["player_id"],
            },
        )
        assert request_response.status_code == 202
        assert "magic_link_id" not in request_response.json()
        assert sent_links and token in sent_links[0]["link_url"]

        consume_response = await client.post(
            "/auth/magic-links/consume",
            json={"token": token},
        )
        assert consume_response.status_code == 200
        consume_data = consume_response.json()
        assert consume_data["status"] == "merge_required"

        resolve_response = await client.post(
            "/auth/magic-links/resolve",
            json={"token": token, "merge_guest": False},
        )
        assert resolve_response.status_code == 200
        resolve_data = resolve_response.json()
        assert resolve_data["status"] == "authenticated"

        refresh_after_upgrade = await client.post(
            "/auth/refresh",
            json={"refresh_token": guest_refresh_token},
            params={"game_type": "qf"},
        )
        assert refresh_after_upgrade.status_code == 401

        account = await db_session.scalar(
            select(Account).where(Account.primary_email == "tal.collision.signin@example.com")
        )
        assert account is not None
        assert resolve_data["auth"]["player"]["player_id"] == existing_data["player_id"]
        assert resolve_data["auth"]["player"]["username"] == existing_data["username"]
        assert resolve_data["auth"]["player"]["account_id"] == str(account.account_id)

        db_session.expire_all()
        merged_guest = await db_session.scalar(
            select(Player).where(Player.player_id == UUID(guest_data["player_id"]))
        )
        assert merged_guest is not None
        assert merged_guest.account_id is None
        assert merged_guest.is_guest is True

        saved_player = await db_session.scalar(
            select(Player).where(Player.player_id == UUID(existing_data["player_id"]))
        )
        assert saved_player is not None
        assert saved_player.account_id == account.account_id


@pytest.mark.asyncio
async def test_magic_link_rejects_spoofed_frontend_origin(test_app, db_session, monkeypatch):
    """The frontend origin used for magic links must match the validated host scope."""

    token = "spoofed-origin-token"
    sent_links: list[dict] = []
    monkeypatch.setattr(
        "backend.services.account_service.secrets",
        _MagicLinkSecretStub(token),
    )
    monkeypatch.setattr(
        "backend.services.magic_link_mailer.MagicLinkMailer.send_magic_link",
        lambda self, **kwargs: _capture_magic_link_send(sent_links, **kwargs),
    )

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="https://quipflip.crowdcraftlabs.com",
    ) as client:
        guest_response = await client.post("/qf/player/guest")
        assert guest_response.status_code == 201
        guest_data = guest_response.json()

        request_response = await client.post(
            "/qf/auth/magic-links",
            json={
                "email": "tal.spoofed@example.com",
                "guest_player_id": guest_data["player_id"],
            },
            headers={"Origin": "https://evil.example"},
        )

        assert request_response.status_code == 400
        assert request_response.json()["detail"] == "invalid_frontend_origin"
        assert not sent_links
