#!/usr/bin/env python3
"""SQLite backup, verification, and restore operations."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine.url import make_url

from scripts.ops.common import (
    current_git_sha,
    ensure_directories,
    json_dump,
    json_load,
    release_timestamp,
    sha256_file,
    validate_production_configuration,
)


SCRIPT_VERSION = "0.1"
BACKUP_FILE_NAME = "backup.sqlite3"
MANIFEST_FILE_NAME = "manifest.json"


@dataclass(frozen=True, slots=True)
class BackupPaths:
    backup_dir: Path
    database_file: Path
    manifest_file: Path


def _resolve_sqlite_path(value: str) -> Path:
    raw = value.strip()
    if not raw:
        raise ValueError("Empty SQLite source path")

    if "://" not in raw:
        return Path(raw).expanduser().resolve()

    url = make_url(raw)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise ValueError("Source must resolve to a SQLite path or sqlite URL")
    return Path(url.database).expanduser().resolve()


def _backup_paths(backup_dir: Path) -> BackupPaths:
    return BackupPaths(
        backup_dir=backup_dir,
        database_file=backup_dir / BACKUP_FILE_NAME,
        manifest_file=backup_dir / MANIFEST_FILE_NAME,
    )


def _connect_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0)


def _connect_rw(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(str(path), timeout=5.0)


def _collect_sqlite_checks(path: Path) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    with _connect_readonly(path) as conn:
        quick_check = conn.execute("PRAGMA quick_check").fetchall()
        integrity_check = conn.execute("PRAGMA integrity_check").fetchall()
        foreign_key_check = conn.execute("PRAGMA foreign_key_check").fetchall()
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]

    checks["quick_check"] = [row[0] for row in quick_check]
    checks["integrity_check"] = [row[0] for row in integrity_check]
    checks["foreign_key_check"] = [list(row) for row in foreign_key_check]
    checks["page_count"] = int(page_count)
    checks["page_size"] = int(page_size)
    checks["journal_mode"] = str(journal_mode)
    checks["size_bytes"] = path.stat().st_size
    return checks


def _read_alembic_revision(path: Path) -> list[str]:
    with _connect_readonly(path) as conn:
        try:
            rows = conn.execute("SELECT version_num FROM alembic_version").fetchall()
        except sqlite3.Error:
            return []
    return [row[0] for row in rows if row and row[0]]


def create_backup(
    source: Path,
    backup_dir: Path,
    *,
    release_id: str = "",
    git_sha: str = "",
    source_revision: str = "",
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    ensure_directories(backup_dir)
    paths = _backup_paths(backup_dir)
    if paths.database_file.exists():
        raise FileExistsError(paths.database_file)

    backup_id = f"{release_timestamp()}-{uuid.uuid4().hex[:8]}"
    tmp_database = backup_dir / f".{BACKUP_FILE_NAME}.tmp"
    if tmp_database.exists():
        tmp_database.unlink()

    with _connect_readonly(source) as source_conn, _connect_rw(tmp_database) as target_conn:
        source_conn.backup(target_conn)

    os.replace(tmp_database, paths.database_file)
    checks = _collect_sqlite_checks(paths.database_file)
    git_sha = git_sha or current_git_sha()
    source_revision = source_revision or ",".join(_read_alembic_revision(paths.database_file))

    manifest = {
        "backup_id": backup_id,
        "tool": "sqlite-backup",
        "tool_version": SCRIPT_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "source_database": str(source),
        "source_git_sha": git_sha,
        "source_release_id": release_id,
        "source_revision": source_revision,
        "database_file": str(paths.database_file),
        "sha256": sha256_file(paths.database_file),
        "checks": checks,
    }
    json_dump(paths.manifest_file, manifest)
    return manifest


def verify_backup(backup_dir: Path) -> dict[str, Any]:
    paths = _backup_paths(backup_dir)
    if not paths.manifest_file.is_file():
        raise FileNotFoundError(paths.manifest_file)
    if not paths.database_file.is_file():
        raise FileNotFoundError(paths.database_file)

    manifest = json_load(paths.manifest_file)
    actual_hash = sha256_file(paths.database_file)
    if manifest.get("sha256") != actual_hash:
        raise RuntimeError(
            f"SHA-256 mismatch for {paths.database_file}: expected {manifest.get('sha256')}, found {actual_hash}"
        )

    checks = _collect_sqlite_checks(paths.database_file)
    if not checks["quick_check"] or checks["quick_check"] != ["ok"]:
        raise RuntimeError(f"quick_check failed: {checks['quick_check']}")
    if not checks["integrity_check"] or checks["integrity_check"] != ["ok"]:
        raise RuntimeError(f"integrity_check failed: {checks['integrity_check']}")
    if checks["foreign_key_check"]:
        raise RuntimeError(f"foreign_key_check failed: {checks['foreign_key_check']}")

    manifest["verified_at"] = datetime.now(UTC).isoformat()
    manifest["verified_checks"] = checks
    json_dump(paths.manifest_file, manifest)
    return manifest


def restore_backup(backup_dir: Path, destination: Path, *, preserve_existing: bool = True) -> dict[str, Any]:
    paths = _backup_paths(backup_dir)
    if not paths.manifest_file.is_file():
        raise FileNotFoundError(paths.manifest_file)
    if not paths.database_file.is_file():
        raise FileNotFoundError(paths.database_file)

    manifest = verify_backup(backup_dir)
    destination = destination.expanduser().resolve()
    ensure_directories(destination.parent)

    if destination.exists() and preserve_existing:
        incident_id = f"incident-{release_timestamp()}-{uuid.uuid4().hex[:8]}"
        incident_path = destination.with_name(f"{destination.stem}.{incident_id}{destination.suffix}")
        os.replace(destination, incident_path)
        manifest["preserved_existing"] = str(incident_path)

    tmp_destination = destination.with_name(f".{destination.name}.tmp")
    if tmp_destination.exists():
        tmp_destination.unlink()
    shutil.copy2(paths.database_file, tmp_destination)
    os.replace(tmp_destination, destination)

    restored_checks = _collect_sqlite_checks(destination)
    if restored_checks["quick_check"] != ["ok"] or restored_checks["integrity_check"] != ["ok"]:
        raise RuntimeError(f"restored database failed checks: {restored_checks}")
    if restored_checks["foreign_key_check"]:
        raise RuntimeError(f"restored database has foreign key violations: {restored_checks['foreign_key_check']}")

    manifest["restored_at"] = datetime.now(UTC).isoformat()
    manifest["restored_database"] = str(destination)
    manifest["restored_checks"] = restored_checks
    json_dump(paths.manifest_file, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sqlite-backup", description="SQLite backup and restore operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a verified SQLite backup artifact.")
    create_parser.add_argument("--source", required=True, help="Source SQLite database path or sqlite URL.")
    create_parser.add_argument("--destination", required=True, help="Backup directory to create.")
    create_parser.add_argument("--release-id", default="", help="Source release ID to record.")
    create_parser.add_argument("--git-sha", default="", help="Source Git SHA to record.")
    create_parser.add_argument("--revision", default="", help="Source Alembic revision to record.")
    create_parser.set_defaults(handler=_handle_create)

    verify_parser = subparsers.add_parser("verify", help="Verify an existing backup artifact.")
    verify_parser.add_argument("--backup", required=True, help="Backup directory to verify.")
    verify_parser.set_defaults(handler=_handle_verify)

    restore_parser = subparsers.add_parser("restore", help="Restore a verified backup to a destination path.")
    restore_parser.add_argument("--backup", required=True, help="Backup directory to restore from.")
    restore_parser.add_argument("--destination", required=True, help="Destination SQLite database path.")
    preserve_group = restore_parser.add_mutually_exclusive_group()
    preserve_group.add_argument(
        "--preserve-existing",
        dest="preserve_existing",
        action="store_true",
        help="Preserve the current database as an incident artifact.",
    )
    preserve_group.add_argument(
        "--no-preserve-existing",
        dest="preserve_existing",
        action="store_false",
        help="Replace an existing destination without preserving it first.",
    )
    restore_parser.set_defaults(preserve_existing=True)
    restore_parser.set_defaults(handler=_handle_restore)

    return parser


def _handle_create(args: argparse.Namespace) -> int:
    validate_production_configuration()
    source = _resolve_sqlite_path(args.source)
    backup_dir = Path(args.destination).expanduser().resolve()
    manifest = create_backup(
        source,
        backup_dir,
        release_id=args.release_id,
        git_sha=args.git_sha,
        source_revision=args.revision,
    )
    print(json_dump_to_string(manifest))
    return 0


def _handle_verify(args: argparse.Namespace) -> int:
    validate_production_configuration()
    backup_dir = Path(args.backup).expanduser().resolve()
    manifest = verify_backup(backup_dir)
    print(json_dump_to_string(manifest))
    return 0


def _handle_restore(args: argparse.Namespace) -> int:
    validate_production_configuration()
    backup_dir = Path(args.backup).expanduser().resolve()
    destination = Path(args.destination).expanduser().resolve()
    manifest = restore_backup(backup_dir, destination, preserve_existing=args.preserve_existing)
    print(json_dump_to_string(manifest))
    return 0


def json_dump_to_string(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("No command selected")
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
