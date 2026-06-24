from __future__ import annotations

from pathlib import Path
import runpy


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "install-launch-agents.py"


def test_install_launch_agents_renders_templates(tmp_path, monkeypatch):
    ns = runpy.run_path(str(SCRIPT_PATH))

    ns["main"].__globals__["_require_clean_checkout"] = lambda: None
    monkeypatch.setattr(ns["shutil"], "which", lambda _name: None)

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".venv" / "bin").mkdir(parents=True)
    (checkout / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
    (checkout / ".venv" / "bin" / "uvicorn").write_text("#!/bin/sh\n", encoding="utf-8")
    (checkout / "scripts").mkdir()
    (checkout / "scripts" / "run-production-server.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    cloudflared = tmp_path / "cloudflared"
    cloudflared.write_text("#!/bin/sh\n", encoding="utf-8")

    dest_dir = tmp_path / "LaunchAgents"
    exit_code = ns["main"](
        [
            "--checkout",
            str(checkout),
            "--python",
            str(checkout / ".venv" / "bin" / "python"),
            "--uvicorn",
            str(checkout / ".venv" / "bin" / "uvicorn"),
            "--cloudflared",
            str(cloudflared),
            "--tunnel-uuid",
            "tunnel-uuid-123",
            "--release-id",
            "release-123",
            "--dest",
            str(dest_dir),
        ]
    )

    assert exit_code == 0
    server_plist = (dest_dir / "com.crowdcraft.server.plist").read_text(encoding="utf-8")
    tunnel_plist = (dest_dir / "com.crowdcraft.tunnel.plist").read_text(encoding="utf-8")
    tunnel_yml = (dest_dir / "crowdcraft.yml").read_text(encoding="utf-8")

    assert "${" not in server_plist
    assert "${" not in tunnel_plist
    assert "${" not in tunnel_yml
    assert "tunnel-uuid-123" in tunnel_yml


def test_install_launch_agents_points_server_plist_at_wrapper(tmp_path, monkeypatch):
    ns = runpy.run_path(str(SCRIPT_PATH))

    ns["main"].__globals__["_require_clean_checkout"] = lambda: None
    monkeypatch.setattr(ns["shutil"], "which", lambda _name: None)

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".venv" / "bin").mkdir(parents=True)
    (checkout / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
    (checkout / ".venv" / "bin" / "uvicorn").write_text("#!/bin/sh\n", encoding="utf-8")
    (checkout / "scripts").mkdir()
    (checkout / "scripts" / "run-production-server.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    cloudflared = tmp_path / "cloudflared"
    cloudflared.write_text("#!/bin/sh\n", encoding="utf-8")

    dest_dir = tmp_path / "LaunchAgents"
    exit_code = ns["main"](
        [
            "--checkout",
            str(checkout),
            "--python",
            str(checkout / ".venv" / "bin" / "python"),
            "--uvicorn",
            str(checkout / ".venv" / "bin" / "uvicorn"),
            "--cloudflared",
            str(cloudflared),
            "--tunnel-uuid",
            "tunnel-uuid-123",
            "--release-id",
            "release-123",
            "--dest",
            str(dest_dir),
        ]
    )

    server_plist = (dest_dir / "com.crowdcraft.server.plist").read_text(encoding="utf-8")

    assert exit_code == 0
    assert f"<string>{checkout / 'scripts' / 'run-production-server.py'}</string>" in server_plist
    assert f"<string>{checkout / '.venv' / 'bin' / 'python'}</string>" in server_plist
