"""macOS Keychain helpers for Crowdcraft deployment secrets."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Mapping


KEYCHAIN_SECURITY = Path("/usr/bin/security")
DEFAULT_KEYCHAIN_SERVICE = "com.crowdcraft.production"
DEFAULT_SECRET_ACCOUNT = "SECRET_KEY"
DEFAULT_OPENAI_ACCOUNT = "OPENAI_API_KEY"
DEFAULT_GEMINI_ACCOUNT = "GEMINI_API_KEY"


def _build_add_password_command(service: str, account: str) -> list[str]:
    return [
        str(KEYCHAIN_SECURITY),
        "add-generic-password",
        "-U",
        "-s",
        service,
        "-a",
        account,
        "-w",
    ]


def store_generic_password(service: str, account: str, *, apply: bool) -> dict[str, Any]:
    """Return a redacted plan or store one Keychain item.

    The macOS `security` tool prompts for the password when `-w` is the last
    argument, which keeps the secret out of the shell history and process list.
    """

    command = _build_add_password_command(service, account)
    report: dict[str, Any] = {
        "service": service,
        "account": account,
        "command": command,
        "applied": apply,
    }
    if not apply:
        report["status"] = "planned"
        return report

    if not KEYCHAIN_SECURITY.is_file():
        raise RuntimeError("macOS security tool is unavailable")

    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Unable to store Keychain item {service!r}/{account!r}")

    report["status"] = "stored"
    return report


def read_generic_password(service: str, account: str, *, required: bool) -> str | None:
    if not service:
        if required:
            raise RuntimeError("KEYCHAIN_SERVICE must be configured")
        return None
    if not account:
        if required:
            raise RuntimeError(f"Keychain account is missing for {service}")
        return None
    if not KEYCHAIN_SECURITY.is_file():
        if required:
            raise RuntimeError("macOS security tool is unavailable")
        return None

    result = subprocess.run(
        [
            str(KEYCHAIN_SECURITY),
            "find-generic-password",
            "-s",
            service,
            "-a",
            account,
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        if required:
            raise RuntimeError(
                f"Unable to load Keychain item {service!r}/{account!r}: {message or 'unknown error'}"
            )
        return None

    secret = result.stdout.rstrip("\n")
    if not secret:
        if required:
            raise RuntimeError(f"Keychain item {service!r}/{account!r} is empty")
        return None
    return secret


def load_production_secret_environment(environment: Mapping[str, str]) -> dict[str, str]:
    service = environment.get("KEYCHAIN_SERVICE", "").strip()
    secret_account = environment.get("SECRET_KEY_ACCOUNT", "").strip() or DEFAULT_SECRET_ACCOUNT
    secrets = {
        "SECRET_KEY": read_generic_password(service, secret_account, required=True),
    }

    provider = environment.get("AI_PROVIDER", "openai").strip().lower()
    if provider == "openai":
        account = environment.get("OPENAI_ACCOUNT", "").strip() or DEFAULT_OPENAI_ACCOUNT
        provider_secret = read_generic_password(service, account, required=False)
        if provider_secret:
            secrets["OPENAI_API_KEY"] = provider_secret
    elif provider == "gemini":
        account = environment.get("GEMINI_ACCOUNT", "").strip() or DEFAULT_GEMINI_ACCOUNT
        provider_secret = read_generic_password(service, account, required=False)
        if provider_secret:
            secrets["GEMINI_API_KEY"] = provider_secret

    return {name: value for name, value in secrets.items() if value}


def store_production_secrets(
    *,
    service: str = DEFAULT_KEYCHAIN_SERVICE,
    secret_account: str = DEFAULT_SECRET_ACCOUNT,
    openai_account: str = DEFAULT_OPENAI_ACCOUNT,
    gemini_account: str = DEFAULT_GEMINI_ACCOUNT,
    include_openai: bool = True,
    include_gemini: bool = True,
    apply: bool = False,
) -> dict[str, Any]:
    """Plan or store the production signing and provider secrets."""

    accounts = [secret_account]
    if include_openai:
        accounts.append(openai_account)
    if include_gemini:
        accounts.append(gemini_account)

    items = [store_generic_password(service, account, apply=apply) for account in accounts]
    return {
        "service": service,
        "applied": apply,
        "items": items,
    }
