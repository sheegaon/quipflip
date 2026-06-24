from __future__ import annotations

import os
import runpy
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run-production-server.py"


def _load_script_namespace():
    return runpy.run_path(str(SCRIPT_PATH))


def test_production_wrapper_loads_required_and_configured_provider_secrets(monkeypatch):
    ns = _load_script_namespace()

    calls: list[tuple[str, str, bool]] = []

    def fake_read_keychain_secret(service: str, account: str, *, required: bool):
        calls.append((service, account, required))
        mapping = {
            "SECRET_KEY": "secret-value",
            "OPENAI_API_KEY": "openai-value",
        }
        return mapping.get(account)

    monkeypatch.setenv(ns["KEYCHAIN_SERVICE_ENV"], "com.crowdcraft.production")
    monkeypatch.setenv(ns["SECRET_KEY_ACCOUNT_ENV"], "SECRET_KEY")
    monkeypatch.setenv(ns["OPENAI_ACCOUNT_ENV"], "OPENAI_API_KEY")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ns["_load_keychain_env"].__globals__["_read_keychain_secret"] = fake_read_keychain_secret

    ns["_load_keychain_env"]()

    assert os.environ["SECRET_KEY"] == "secret-value"
    assert os.environ["OPENAI_API_KEY"] == "openai-value"
    assert calls == [
        ("com.crowdcraft.production", "SECRET_KEY", True),
        ("com.crowdcraft.production", "OPENAI_API_KEY", False),
    ]
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_production_wrapper_skips_optional_provider_secret_when_disabled(monkeypatch):
    ns = _load_script_namespace()

    calls: list[tuple[str, str, bool]] = []

    def fake_read_keychain_secret(service: str, account: str, *, required: bool):
        calls.append((service, account, required))
        if account == "SECRET_KEY":
            return "secret-value"
        return None

    monkeypatch.setenv(ns["KEYCHAIN_SERVICE_ENV"], "com.crowdcraft.production")
    monkeypatch.setenv(ns["SECRET_KEY_ACCOUNT_ENV"], "SECRET_KEY")
    monkeypatch.setenv("AI_PROVIDER", "none")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    ns["_load_keychain_env"].__globals__["_read_keychain_secret"] = fake_read_keychain_secret

    ns["_load_keychain_env"]()

    assert os.environ["SECRET_KEY"] == "secret-value"
    assert "OPENAI_API_KEY" not in os.environ
    assert "GEMINI_API_KEY" not in os.environ
    assert calls == [("com.crowdcraft.production", "SECRET_KEY", True)]
    monkeypatch.delenv("SECRET_KEY", raising=False)
