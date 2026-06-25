"""Release, rollback, and content-sync operations for Crowdcraft."""

from __future__ import annotations

import asyncio
import json
import os
import plistlib
import shutil
import subprocess
import sys
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select

from backend.config import get_settings
from backend.runtime.config import resolve_runtime_paths, validate_runtime_resources, validate_runtime_settings
from backend.runtime.host_scope import build_host_scope_map, host_scope_for_game
from backend.utils.model_registry import GameType

from scripts.ops.common import (
    current_git_sha,
    ensure_directories,
    file_lock,
    get_deployment_paths,
    json_dump,
    json_load,
    now_utc,
    release_timestamp,
    run_command,
    sha256_file,
    validate_production_configuration,
)
from scripts.ops.sqlite_backup import create_backup, restore_backup, verify_backup
from scripts.ops.smoke import run_smoke_sync


ROOT_DIR = Path(__file__).resolve().parents[2]
STATE_CREATED = "CREATED"
STATE_PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
STATE_VERIFIED = "VERIFIED"
STATE_SERVICE_QUIESCED = "SERVICE_QUIESCED"
STATE_BACKUP_VERIFIED = "BACKUP_VERIFIED"
STATE_DATABASE_MIGRATED = "DATABASE_MIGRATED"
STATE_CONTENT_SYNCED = "CONTENT_SYNCED"
STATE_STATIC_STAGED = "STATIC_STAGED"
STATE_STATIC_PUBLISHED = "STATIC_PUBLISHED"
STATE_SERVICE_READY = "SERVICE_READY"
STATE_SMOKE_PASSED = "SMOKE_PASSED"
STATE_COMPLETE = "COMPLETE"
STATE_FAILED = "FAILED"
SERVER_LAUNCHD_LABEL = "com.crowdcraft.server"
SERVER_LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{SERVER_LAUNCHD_LABEL}.plist"


@dataclass(frozen=True, slots=True)
class StaticPublication:
    release_id: str
    release_root: str
    current_pointer: str
    games: dict[str, Any]


@dataclass(frozen=True, slots=True)
class StaticStaging:
    release_id: str
    staging_root: str
    games: dict[str, Any]


def validate_config(*, require_runtime_resources: bool = True) -> dict[str, Any]:
    """Validate production runtime configuration and tool availability."""

    errors: list[str] = []
    paths_payload: dict[str, Any] = {}
    try:
        settings = get_settings()
        paths = resolve_runtime_paths(settings)
        paths_payload = {key: str(value) if isinstance(value, Path) else value for key, value in asdict(paths).items()}
        errors.extend(validate_runtime_settings(settings))
        if require_runtime_resources:
            errors.extend(validate_runtime_resources(settings))
    except Exception as exc:
        errors.append(f"configuration validation failed: {exc}")

    tool_checks = {
        "git": shutil.which("git") is not None,
        "python": shutil.which("python3") is not None or shutil.which("python") is not None,
        "npm": shutil.which("npm") is not None,
        "cloudflared": shutil.which("cloudflared") is not None,
        "launchctl": shutil.which("launchctl") is not None,
    }

    return {
        "ok": not errors,
        "errors": errors,
        "paths": paths_payload,
        "tool_checks": tool_checks,
    }


async def snapshot_content_state() -> dict[str, Any]:
    from backend.database import AsyncSessionLocal
    from backend.models.mm.caption import MMCaption
    from backend.models.mm.image import MMImage
    from backend.models.player import Player
    from backend.models.qf.prompt import Prompt
    from backend.models.qf.quest import QFQuest
    from backend.models.tl import TLAnswer, TLPrompt
    from backend.scripts.mm.import_images import SEED_CAPTIONS, find_image_files
    from backend.scripts.tl.seed_answers import load_completions_from_csv
    from backend.scripts.tl.seed_prompts import load_prompts_from_csv as load_tl_prompts
    from backend.services.qf.prompt_seeder import load_prompts_from_csv as load_qf_prompts
    from backend.services.qf.quest_service import QuestService

    qf_prompts_source = len(load_qf_prompts())
    tl_prompts_source = len(load_tl_prompts())
    tl_answers_source = sum(len(completions) for completions in load_completions_from_csv().values())
    image_files = find_image_files()
    mm_images_source = len(image_files)
    mm_captions_source = len(SEED_CAPTIONS) * mm_images_source
    starter_quest_types = {quest_type.value for quest_type in QuestService.STARTER_QUEST_TYPES}

    async with AsyncSessionLocal() as db:
        counts = {
            "players": await db.scalar(select(func.count(Player.player_id))),
            "qf_prompts": await db.scalar(select(func.count(Prompt.prompt_id))),
            "qf_quests": await db.scalar(
                select(func.count(QFQuest.quest_id)).where(QFQuest.quest_type.in_(starter_quest_types))
            ),
            "mm_images": await db.scalar(select(func.count(MMImage.image_id))),
            "mm_captions": await db.scalar(select(func.count(MMCaption.caption_id))),
            "tl_prompts": await db.scalar(select(func.count(TLPrompt.prompt_id))),
            "tl_answers": await db.scalar(select(func.count(TLAnswer.answer_id))),
        }

    return {
        "source": {
            "qf_prompts": qf_prompts_source,
            "mm_images": mm_images_source,
            "mm_captions": mm_captions_source,
            "tl_prompts": tl_prompts_source,
            "tl_answers": tl_answers_source,
        },
        "database": counts,
    }


async def sync_content(*, apply: bool, release_id: str) -> dict[str, Any]:
    report = await snapshot_content_state()
    report["release_id"] = release_id
    report["applied"] = apply
    if apply:
        from backend.main import run_release_sync_content

        await run_release_sync_content()
        report["applied"] = True
    return report


def cleanup_retention(*, apply: bool, command_id: str) -> dict[str, Any]:
    paths = get_deployment_paths()
    backup_root = paths.runtime_root / "backups"
    backup_dirs = (
        sorted(
            [path for path in backup_root.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if backup_root.exists()
        else []
    )

    return {
        "command_id": command_id,
        "apply": apply,
        "backup_root": str(backup_root),
        "backup_count": len(backup_dirs),
        "backups": [str(path) for path in backup_dirs],
        "deleted": [],
        "note": "Retention policy is not yet encoded; this command currently reports backup inventory only.",
    }


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _state_event(state: str, **payload: Any) -> dict[str, Any]:
    event = {"state": state, "timestamp": now_utc()}
    event.update(payload)
    return event


def _release_dirs(paths: Any, release_id: str) -> dict[str, Path]:
    runtime_root = paths.runtime_root
    static_root = runtime_root / "static"
    return {
        "runtime_root": runtime_root,
        "releases_root": runtime_root / "releases",
        "backups_root": runtime_root / "backups",
        "locks_root": runtime_root / "locks",
        "static_root": static_root,
        "staging_root": static_root / "staging" / release_id,
        "published_root": static_root / "releases" / release_id,
        "current_pointer": static_root / "current",
        "release_record_path": runtime_root / "releases" / f"{release_id}.json",
    }


def _current_static_release_id(current_pointer: Path) -> str:
    if not current_pointer.exists() and not current_pointer.is_symlink():
        return ""

    try:
        resolved = current_pointer.resolve(strict=False)
    except Exception:
        return ""

    parts = resolved.parts
    if "releases" not in parts:
        return ""

    release_index = parts.index("releases") + 1
    if release_index >= len(parts):
        return ""

    return parts[release_index]


def _read_release_record(release_record_path: Path) -> dict[str, Any]:
    if not release_record_path.is_file():
        raise FileNotFoundError(release_record_path)
    return json_load(release_record_path)


def _write_release_record(release_record_path: Path, payload: dict[str, Any]) -> None:
    ensure_directories(release_record_path.parent)
    json_dump(release_record_path, payload)


def _append_release_event(
    release_record_path: Path,
    release_record: dict[str, Any],
    state: str,
    **payload: Any,
) -> None:
    timeline = list(release_record.get("timeline", []))
    event = _state_event(state, **payload)
    timeline.append(event)
    release_record["timeline"] = timeline
    release_record["current_state"] = state
    release_record["updated_at"] = event["timestamp"]
    release_record.setdefault("state_history", []).append(state)
    release_record.update(payload)
    _write_release_record(release_record_path, release_record)


def _truncated_completed_process(result: subprocess.CompletedProcess[str], limit: int = 2000) -> dict[str, Any]:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return {
        "returncode": result.returncode,
        "stdout": stdout[:limit],
        "stderr": stderr[:limit],
        "stdout_truncated": len(stdout) > limit,
        "stderr_truncated": len(stderr) > limit,
    }


def _frontend_dist_roots() -> dict[GameType, Path]:
    return {
        GameType.QF: ROOT_DIR / "frontend" / "qf" / "dist",
        GameType.MM: ROOT_DIR / "frontend" / "mm" / "dist",
        GameType.IR: ROOT_DIR / "frontend" / "ir" / "dist",
        GameType.TL: ROOT_DIR / "frontend" / "tl" / "dist",
    }


def _hash_tree(root: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        files.append(
            {
                "path": str(path.relative_to(root)),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return files


def _stage_static_release(paths: Any, release_id: str) -> StaticStaging:
    runtime_paths = _release_dirs(paths, release_id)
    staging_root = runtime_paths["staging_root"]
    published_root = runtime_paths["published_root"]

    ensure_directories(staging_root.parent, published_root.parent)
    if staging_root.exists():
        shutil.rmtree(staging_root)
    if published_root.exists():
        raise FileExistsError(published_root)

    games_payload: dict[str, Any] = {}
    for game, source_root in _frontend_dist_roots().items():
        if not source_root.is_dir():
            raise FileNotFoundError(source_root)
        destination = staging_root / game.value
        shutil.copytree(source_root, destination)
        index_html = destination / "index.html"
        if not index_html.is_file():
            raise FileNotFoundError(index_html)
        games_payload[game.value] = {
            "source": str(source_root),
            "destination": str(destination),
            "index_sha256": sha256_file(index_html),
            "files": _hash_tree(destination),
        }

    return StaticStaging(
        release_id=release_id,
        staging_root=str(staging_root),
        games=games_payload,
    )


def _publish_staged_static_release(
    paths: Any,
    release_id: str,
    staging_root: Path,
    games_payload: dict[str, Any],
) -> StaticPublication:
    runtime_paths = _release_dirs(paths, release_id)
    published_root = runtime_paths["published_root"]
    current_pointer = runtime_paths["current_pointer"]

    ensure_directories(published_root.parent, current_pointer.parent)
    if published_root.exists():
        raise FileExistsError(published_root)

    os.replace(staging_root, published_root)

    tmp_pointer = current_pointer.with_name(f".current.{release_id}.tmp")
    if tmp_pointer.exists() or tmp_pointer.is_symlink():
        tmp_pointer.unlink()
    tmp_pointer.symlink_to(published_root, target_is_directory=True)
    os.replace(tmp_pointer, current_pointer)

    return StaticPublication(
        release_id=release_id,
        release_root=str(published_root),
        current_pointer=str(current_pointer),
        games=games_payload,
    )


def _rollback_static_release(paths: Any, release_record: dict[str, Any]) -> dict[str, Any]:
    runtime_paths = _release_dirs(paths, str(release_record["release_id"]))
    current_pointer = runtime_paths["current_pointer"]
    previous_release_id = str(release_record.get("previous_static_release_id") or "")
    if not previous_release_id:
        return {
            "restored_static": False,
            "reason": "no previous static release recorded",
        }

    previous_release_root = runtime_paths["static_root"] / "releases" / previous_release_id
    if not previous_release_root.is_dir():
        raise FileNotFoundError(previous_release_root)

    tmp_pointer = current_pointer.with_name(f".current.rollback.{release_record['release_id']}.tmp")
    if tmp_pointer.exists() or tmp_pointer.is_symlink():
        tmp_pointer.unlink()
    tmp_pointer.symlink_to(previous_release_root, target_is_directory=True)
    os.replace(tmp_pointer, current_pointer)

    return {
        "restored_static": True,
        "restored_release_id": previous_release_id,
        "restored_root": str(previous_release_root),
    }


def _run_verify_gate() -> dict[str, Any]:
    settings = get_settings()
    verify_env = os.environ.copy()
    for field_name in settings.__class__.model_fields:
        verify_env.pop(field_name.upper(), None)
    verify_env["ENVIRONMENT"] = "development"

    result = run_command(
        [sys.executable, "scripts/verify.py", "verify"],
        cwd=ROOT_DIR,
        env=verify_env,
        stream=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "verification failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return _truncated_completed_process(result)


def _run_smoke_gate(base_url: str = "http://127.0.0.1:8000") -> dict[str, Any]:
    report = run_smoke_sync(base_url=base_url)
    return {
        "base_url": base_url,
        "ok": report["ok"],
        "case_count": len(report["cases"]),
        "results": report["results"],
    }


def _launchctl_target() -> str:
    uid = os.getuid() if hasattr(os, "getuid") else 0
    return f"gui/{uid}"


def _run_launchctl(command: str) -> dict[str, Any]:
    args = ["launchctl", command]
    if command == "bootout":
        args.extend([_launchctl_target(), str(SERVER_LAUNCH_AGENT_PATH)])
    elif command == "bootstrap":
        args.extend([_launchctl_target(), str(SERVER_LAUNCH_AGENT_PATH)])
    else:
        raise ValueError(f"Unsupported launchctl command: {command}")

    result = run_command(args, cwd=ROOT_DIR, check=False)
    if command == "bootout" and result.returncode != 0:
        diagnostics = f"{result.stdout}\n{result.stderr}".lower()
        if (
            "could not find service" in diagnostics
            or "no such process" in diagnostics
            or "input/output error" in diagnostics
            or "i/o error" in diagnostics
        ):
            return {
                **_truncated_completed_process(result),
                "already_stopped": True,
            }
    if result.returncode != 0:
        raise RuntimeError(
            f"launchctl {command} failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return _truncated_completed_process(result)


def _update_server_launch_agent(*, release_id: str, expected_revision: str) -> dict[str, Any]:
    if not SERVER_LAUNCH_AGENT_PATH.is_file():
        raise FileNotFoundError(SERVER_LAUNCH_AGENT_PATH)

    with SERVER_LAUNCH_AGENT_PATH.open("rb") as handle:
        payload = plistlib.load(handle)

    environment = payload.setdefault("EnvironmentVariables", {})
    environment["CROWDCRAFT_RELEASE_ID"] = release_id
    environment["CROWDCRAFT_EXPECTED_REVISION"] = expected_revision

    temporary_path = SERVER_LAUNCH_AGENT_PATH.with_suffix(".plist.tmp")
    with temporary_path.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=False)
    os.chmod(temporary_path, 0o644)
    os.replace(temporary_path, SERVER_LAUNCH_AGENT_PATH)

    return {
        "path": str(SERVER_LAUNCH_AGENT_PATH),
        "release_id": release_id,
        "expected_revision": expected_revision,
    }


def load_server_launch_agent_environment() -> dict[str, str]:
    if not SERVER_LAUNCH_AGENT_PATH.is_file():
        raise FileNotFoundError(SERVER_LAUNCH_AGENT_PATH)

    with SERVER_LAUNCH_AGENT_PATH.open("rb") as handle:
        payload = plistlib.load(handle)

    raw_environment = payload.get("EnvironmentVariables", {})
    if not isinstance(raw_environment, dict):
        raise RuntimeError(f"Invalid EnvironmentVariables in {SERVER_LAUNCH_AGENT_PATH}")

    environment = {
        str(key): str(value)
        for key, value in raw_environment.items()
        if isinstance(key, str) and isinstance(value, (str, int, float, bool))
    }
    if not environment:
        raise RuntimeError(f"No EnvironmentVariables found in {SERVER_LAUNCH_AGENT_PATH}")
    return environment


def current_alembic_head() -> str:
    result = run_command([sys.executable, "-m", "alembic", "heads"], cwd=ROOT_DIR)
    heads = [
        line.split()[0]
        for line in result.stdout.splitlines()
        if line.strip().endswith("(head)")
    ]
    if len(heads) != 1:
        raise RuntimeError(f"Expected exactly one Alembic head, found {heads or 'none'}")
    return heads[0]


def _wait_for_listener_closed(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 1.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    last_connect_ex = 0

    while True:
        attempts += 1
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            last_connect_ex = sock.connect_ex((host, port))
        if last_connect_ex != 0:
            return {
                "ok": True,
                "host": host,
                "port": port,
                "attempts": attempts,
                "status": "closed",
                "last_connect_ex": last_connect_ex,
            }

        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"listener on {host}:{port} did not close after {attempts} attempts"
            )
        time.sleep(poll_interval_seconds)


async def _wait_for_endpoint(
    path: str,
    *,
    host_header: str,
    base_url: str = "http://127.0.0.1:8000",
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 1.0,
) -> dict[str, Any]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    attempts = 0
    last_result: dict[str, Any] = {}

    async with httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(5.0, connect=2.0), follow_redirects=True) as client:
        while True:
            attempts += 1
            try:
                response = await client.get(path, headers={"Host": host_header, "Accept": "application/json"})
                last_result = {
                    "status_code": response.status_code,
                    "content_type": response.headers.get("content-type", ""),
                    "body_prefix": response.text[:200] if response.text else "",
                }
                if response.status_code == 200:
                    return {
                        "ok": True,
                        "base_url": base_url,
                        "path": path,
                        "host": host_header,
                        "attempts": attempts,
                        "response": last_result,
                    }
            except Exception as exc:  # pragma: no cover - defensive poll loop
                last_result = {
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc)[:200],
                }

            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(
                    f"{path} did not become ready for host {host_header!r} at {base_url} "
                    f"after {attempts} attempts: {last_result}"
                )
            await asyncio.sleep(poll_interval_seconds)


async def _wait_for_livez(host_header: str, *, base_url: str = "http://127.0.0.1:8000") -> dict[str, Any]:
    return await _wait_for_endpoint("/livez", host_header=host_header, base_url=base_url)


async def _wait_for_readyz(host_header: str, *, base_url: str = "http://127.0.0.1:8000") -> dict[str, Any]:
    return await _wait_for_endpoint("/readyz", host_header=host_header, base_url=base_url)


def _primary_host_header(settings: Any) -> str:
    host_scope = host_scope_for_game(GameType.QF, build_host_scope_map(settings))
    if host_scope is None:
        raise RuntimeError("QF host is not configured")
    return host_scope.hostname


def run_release(
    *,
    revision: str,
    release_id: str = "",
    apply: bool = False,
    run_smoke: bool = True,
) -> dict[str, Any]:
    """Run a guarded release workflow, optionally mutating production state."""

    validation = validate_config(require_runtime_resources=False)
    if not validation["ok"]:
        return {
            "ok": False,
            "apply": apply,
            "release_id": release_id,
            "revision": revision,
            "validation": validation,
            "state": STATE_FAILED,
            "errors": validation["errors"],
        }

    settings = get_settings()
    paths = resolve_runtime_paths(settings)
    runtime_dirs = _release_dirs(paths, release_id or f"{release_timestamp()}-{revision[:8]}")
    release_id = runtime_dirs["release_record_path"].stem
    release_record_path = runtime_dirs["release_record_path"]
    lock_path = runtime_dirs["locks_root"] / "release.lock"

    planned_states = [
        STATE_CREATED,
        STATE_PREFLIGHT_PASSED,
        STATE_VERIFIED,
        STATE_STATIC_STAGED,
        STATE_SERVICE_QUIESCED,
        STATE_BACKUP_VERIFIED,
        STATE_DATABASE_MIGRATED,
        STATE_CONTENT_SYNCED,
        STATE_STATIC_PUBLISHED,
        STATE_SERVICE_READY,
        STATE_SMOKE_PASSED,
        STATE_COMPLETE,
    ]

    if not apply:
        return {
            "ok": True,
            "apply": False,
            "release_id": release_id,
            "revision": revision,
            "validation": validation,
            "planned_states": planned_states,
            "current_static_release_id": _current_static_release_id(runtime_dirs["current_pointer"]),
        }

    ensure_directories(
        runtime_dirs["releases_root"],
        runtime_dirs["backups_root"],
        runtime_dirs["locks_root"],
        runtime_dirs["static_root"],
        runtime_dirs["static_root"] / "releases",
        runtime_dirs["static_root"] / "staging",
    )
    if release_record_path.exists():
        raise FileExistsError(release_record_path)

    release_record: dict[str, Any] = {
        "release_id": release_id,
        "git_sha": revision,
        "created_at": now_utc(),
        "updated_at": now_utc(),
        "status": "running",
        "current_state": STATE_CREATED,
        "state_history": [STATE_CREATED],
        "timeline": [_state_event(STATE_CREATED)],
        "runtime_root": str(paths.runtime_root),
        "static_root": str(paths.static_root),
        "database_path": str(paths.database_path) if paths.database_path else "",
        "expected_revision": paths.expected_revision,
        "current_static_release_id": _current_static_release_id(runtime_dirs["current_pointer"]),
        "previous_static_release_id": _current_static_release_id(runtime_dirs["current_pointer"]),
        "validation": validation,
    }
    _write_release_record(release_record_path, release_record)

    try:
        with file_lock(lock_path):
            _append_release_event(release_record_path, release_record, STATE_PREFLIGHT_PASSED)

            verify_summary = _run_verify_gate()
            release_record["verify"] = verify_summary
            _append_release_event(release_record_path, release_record, STATE_VERIFIED)

            static_staging = _stage_static_release(paths, release_id)
            release_record["static_staging"] = asdict(static_staging)
            _append_release_event(release_record_path, release_record, STATE_STATIC_STAGED)

            service_quiesce = _run_launchctl("bootout")
            release_record["service_quiesce"] = service_quiesce
            release_record["listener_closed"] = _wait_for_listener_closed()
            _append_release_event(release_record_path, release_record, STATE_SERVICE_QUIESCED)

            if paths.database_path is None:
                raise RuntimeError("DATABASE_URL does not resolve to a SQLite database path")

            if paths.database_path.is_file():
                backup_dir = runtime_dirs["backups_root"] / release_id
                backup_manifest = create_backup(
                    paths.database_path,
                    backup_dir,
                    release_id=release_id,
                    git_sha=revision,
                )
                verified_backup = verify_backup(backup_dir)
                release_record["backup"] = {
                    "backup_dir": str(backup_dir),
                    "manifest": backup_manifest,
                    "verified_manifest": verified_backup,
                }
            else:
                ensure_directories(paths.database_path.parent)
                release_record["backup"] = {
                    "skipped": True,
                    "reason": "initial deployment: database does not exist",
                }
            _append_release_event(release_record_path, release_record, STATE_BACKUP_VERIFIED)

            alembic_result = run_command([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT_DIR)
            if alembic_result.returncode != 0:
                raise RuntimeError(
                    "alembic upgrade head failed:\n"
                    f"stdout:\n{alembic_result.stdout}\n"
                    f"stderr:\n{alembic_result.stderr}"
                )
            release_record["alembic"] = _truncated_completed_process(alembic_result)
            _append_release_event(release_record_path, release_record, STATE_DATABASE_MIGRATED)

            content_report = asyncio.run(sync_content(apply=True, release_id=release_id))
            release_record["content"] = content_report
            _append_release_event(release_record_path, release_record, STATE_CONTENT_SYNCED)

            static_publication = _publish_staged_static_release(
                paths, release_id, Path(static_staging.staging_root), static_staging.games
            )
            release_record["static_publication"] = asdict(static_publication)
            _append_release_event(release_record_path, release_record, STATE_STATIC_PUBLISHED)

            release_record["launch_agent"] = _update_server_launch_agent(
                release_id=release_id,
                expected_revision=paths.expected_revision,
            )
            service_restart = _run_launchctl("bootstrap")
            release_record["service_restart"] = service_restart
            host_header = _primary_host_header(settings)
            livez_report = asyncio.run(_wait_for_livez(host_header))
            readyz_report = asyncio.run(_wait_for_readyz(host_header))
            release_record["livez"] = livez_report
            release_record["readyz"] = readyz_report
            _append_release_event(release_record_path, release_record, STATE_SERVICE_READY)

            if run_smoke:
                smoke_report = _run_smoke_gate()
                release_record["smoke"] = smoke_report
                _append_release_event(release_record_path, release_record, STATE_SMOKE_PASSED)

            release_record["status"] = "complete"
            release_record["current_state"] = STATE_COMPLETE
            release_record["updated_at"] = now_utc()
            release_record["state_history"].append(STATE_COMPLETE)
            release_record["timeline"].append(_state_event(STATE_COMPLETE))
            _write_release_record(release_record_path, release_record)

    except Exception as exc:
        release_record["status"] = "failed"
        release_record["failed_state"] = release_record.get("current_state", STATE_FAILED)
        release_record["failure"] = {
            "type": exc.__class__.__name__,
            "message": str(exc),
        }
        release_record["updated_at"] = now_utc()
        release_record["timeline"].append(
            _state_event(
                STATE_FAILED,
                failed_state=release_record["failed_state"],
                error_type=exc.__class__.__name__,
                error_message=str(exc),
            )
        )
        _write_release_record(release_record_path, release_record)
        raise

    return release_record


def run_rollback(
    *,
    release_id: str,
    apply: bool = False,
) -> dict[str, Any]:
    """Restore the recorded release artifacts to the previous known-good state."""

    validation = validate_config()
    if not validation["ok"]:
        return {
            "ok": False,
            "apply": apply,
            "release_id": release_id,
            "validation": validation,
            "errors": validation["errors"],
        }

    settings = get_settings()
    paths = resolve_runtime_paths(settings)
    runtime_dirs = _release_dirs(paths, release_id)
    release_record_path = runtime_dirs["release_record_path"]
    lock_path = runtime_dirs["locks_root"] / "release.lock"
    release_record = _read_release_record(release_record_path)

    backup_info = release_record.get("backup", {})
    backup_dir_raw = str(backup_info.get("backup_dir", "") or "").strip()
    if not backup_dir_raw:
        raise RuntimeError("release record is missing backup metadata")
    backup_dir = Path(backup_dir_raw).expanduser().resolve()

    rollback_plan = {
        "ok": True,
        "apply": apply,
        "release_id": release_id,
        "validation": validation,
        "backup_dir": str(backup_dir),
        "current_static_release_id": _current_static_release_id(runtime_dirs["current_pointer"]),
        "previous_static_release_id": release_record.get("previous_static_release_id", ""),
    }

    if not apply:
        rollback_plan["planned_actions"] = [
            "quiesce_service",
            "restore_backup",
            "restore_static_pointer",
            "restart_service",
            "wait_for_livez",
            "wait_for_readyz",
            "run_smoke",
            "record_rollback",
        ]
        return rollback_plan

    ensure_directories(runtime_dirs["releases_root"], runtime_dirs["locks_root"], runtime_dirs["static_root"])

    with file_lock(lock_path):
        if paths.database_path is None:
            raise RuntimeError("DATABASE_URL does not resolve to a SQLite database path")

        rollback_plan["service_quiesce"] = _run_launchctl("bootout")
        rollback_plan["listener_closed"] = _wait_for_listener_closed()

        restore_manifest = restore_backup(backup_dir, paths.database_path, preserve_existing=True)
        rollback_plan["restore"] = restore_manifest

        static_restore = _rollback_static_release(paths, release_record)
        rollback_plan["static_restore"] = static_restore

        previous_release_id = str(release_record.get("previous_static_release_id") or "")
        backup_manifest = backup_info.get("manifest", {})
        previous_revision = str(backup_manifest.get("source_revision") or "")
        if not previous_release_id or not previous_revision:
            raise RuntimeError("release record is missing rollback release or revision metadata")
        rollback_plan["launch_agent"] = _update_server_launch_agent(
            release_id=previous_release_id,
            expected_revision=previous_revision,
        )
        rollback_plan["service_restart"] = _run_launchctl("bootstrap")
        host_header = _primary_host_header(settings)
        rollback_plan["livez"] = asyncio.run(_wait_for_livez(host_header))
        rollback_plan["readyz"] = asyncio.run(_wait_for_readyz(host_header))
        rollback_plan["smoke"] = _run_smoke_gate()

        release_record["rollback"] = {
            "restored_at": now_utc(),
            "restore": restore_manifest,
            "static_restore": static_restore,
            "service_quiesce": rollback_plan["service_quiesce"],
            "service_restart": rollback_plan["service_restart"],
            "livez": rollback_plan["livez"],
            "readyz": rollback_plan["readyz"],
            "smoke": rollback_plan["smoke"],
        }
        release_record["status"] = "rolled_back"
        release_record["current_state"] = "ROLLED_BACK"
        release_record["updated_at"] = now_utc()
        release_record.setdefault("state_history", []).append("ROLLED_BACK")
        release_record.setdefault("timeline", []).append(_state_event("ROLLED_BACK"))
        _write_release_record(release_record_path, release_record)

    rollback_plan["release_record"] = release_record
    return rollback_plan


def run_sync_content(apply: bool, release_id: str) -> dict[str, Any]:
    return asyncio.run(sync_content(apply=apply, release_id=release_id))


def run_deploy_release(*, revision: str, release_id: str = "", apply: bool = False, run_smoke: bool = True) -> dict[str, Any]:
    return run_release(revision=revision, release_id=release_id, apply=apply, run_smoke=run_smoke)


def run_deploy_rollback(*, release_id: str, apply: bool = False) -> dict[str, Any]:
    return run_rollback(release_id=release_id, apply=apply)
