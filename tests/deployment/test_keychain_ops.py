from __future__ import annotations

import json
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
