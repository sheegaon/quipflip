#!/usr/bin/env python3
"""Operator CLI entrypoint for Crowdcraft deployment tasks."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ops.release import (
    cleanup_retention,
    current_alembic_head,
    dump_json,
    load_server_launch_agent_environment,
    release_timestamp,
    run_deploy_release,
    run_deploy_rollback,
    run_sync_content,
    validate_config,
)
from scripts.ops.keychain import (
    DEFAULT_GEMINI_ACCOUNT,
    DEFAULT_KEYCHAIN_SERVICE,
    DEFAULT_OPENAI_ACCOUNT,
    DEFAULT_SECRET_ACCOUNT,
    DEFAULT_SMTP_PASSWORD_ACCOUNT,
    load_production_secret_environment,
    store_production_secrets,
)
from scripts.ops.smoke import dump_json as smoke_dump_json, run_smoke_sync


async def _handle_bootstrap(_args: argparse.Namespace) -> None:
    from backend.main import run_startup_bootstrap

    await run_startup_bootstrap()


def _load_installed_production_environment() -> None:
    for name, value in load_server_launch_agent_environment().items():
        os.environ[name] = value
    for name, value in load_production_secret_environment(os.environ).items():
        os.environ[name] = value

    from backend.config import get_settings

    get_settings.cache_clear()


def _handle_release_validate_config(_args: argparse.Namespace) -> int:
    _load_installed_production_environment()
    print(dump_json(validate_config()), end="")
    return 0


async def _handle_release_sync_content(args: argparse.Namespace) -> int:
    report = await run_sync_content(apply=args.apply, release_id=args.release_id)
    print(dump_json(report), end="")
    return 0


def _handle_cleanup_retention(args: argparse.Namespace) -> int:
    print(dump_json(cleanup_retention(apply=args.apply, command_id=args.command_id)), end="")
    return 0


def _handle_deploy_release(args: argparse.Namespace) -> int:
    _load_installed_production_environment()

    release_id = args.release_id or f"{release_timestamp()}-{args.revision[:8]}"
    expected_revision = args.expected_revision or current_alembic_head()
    os.environ["CROWDCRAFT_RELEASE_ID"] = release_id
    os.environ["CROWDCRAFT_EXPECTED_REVISION"] = expected_revision

    from backend.config import get_settings

    get_settings.cache_clear()
    report = run_deploy_release(
        revision=args.revision,
        release_id=release_id,
        apply=args.apply,
        run_smoke=not args.skip_smoke,
    )
    print(dump_json(report), end="")
    return 0


def _handle_deploy_rollback(args: argparse.Namespace) -> int:
    _load_installed_production_environment()
    report = run_deploy_rollback(release_id=args.release_id, apply=args.apply)
    print(dump_json(report), end="")
    return 0


def _handle_smoke(args: argparse.Namespace) -> int:
    report = run_smoke_sync(base_url=args.base_url)
    if args.json:
        print(smoke_dump_json(report), end="")
    else:
        print(f"Smoke passed for {report['base_url']} with {len(report['cases'])} hosts")
    return 0


def _handle_secrets_keychain_store(args: argparse.Namespace) -> int:
    report = store_production_secrets(
        service=args.service,
        secret_account=args.secret_account,
        openai_account=args.openai_account,
        gemini_account=args.gemini_account,
        smtp_password_account=args.smtp_password_account,
        include_secret_key=not args.skip_secret,
        include_openai=not args.skip_openai,
        include_gemini=not args.skip_gemini,
        include_smtp=args.with_smtp,
        apply=args.apply,
    )
    print(dump_json(report), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crowdcraft-ops",
        description="Crowdcraft deployment and maintenance operations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Run one-time startup bootstrap mutations explicitly.",
    )
    bootstrap_parser.set_defaults(handler=_handle_bootstrap)

    release_parser = subparsers.add_parser(
        "release",
        help="Release-time validation and content sync commands.",
    )
    release_subparsers = release_parser.add_subparsers(dest="release_command", required=True)

    release_validate = release_subparsers.add_parser(
        "validate-config",
        help="Validate production runtime configuration and tool availability.",
    )
    release_validate.set_defaults(handler=_handle_release_validate_config)

    release_sync = release_subparsers.add_parser(
        "sync-content",
        help="Report or apply release-scoped content synchronization.",
    )
    release_sync.add_argument("--release-id", default="", help="Release identifier to record in the report.")
    apply_group = release_sync.add_mutually_exclusive_group(required=False)
    apply_group.add_argument("--dry-run", dest="apply", action="store_false", help="Report without mutating the database.")
    apply_group.add_argument("--apply", dest="apply", action="store_true", help="Apply the content mutations.")
    release_sync.set_defaults(apply=False, handler=_handle_release_sync_content)

    maintenance_parser = subparsers.add_parser(
        "maintenance",
        help="Maintenance and retention commands.",
    )
    maintenance_subparsers = maintenance_parser.add_subparsers(dest="maintenance_command", required=True)

    cleanup_parser = maintenance_subparsers.add_parser(
        "cleanup-retention",
        help="Report backup-retention inventory for the current runtime root.",
    )
    cleanup_parser.add_argument("--command-id", default="", help="Retention command identifier to record in the report.")
    cleanup_group = cleanup_parser.add_mutually_exclusive_group(required=False)
    cleanup_group.add_argument("--dry-run", dest="apply", action="store_false", help="Report backup inventory only.")
    cleanup_group.add_argument("--apply", dest="apply", action="store_true", help="Apply the current retention policy.")
    cleanup_parser.set_defaults(apply=False, handler=_handle_cleanup_retention)

    deploy_parser = subparsers.add_parser(
        "deploy",
        help="Release and rollback orchestration.",
    )
    deploy_subparsers = deploy_parser.add_subparsers(dest="deploy_command", required=True)

    deploy_release = deploy_subparsers.add_parser(
        "release",
        help="Run the guarded deployment release sequence.",
    )
    deploy_release.add_argument("--revision", required=True, help="Full Git SHA to release.")
    deploy_release.add_argument("--release-id", default="", help="Release identifier to record.")
    deploy_release.add_argument(
        "--expected-revision",
        default="",
        help="Expected Alembic head (default: resolve the checkout's single head).",
    )
    deploy_release.add_argument("--skip-smoke", action="store_true", help="Skip the smoke gate for dry runs or rehearsals.")
    deploy_release.add_argument("--apply", action="store_true", help="Apply the release instead of producing a dry run.")
    deploy_release.set_defaults(handler=_handle_deploy_release)

    deploy_rollback = deploy_subparsers.add_parser(
        "rollback",
        help="Restore the recorded release artifacts.",
    )
    deploy_rollback.add_argument("--release-id", required=True, help="Release identifier to roll back.")
    deploy_rollback.add_argument("--apply", action="store_true", help="Apply the rollback instead of producing a dry run.")
    deploy_rollback.set_defaults(handler=_handle_deploy_rollback)

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Run the host-matrix smoke checks against a deployment.",
    )
    smoke_parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL to smoke.")
    smoke_parser.add_argument("--json", action="store_true", help="Print the smoke report as JSON.")
    smoke_parser.set_defaults(handler=_handle_smoke)

    secrets_parser = subparsers.add_parser(
        "secrets",
        help="Store production secrets in the macOS Keychain.",
    )
    secrets_subparsers = secrets_parser.add_subparsers(dest="secrets_command", required=True)

    keychain_store = secrets_subparsers.add_parser(
        "keychain-store",
        help="Plan or store the production signing and provider secrets.",
    )
    keychain_store.add_argument("--service", default=DEFAULT_KEYCHAIN_SERVICE, help="Keychain service name.")
    keychain_store.add_argument("--secret-account", default=DEFAULT_SECRET_ACCOUNT, help="Keychain account for SECRET_KEY.")
    keychain_store.add_argument("--openai-account", default=DEFAULT_OPENAI_ACCOUNT, help="Keychain account for OPENAI_API_KEY.")
    keychain_store.add_argument("--gemini-account", default=DEFAULT_GEMINI_ACCOUNT, help="Keychain account for GEMINI_API_KEY.")
    keychain_store.add_argument("--smtp-password-account", default=DEFAULT_SMTP_PASSWORD_ACCOUNT, help="Keychain account for SMTP_PASSWORD.")
    keychain_store.add_argument("--skip-secret", action="store_true", help="Skip storing SECRET_KEY (e.g. when adding only SMTP to a live deployment).")
    keychain_store.add_argument("--skip-openai", action="store_true", help="Skip storing OPENAI_API_KEY.")
    keychain_store.add_argument("--skip-gemini", action="store_true", help="Skip storing GEMINI_API_KEY.")
    keychain_store.add_argument("--with-smtp", action="store_true", help="Also store SMTP_PASSWORD (magic-link email delivery).")
    keychain_store.add_argument("--apply", action="store_true", help="Actually store the secrets instead of printing the plan.")
    keychain_store.set_defaults(handler=_handle_secrets_keychain_store)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("No command selected")

    result = handler(args)
    if asyncio.iscoroutine(result):
        return asyncio.run(result)
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
