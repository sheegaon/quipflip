from __future__ import annotations

import json
import os
import subprocess

from scripts.ops import crowdcraft_ops
from scripts.ops import keychain


def test_keychain_store_plans_default_accounts_without_apply():
    report = keychain.store_production_secrets(apply=False)

    assert report["service"] == keychain.DEFAULT_KEYCHAIN_SERVICE
    assert report["applied"] is False
    assert [item["account"] for item in report["items"]] == [
        keychain.DEFAULT_SECRET_ACCOUNT,
        keychain.DEFAULT_OPENAI_ACCOUNT,
        keychain.DEFAULT_GEMINI_ACCOUNT,
    ]
    assert all(item["status"] == "planned" for item in report["items"])
    assert all(item["command"][-1] == "-w" for item in report["items"])


def test_keychain_store_executes_security_prompt_without_secret_value(tmp_path, monkeypatch):
    security = tmp_path / "security"
    security.write_text("", encoding="utf-8")
    monkeypatch.setattr(keychain, "KEYCHAIN_SECURITY", security)

    commands: list[list[str]] = []

    def fake_run(command, check):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(keychain.subprocess, "run", fake_run)

    report = keychain.store_production_secrets(apply=True, include_openai=True, include_gemini=False)

    assert report["applied"] is True
    assert [item["account"] for item in report["items"]] == [
        keychain.DEFAULT_SECRET_ACCOUNT,
        keychain.DEFAULT_OPENAI_ACCOUNT,
    ]
    assert commands == [
        [
            str(security),
            "add-generic-password",
            "-U",
            "-s",
            keychain.DEFAULT_KEYCHAIN_SERVICE,
            "-a",
            keychain.DEFAULT_SECRET_ACCOUNT,
            "-w",
        ],
        [
            str(security),
            "add-generic-password",
            "-U",
            "-s",
            keychain.DEFAULT_KEYCHAIN_SERVICE,
            "-a",
            keychain.DEFAULT_OPENAI_ACCOUNT,
            "-w",
        ],
    ]


def test_load_production_secret_environment_reads_only_active_provider(monkeypatch):
    calls: list[tuple[str, str, bool]] = []

    def fake_read(service: str, account: str, *, required: bool):
        calls.append((service, account, required))
        return {
            keychain.DEFAULT_SECRET_ACCOUNT: "secret-value",
            keychain.DEFAULT_GEMINI_ACCOUNT: "gemini-value",
        }.get(account)

    monkeypatch.setattr(keychain, "read_generic_password", fake_read)

    environment = keychain.load_production_secret_environment(
        {
            "KEYCHAIN_SERVICE": keychain.DEFAULT_KEYCHAIN_SERVICE,
            "AI_PROVIDER": "gemini",
        }
    )

    assert environment == {
        "SECRET_KEY": "secret-value",
        "GEMINI_API_KEY": "gemini-value",
    }
    assert calls == [
        (keychain.DEFAULT_KEYCHAIN_SERVICE, keychain.DEFAULT_SECRET_ACCOUNT, True),
        (keychain.DEFAULT_KEYCHAIN_SERVICE, keychain.DEFAULT_GEMINI_ACCOUNT, False),
    ]


def test_crowdcraft_ops_secrets_command_routes_to_keychain(monkeypatch, capsys):
    captured: dict[str, object] = {}

    def fake_store_production_secrets(**kwargs):
        captured.update(kwargs)
        return {"applied": kwargs["apply"], "items": []}

    monkeypatch.setattr(crowdcraft_ops, "store_production_secrets", fake_store_production_secrets)

    exit_code = crowdcraft_ops.main(
        [
            "secrets",
            "keychain-store",
            "--service",
            "com.crowdcraft.production",
            "--skip-gemini",
            "--apply",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "service": "com.crowdcraft.production",
        "secret_account": keychain.DEFAULT_SECRET_ACCOUNT,
        "openai_account": keychain.DEFAULT_OPENAI_ACCOUNT,
        "gemini_account": keychain.DEFAULT_GEMINI_ACCOUNT,
        "include_openai": True,
        "include_gemini": False,
        "apply": True,
    }
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == {"applied": True, "items": []}


def test_deploy_release_loads_launch_agent_environment(monkeypatch, capsys):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        crowdcraft_ops,
        "load_server_launch_agent_environment",
        lambda: {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "sqlite+aiosqlite:////tmp/crowdcraft.sqlite3",
            "CROWDCRAFT_RUNTIME_ROOT": "/tmp/Crowdcraft",
        },
    )
    monkeypatch.setattr(crowdcraft_ops, "current_alembic_head", lambda: "revision-123")
    monkeypatch.setattr(
        crowdcraft_ops,
        "load_production_secret_environment",
        lambda _environment: {"SECRET_KEY": "secret-value"},
    )
    monkeypatch.setattr(
        crowdcraft_ops,
        "run_deploy_release",
        lambda **kwargs: captured.update(kwargs) or {"ok": True, **kwargs},
    )
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CROWDCRAFT_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("CROWDCRAFT_RELEASE_ID", raising=False)
    monkeypatch.delenv("CROWDCRAFT_EXPECTED_REVISION", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    exit_code = crowdcraft_ops.main(
        [
            "deploy",
            "release",
            "--revision",
            "abcdef1234567890",
            "--release-id",
            "release-123",
        ]
    )

    assert exit_code == 0
    assert captured["release_id"] == "release-123"
    assert os.environ["ENVIRONMENT"] == "production"
    assert os.environ["CROWDCRAFT_RELEASE_ID"] == "release-123"
    assert os.environ["CROWDCRAFT_EXPECTED_REVISION"] == "revision-123"
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_deploy_rollback_loads_launch_agent_environment(monkeypatch, capsys):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        crowdcraft_ops,
        "load_server_launch_agent_environment",
        lambda: {
            "ENVIRONMENT": "production",
            "DATABASE_URL": "sqlite+aiosqlite:////tmp/crowdcraft.sqlite3",
        },
    )
    monkeypatch.setattr(
        crowdcraft_ops,
        "run_deploy_rollback",
        lambda **kwargs: captured.update(kwargs) or {"ok": True, **kwargs},
    )
    monkeypatch.setattr(
        crowdcraft_ops,
        "load_production_secret_environment",
        lambda _environment: {"SECRET_KEY": "secret-value"},
    )
    monkeypatch.setenv("ENVIRONMENT", "development")

    exit_code = crowdcraft_ops.main(
        [
            "deploy",
            "rollback",
            "--release-id",
            "release-123",
        ]
    )

    assert exit_code == 0
    assert captured == {"release_id": "release-123", "apply": False}
    assert os.environ["ENVIRONMENT"] == "production"
    assert json.loads(capsys.readouterr().out)["ok"] is True
