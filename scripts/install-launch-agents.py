#!/usr/bin/env python3
"""Render and install Crowdcraft LaunchAgent plist templates."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template

ROOT_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT_DIR / "scripts" / "templates"
DEFAULT_PLIST_DIR = Path.home() / "Library" / "LaunchAgents"


def _require_clean_checkout() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(ROOT_DIR),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    if result.stdout.strip():
        raise RuntimeError("Refusing to install launch agents from a dirty checkout")


def _render_template(template_path: Path, values: dict[str, str]) -> str:
    return Template(template_path.read_text(encoding="utf-8")).safe_substitute(values)


def _lint_plist(plist_path: Path) -> None:
    plutil = shutil.which("plutil")
    if not plutil:
        return
    result = subprocess.run([plutil, "-lint", str(plist_path)], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"plutil -lint failed for {plist_path}")


def _install_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(destination, 0o644)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="install-launch-agents", description="Install Crowdcraft LaunchAgent templates.")
    parser.add_argument(
        "--dest",
        default=str(DEFAULT_PLIST_DIR),
        help="Destination LaunchAgents directory (default: ~/Library/LaunchAgents).",
    )
    parser.add_argument("--checkout", default=str(ROOT_DIR), help="Production checkout path.")
    parser.add_argument("--python", default="", help="Absolute Python interpreter path.")
    parser.add_argument("--uvicorn", default="", help="Absolute uvicorn path.")
    parser.add_argument("--cloudflared", default="", help="Absolute cloudflared path.")
    parser.add_argument("--runtime-root", default="", help="Runtime root path.")
    parser.add_argument("--log-dir", default="", help="Log directory path.")
    parser.add_argument("--tunnel-uuid", default="", help="Cloudflare tunnel UUID.")
    parser.add_argument(
        "--credentials-file",
        default="",
        help="Absolute cloudflared credentials file path (default: ~/.cloudflared/<tunnel-uuid>.json).",
    )
    parser.add_argument(
        "--cloudflared-config",
        default=str(Path.home() / ".cloudflared" / "crowdcraft.yml"),
        help="Absolute cloudflared configuration file path.",
    )
    parser.add_argument("--release-id", default="", help="Release ID to embed in the plist.")
    parser.add_argument(
        "--expected-revision",
        default="",
        help="Expected Alembic revision to embed in the production LaunchAgent.",
    )
    parser.add_argument("--keychain-service", default="com.crowdcraft.production", help="Keychain service name.")
    parser.add_argument("--secret-key-account", default="SECRET_KEY", help="Keychain account for SECRET_KEY.")
    parser.add_argument("--openai-account", default="OPENAI_API_KEY", help="Keychain account for OPENAI_API_KEY.")
    parser.add_argument("--gemini-account", default="GEMINI_API_KEY", help="Keychain account for GEMINI_API_KEY.")
    parser.add_argument(
        "--smtp-host",
        default="",
        help="SMTP host for magic-link email (e.g. smtp.resend.com). Empty disables email sending.",
    )
    parser.add_argument("--smtp-port", default="587", help="SMTP port (default: 587 STARTTLS).")
    parser.add_argument("--smtp-username", default="", help="SMTP username (Resend: the literal 'resend').")
    parser.add_argument(
        "--smtp-from-address",
        default="no-reply@crowdcraftlabs.com",
        help="From address for outgoing email.",
    )
    parser.add_argument("--smtp-from-name", default="Crowdcraft", help="From display name for outgoing email.")
    parser.add_argument("--smtp-use-tls", default="true", help="Use STARTTLS (true/false).")
    parser.add_argument("--smtp-use-ssl", default="false", help="Use implicit SSL (true/false).")
    parser.add_argument("--smtp-timeout-seconds", default="10", help="SMTP connection timeout in seconds.")
    parser.add_argument(
        "--smtp-password-account",
        default="SMTP_PASSWORD",
        help="Keychain account for SMTP_PASSWORD (the Resend API key).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _require_clean_checkout()

    checkout = Path(args.checkout).expanduser().absolute()
    python_path = Path(args.python).expanduser().absolute() if args.python else checkout / ".venv" / "bin" / "python"
    uvicorn_path = Path(args.uvicorn).expanduser().absolute() if args.uvicorn else checkout / ".venv" / "bin" / "uvicorn"
    cloudflared_path = Path(args.cloudflared).expanduser().absolute() if args.cloudflared else shutil.which("cloudflared")
    runtime_root = Path(args.runtime_root).expanduser().absolute() if args.runtime_root else Path.home() / "Library" / "Application Support" / "Crowdcraft"
    log_dir = Path(args.log_dir).expanduser().absolute() if args.log_dir else Path.home() / "Library" / "Logs" / "Crowdcraft"
    database_url = f"sqlite+aiosqlite:///{runtime_root / 'crowdcraft.sqlite3'}"
    if cloudflared_path is None:
        raise RuntimeError("cloudflared not found on PATH and no --cloudflared was provided")
    cloudflared_path = Path(cloudflared_path).expanduser().absolute()
    credentials_file = (
        Path(args.credentials_file).expanduser().absolute()
        if args.credentials_file.strip()
        else (Path.home() / ".cloudflared" / f"{args.tunnel_uuid.strip()}.json")
    )
    cloudflared_config = Path(args.cloudflared_config).expanduser().absolute()
    if not args.tunnel_uuid.strip():
        raise RuntimeError("--tunnel-uuid is required to render the Cloudflare tunnel config")
    if not args.release_id.strip():
        raise RuntimeError("--release-id is required to render the production LaunchAgent")
    if not args.expected_revision.strip():
        raise RuntimeError("--expected-revision is required to render the production LaunchAgent")

    values = {
        "CHECKOUT_PATH": str(checkout),
        "PYTHON_PATH": str(python_path),
        "UVICORN_PATH": str(uvicorn_path),
        "CLOUDFLARED_PATH": str(cloudflared_path),
        "CLOUDFLARED_CREDENTIALS_FILE": str(credentials_file),
        "CLOUDFLARED_CONFIG_PATH": str(cloudflared_config),
        "TUNNEL_UUID": args.tunnel_uuid.strip(),
        "RUNTIME_ROOT": str(runtime_root),
        "DATABASE_URL": database_url,
        "STATIC_ROOT": str(runtime_root / "static" / "current"),
        "LOG_DIR": str(log_dir),
        "RELEASE_ID": args.release_id.strip(),
        "EXPECTED_REVISION": args.expected_revision.strip(),
        "ENVIRONMENT": "production",
        "QF_FRONTEND_URL": "https://quipflip.crowdcraftlabs.com",
        "MM_FRONTEND_URL": "https://mememint.crowdcraftlabs.com",
        "IR_FRONTEND_URL": "https://initialreaction.crowdcraftlabs.com",
        "TL_FRONTEND_URL": "https://thinklink.crowdcraftlabs.com",
        "WORKERS": "1",
        "TRUST_PROXY": "true",
        "KEYCHAIN_SERVICE": args.keychain_service,
        "SECRET_KEY_ACCOUNT": args.secret_key_account,
        "OPENAI_ACCOUNT": args.openai_account,
        "GEMINI_ACCOUNT": args.gemini_account,
        "SMTP_HOST": args.smtp_host.strip(),
        "SMTP_PORT": args.smtp_port.strip(),
        "SMTP_USERNAME": args.smtp_username.strip(),
        "SMTP_FROM_ADDRESS": args.smtp_from_address.strip(),
        "SMTP_FROM_NAME": args.smtp_from_name.strip(),
        "SMTP_USE_TLS": args.smtp_use_tls.strip(),
        "SMTP_USE_SSL": args.smtp_use_ssl.strip(),
        "SMTP_TIMEOUT_SECONDS": args.smtp_timeout_seconds.strip(),
        "SMTP_PASSWORD_ACCOUNT": args.smtp_password_account.strip(),
    }

    dest_dir = Path(args.dest).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    for template_name in ("com.crowdcraft.server.plist", "com.crowdcraft.tunnel.plist"):
        template_path = TEMPLATE_DIR / template_name
        rendered = _render_template(template_path, values)
        output_path = dest_dir / template_name
        output_path.write_text(rendered, encoding="utf-8")
        os.chmod(output_path, 0o644)
        _lint_plist(output_path)

    rendered_tunnel_config = _render_template(TEMPLATE_DIR / "crowdcraft.yml", values)
    cloudflared_config.parent.mkdir(parents=True, exist_ok=True)
    cloudflared_config.write_text(rendered_tunnel_config, encoding="utf-8")
    os.chmod(cloudflared_config, 0o600)

    print(f"Rendered launch agents to {dest_dir}")
    print(f"Rendered Cloudflare config to {cloudflared_config}")
    print(f"Install server plist: launchctl bootstrap gui/$(id -u) {dest_dir / 'com.crowdcraft.server.plist'}")
    print(f"Install tunnel plist: launchctl bootstrap gui/$(id -u) {dest_dir / 'com.crowdcraft.tunnel.plist'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
