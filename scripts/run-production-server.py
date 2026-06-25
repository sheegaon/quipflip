#!/usr/bin/env python3
"""Production server wrapper for the Crowdcraft deployment."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ops.keychain import read_generic_password

KEYCHAIN_SERVICE_ENV = "KEYCHAIN_SERVICE"
SECRET_KEY_ACCOUNT_ENV = "SECRET_KEY_ACCOUNT"
OPENAI_ACCOUNT_ENV = "OPENAI_ACCOUNT"
GEMINI_ACCOUNT_ENV = "GEMINI_ACCOUNT"
SMTP_PASSWORD_ACCOUNT_ENV = "SMTP_PASSWORD_ACCOUNT"


def _read_keychain_secret(service: str, account: str, *, required: bool) -> str | None:
    return read_generic_password(service, account, required=required)


def _load_keychain_env() -> None:
    env = os.environ
    service = env.get(KEYCHAIN_SERVICE_ENV, "").strip()
    if not service:
        raise RuntimeError("KEYCHAIN_SERVICE must be set for the production wrapper")

    secret_key_account = env.get(SECRET_KEY_ACCOUNT_ENV, "").strip() or "SECRET_KEY"
    secret_key = _read_keychain_secret(service, secret_key_account, required=True)
    if not secret_key:
        raise RuntimeError("SECRET_KEY could not be loaded from Keychain")
    env["SECRET_KEY"] = secret_key
    del secret_key

    provider = env.get("AI_PROVIDER", "openai").strip().lower()
    if provider == "openai":
        openai_account = env.get(OPENAI_ACCOUNT_ENV, "").strip() or "OPENAI_API_KEY"
        openai_api_key = _read_keychain_secret(service, openai_account, required=False)
        if openai_api_key:
            env["OPENAI_API_KEY"] = openai_api_key
            del openai_api_key
    elif provider == "gemini":
        gemini_account = env.get(GEMINI_ACCOUNT_ENV, "").strip() or "GEMINI_API_KEY"
        gemini_api_key = _read_keychain_secret(service, gemini_account, required=False)
        if gemini_api_key:
            env["GEMINI_API_KEY"] = gemini_api_key
            del gemini_api_key

    # SMTP password for magic-link delivery. Only consulted when an SMTP host is
    # configured, so email-less deployments are unaffected.
    if env.get("SMTP_HOST", "").strip():
        smtp_account = env.get(SMTP_PASSWORD_ACCOUNT_ENV, "").strip() or "SMTP_PASSWORD"
        smtp_password = _read_keychain_secret(service, smtp_account, required=False)
        if smtp_password:
            env["SMTP_PASSWORD"] = smtp_password
            del smtp_password


def _validate_production_settings() -> None:
    from backend.config import get_settings
    from backend.runtime.config import validate_runtime_resources, validate_runtime_settings

    settings = get_settings()
    errors = validate_runtime_settings(settings) + validate_runtime_resources(settings)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    os.chdir(ROOT_DIR)
    _load_keychain_env()
    _validate_production_settings()

    argv = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--workers",
        "1",
        "--proxy-headers",
        "--forwarded-allow-ips",
        "127.0.0.1",
    ]
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    main()
