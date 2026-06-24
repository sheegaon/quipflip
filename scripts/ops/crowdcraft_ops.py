#!/usr/bin/env python3
"""Operator CLI entrypoint for Crowdcraft deployment tasks."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.ops.release import cleanup_retention, dump_json, run_sync_content, validate_config


async def _handle_bootstrap(_args: argparse.Namespace) -> None:
    from backend.main import run_startup_bootstrap

    await run_startup_bootstrap()


def _handle_release_validate_config(_args: argparse.Namespace) -> int:
    print(dump_json(validate_config()), end="")
    return 0


async def _handle_release_sync_content(args: argparse.Namespace) -> int:
    report = await run_sync_content(apply=args.apply, release_id=args.release_id)
    print(dump_json(report), end="")
    return 0


def _handle_cleanup_retention(args: argparse.Namespace) -> int:
    print(dump_json(cleanup_retention(apply=args.apply, command_id=args.command_id)), end="")
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
