"""Helpers for sending magic-link emails."""
from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage

from backend.config import Settings

logger = logging.getLogger(__name__)


class MagicLinkMailerError(RuntimeError):
    """Raised when a magic-link email cannot be delivered."""


@dataclass(slots=True)
class MagicLinkMailer:
    """Minimal SMTP mailer for magic-link delivery."""

    settings: Settings

    async def send_magic_link(self, *, to_email: str, link_url: str, expires_at: datetime) -> None:
        if not self.settings.smtp_host:
            if self.settings.environment == "production":
                raise MagicLinkMailerError("smtp_not_configured")

            logger.info(
                "SMTP is not configured; skipping magic-link email delivery to %s",
                to_email,
            )
            return

        await asyncio.to_thread(self._send_magic_link_sync, to_email, link_url, expires_at)

    def _send_magic_link_sync(self, to_email: str, link_url: str, expires_at: datetime) -> None:
        subject = "Your Crowdcraft sign-in link"
        from_name = self.settings.smtp_from_name.strip() or "Crowdcraft"
        from_address = self.settings.smtp_from_address.strip() or self.settings.smtp_username.strip()
        if not from_address:
            from_address = "no-reply@localhost"

        body = (
            "Here is your Crowdcraft account link:\n\n"
            f"{link_url}\n\n"
            f"This link expires at {expires_at.isoformat()}.\n"
            "If you did not request this email, you can ignore it."
        )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"{from_name} <{from_address}>"
        message["To"] = to_email
        message.set_content(body)

        if self.settings.smtp_use_ssl:
            smtp_factory = smtplib.SMTP_SSL
            smtp_kwargs = {
                "host": self.settings.smtp_host,
                "port": self.settings.smtp_port,
                "timeout": self.settings.smtp_timeout_seconds,
                "context": ssl.create_default_context(),
            }
        else:
            smtp_factory = smtplib.SMTP
            smtp_kwargs = {
                "host": self.settings.smtp_host,
                "port": self.settings.smtp_port,
                "timeout": self.settings.smtp_timeout_seconds,
            }

        try:
            with smtp_factory(**smtp_kwargs) as server:
                if self.settings.smtp_use_tls and not self.settings.smtp_use_ssl:
                    server.starttls(context=ssl.create_default_context())

                if self.settings.smtp_username:
                    server.login(self.settings.smtp_username, self.settings.smtp_password)

                server.send_message(message)
        except Exception as exc:  # pragma: no cover - defensive transport wrapper
            raise MagicLinkMailerError("smtp_delivery_failed") from exc
