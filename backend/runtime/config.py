"""Runtime configuration helpers for production deployment checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.engine.url import make_url


DEFAULT_RUNTIME_ROOT = Path.home() / "Library" / "Application Support" / "Crowdcraft"
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / "Crowdcraft"
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Resolved runtime paths and release metadata."""

    runtime_root: Path
    static_root: Path
    log_dir: Path
    database_path: Path | None
    release_id: str
    expected_revision: str
    workers: int
    trust_proxy: bool


def _resolve_sqlite_database_path(database_url: str) -> Path | None:
    if not database_url:
        return None

    try:
        parsed = make_url(database_url)
    except Exception:
        return None

    if not parsed.drivername.startswith("sqlite") or not parsed.database:
        return None

    return Path(parsed.database).expanduser()


def resolve_runtime_paths(settings: Any) -> RuntimePaths:
    """Resolve filesystem paths from a settings object."""

    runtime_root_raw = getattr(settings, "crowdcraft_runtime_root", "") or str(DEFAULT_RUNTIME_ROOT)
    runtime_root = Path(runtime_root_raw).expanduser()

    static_root_raw = getattr(settings, "crowdcraft_static_root", "")
    static_root = Path(static_root_raw).expanduser() if static_root_raw else runtime_root / "static" / "current"

    log_dir_raw = getattr(settings, "crowdcraft_log_dir", "") or str(DEFAULT_LOG_DIR)
    log_dir = Path(log_dir_raw).expanduser()

    database_path = _resolve_sqlite_database_path(getattr(settings, "database_url", ""))
    release_id = str(getattr(settings, "crowdcraft_release_id", "") or "")
    expected_revision = str(getattr(settings, "crowdcraft_expected_revision", "") or "")
    workers_raw = getattr(settings, "crowdcraft_workers", 1)
    workers = int(workers_raw) if workers_raw is not None else 1
    trust_proxy = bool(getattr(settings, "crowdcraft_trust_proxy", False))

    return RuntimePaths(
        runtime_root=runtime_root,
        static_root=static_root,
        log_dir=log_dir,
        database_path=database_path,
        release_id=release_id,
        expected_revision=expected_revision,
        workers=workers,
        trust_proxy=trust_proxy,
    )


def validate_runtime_settings(settings: Any) -> list[str]:
    """Return human-readable production runtime validation failures."""

    if getattr(settings, "environment", "") != "production":
        return []

    paths = resolve_runtime_paths(settings)
    errors: list[str] = []

    secret_key = str(getattr(settings, "secret_key", "") or "")
    if not secret_key or secret_key == "dev-secret-key-change-in-production":
        errors.append("SECRET_KEY must be configured and not use the development default in production")

    if paths.workers != 1:
        errors.append("CROWDCRAFT_WORKERS must be exactly 1 in production")

    if not paths.trust_proxy:
        errors.append("CROWDCRAFT_TRUST_PROXY must be true in production")

    if not paths.runtime_root.is_absolute():
        errors.append("CROWDCRAFT_RUNTIME_ROOT must be an absolute path in production")

    if not paths.log_dir.is_absolute():
        errors.append("CROWDCRAFT_LOG_DIR must be an absolute path in production")

    if paths.database_path is None:
        errors.append("DATABASE_URL must point to SQLite in production")
    else:
        database_path = paths.database_path.expanduser().resolve(strict=False)
        if not paths.database_path.is_absolute():
            errors.append("DATABASE_URL must resolve to an absolute SQLite path in production")
        try:
            database_path.relative_to(REPO_ROOT)
        except ValueError:
            pass
        else:
            errors.append("DATABASE_URL must point outside the repository in production")

    if not paths.release_id:
        errors.append("CROWDCRAFT_RELEASE_ID must be configured in production")

    if not paths.expected_revision:
        errors.append("CROWDCRAFT_EXPECTED_REVISION must be configured in production")

    if not paths.static_root.is_absolute():
        errors.append("CROWDCRAFT_STATIC_ROOT must resolve to an absolute path in production")
    elif not paths.static_root.exists():
        errors.append(f"Static root does not exist: {paths.static_root}")
    elif not paths.static_root.is_dir():
        errors.append(f"Static root is not a directory: {paths.static_root}")
    else:
        for game in ("qf", "mm", "ir", "tl"):
            index_html = paths.static_root / game / "index.html"
            if not index_html.is_file():
                errors.append(f"Missing built SPA for {game}: {index_html}")

    return errors
