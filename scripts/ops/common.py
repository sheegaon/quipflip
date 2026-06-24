"""Shared helpers for Crowdcraft deployment operations."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from backend.config import get_settings
from backend.runtime.config import resolve_runtime_paths, validate_runtime_resources, validate_runtime_settings


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_VERSION = "0.1"


@dataclass(frozen=True, slots=True)
class DeploymentPaths:
    runtime_root: Path
    static_root: Path
    log_dir: Path
    database_path: Path | None
    release_id: str
    expected_revision: str
    workers: int
    trust_proxy: bool


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def get_deployment_paths() -> DeploymentPaths:
    settings = get_settings()
    paths = resolve_runtime_paths(settings)
    return DeploymentPaths(
        runtime_root=paths.runtime_root,
        static_root=paths.static_root,
        log_dir=paths.log_dir,
        database_path=paths.database_path,
        release_id=paths.release_id,
        expected_revision=paths.expected_revision,
        workers=paths.workers,
        trust_proxy=paths.trust_proxy,
    )


def validate_production_configuration() -> list[str]:
    settings = get_settings()
    return validate_runtime_settings(settings) + validate_runtime_resources(settings)


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd or ROOT_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


@contextmanager
def file_lock(lock_path: Path) -> Iterator[int]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle.fileno()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def current_git_sha() -> str:
    result = run_command(["git", "rev-parse", "HEAD"], cwd=ROOT_DIR)
    return result.stdout.strip()


def git_status_porcelain() -> list[str]:
    result = run_command(["git", "status", "--porcelain"], cwd=ROOT_DIR)
    return [line for line in result.stdout.splitlines() if line.strip()]


def release_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
