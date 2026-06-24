from __future__ import annotations

from pathlib import Path
import runpy


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "install-launch-agents.py"


def test_install_launch_agents_renders_templates(tmp_path, monkeypatch):
    ns = runpy.run_path(str(SCRIPT_PATH))

    ns["main"].__globals__["_require_clean_checkout"] = lambda: None
    monkeypatch.setattr(ns["shutil"], "which", lambda _name: None)
    monkeypatch.setattr(ns["Path"], "home", lambda: tmp_path / "home")

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".venv" / "bin").mkdir(parents=True)
    (checkout / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
    (checkout / ".venv" / "bin" / "uvicorn").write_text("#!/bin/sh\n", encoding="utf-8")
    (checkout / "scripts").mkdir()
    (checkout / "scripts" / "run-production-server.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    cloudflared = tmp_path / "cloudflared-bin"
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
            "--expected-revision",
            "revision-123",
            "--cloudflared-config",
            str(tmp_path / "cloudflared" / "crowdcraft.yml"),
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--log-dir",
            str(tmp_path / "logs"),
            "--dest",
            str(dest_dir),
        ]
    )

    assert exit_code == 0
    server_plist = (dest_dir / "com.crowdcraft.server.plist").read_text(encoding="utf-8")
    tunnel_plist = (dest_dir / "com.crowdcraft.tunnel.plist").read_text(encoding="utf-8")
    tunnel_config_path = tmp_path / "cloudflared" / "crowdcraft.yml"
    tunnel_yml = tunnel_config_path.read_text(encoding="utf-8")

    assert "${" not in server_plist
    assert "${" not in tunnel_plist
    assert "${" not in tunnel_yml
    assert "tunnel-uuid-123" in tunnel_yml
    assert str(tmp_path / "home" / ".cloudflared" / "tunnel-uuid-123.json") in tunnel_yml
    assert "revision-123" in server_plist
    assert not (dest_dir / "crowdcraft.yml").exists()
    assert tunnel_config_path.stat().st_mode & 0o777 == 0o600


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

    cloudflared = tmp_path / "cloudflared-bin"
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
            "--expected-revision",
            "revision-123",
            "--cloudflared-config",
            str(tmp_path / "cloudflared" / "crowdcraft.yml"),
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--log-dir",
            str(tmp_path / "logs"),
            "--dest",
            str(dest_dir),
        ]
    )

    server_plist = (dest_dir / "com.crowdcraft.server.plist").read_text(encoding="utf-8")

    assert exit_code == 0
    assert f"<string>{checkout / 'scripts' / 'run-production-server.py'}</string>" in server_plist
    assert f"<string>{checkout / '.venv' / 'bin' / 'python'}</string>" in server_plist


def test_install_launch_agents_preserves_symlink_entrypoints(tmp_path, monkeypatch):
    ns = runpy.run_path(str(SCRIPT_PATH))

    ns["main"].__globals__["_require_clean_checkout"] = lambda: None
    monkeypatch.setattr(ns["shutil"], "which", lambda _name: None)

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".venv" / "bin").mkdir(parents=True)
    python_target = tmp_path / "python-real"
    python_target.write_text("#!/bin/sh\n", encoding="utf-8")
    uvicorn_target = tmp_path / "uvicorn-real"
    uvicorn_target.write_text("#!/bin/sh\n", encoding="utf-8")
    cloudflared_target = tmp_path / "cloudflared-real"
    cloudflared_target.write_text("#!/bin/sh\n", encoding="utf-8")
    (checkout / ".venv" / "bin" / "python").symlink_to(python_target)
    (checkout / ".venv" / "bin" / "uvicorn").symlink_to(uvicorn_target)
    (checkout / "scripts").mkdir()
    (checkout / "scripts" / "run-production-server.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    cloudflared_link = tmp_path / "cloudflared-link"
    cloudflared_link.symlink_to(cloudflared_target)
    cloudflared_config_dir = tmp_path / "cloudflared-config"

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
            str(cloudflared_link),
            "--tunnel-uuid",
            "tunnel-uuid-123",
            "--release-id",
            "release-123",
            "--expected-revision",
            "revision-123",
            "--cloudflared-config",
            str(cloudflared_config_dir / "crowdcraft.yml"),
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--log-dir",
            str(tmp_path / "logs"),
            "--dest",
            str(dest_dir),
        ]
    )

    assert exit_code == 0
    server_plist = (dest_dir / "com.crowdcraft.server.plist").read_text(encoding="utf-8")
    tunnel_plist = (dest_dir / "com.crowdcraft.tunnel.plist").read_text(encoding="utf-8")

    assert f"<string>{checkout / '.venv' / 'bin' / 'python'}</string>" in server_plist
    assert f"<string>{cloudflared_link}</string>" in tunnel_plist
    assert str(python_target) not in server_plist
    assert str(cloudflared_target) not in tunnel_plist
