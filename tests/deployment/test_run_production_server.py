from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

import pytest

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


def test_production_wrapper_execs_uvicorn_with_expected_startup_shape(monkeypatch):
    ns = _load_script_namespace()
    captured: dict[str, object] = {}

    def fake_execv(path: str, argv: list[str]) -> None:
        captured["path"] = path
        captured["argv"] = argv
        raise RuntimeError("execv-called")

    globals_ns = ns["main"].__globals__
    monkeypatch.setitem(globals_ns, "_load_keychain_env", lambda: None)
    monkeypatch.setitem(globals_ns, "_validate_production_settings", lambda: None)
    monkeypatch.setattr(ns["os"], "chdir", lambda _path: None)
    monkeypatch.setattr(ns["os"], "execv", fake_execv)

    with pytest.raises(RuntimeError, match="execv-called"):
        ns["main"]()

    assert captured["path"] == sys.executable
    assert captured["argv"] == [
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
