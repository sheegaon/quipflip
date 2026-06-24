"""Runtime configuration helpers for production deployment checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.engine.url import make_url


DEFAULT_RUNTIME_ROOT = Path.home() / "Library" / "Application Support" / "Crowdcraft"
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / "Crowdcraft"
REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_HOST_SUFFIX = ".crowdcraftlabs.com"


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
    """Return production config failures that require no filesystem I/O.

    Safe to call during Settings initialisation and from CLI tools/migrations
    where built static assets may not yet be present.
    """

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

    frontend_url_fields = (
        ("QF_FRONTEND_URL", getattr(settings, "qf_frontend_url", "")),
        ("MM_FRONTEND_URL", getattr(settings, "mm_frontend_url", "")),
        ("IR_FRONTEND_URL", getattr(settings, "ir_frontend_url", "")),
        ("TL_FRONTEND_URL", getattr(settings, "tl_frontend_url", "")),
    )
    for env_name, raw_url in frontend_url_fields:
        errors.extend(_validate_frontend_url(env_name, str(raw_url or "")))

    return errors


def validate_runtime_resources(settings: Any) -> list[str]:
    """Return filesystem resource failures for production deployment gates.

    Checks that the active static release is present and complete. Separated
    from validate_runtime_settings so that offline tools and migrations can load
    Settings without failing when built SPAs are not yet deployed.

    Call this from the application lifespan (fail-closed startup) and from
    readiness checks, but NOT from Settings initialisation.
    """

    if getattr(settings, "environment", "") != "production":
        return []

    paths = resolve_runtime_paths(settings)
    errors: list[str] = []

    if not paths.static_root.is_absolute():
        return errors

    if not paths.static_root.exists():
        errors.append(f"Static root does not exist: {paths.static_root}")
    elif not paths.static_root.is_dir():
        errors.append(f"Static root is not a directory: {paths.static_root}")
    else:
        for game in ("qf", "mm", "ir", "tl"):
            index_html = paths.static_root / game / "index.html"
            if not index_html.is_file():
                errors.append(f"Missing built SPA for {game}: {index_html}")

    return errors


def _validate_frontend_url(env_name: str, raw_url: str) -> list[str]:
    """Validate a production frontend URL without leaking the configured value."""

    errors: list[str] = []
    if not raw_url:
        errors.append(f"{env_name} must be configured in production")
        return errors

    parsed = urlparse(raw_url)
    if parsed.scheme != "https":
        errors.append(f"{env_name} must use https in production")

    if parsed.username or parsed.password:
        errors.append(f"{env_name} must not include credentials in production")

    if parsed.query or parsed.fragment:
        errors.append(f"{env_name} must not include query strings or fragments in production")

    if parsed.path not in {"", "/"}:
        errors.append(f"{env_name} must not include a path in production")

    if parsed.port is not None:
        errors.append(f"{env_name} must not include a port in production")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        errors.append(f"{env_name} must include a hostname in production")
        return errors

    if hostname in {"localhost", "127.0.0.1", "::1"}:
        errors.append(f"{env_name} must not point at localhost in production")
    elif not hostname.endswith(PRODUCTION_HOST_SUFFIX):
        errors.append(
            f"{env_name} must end with {PRODUCTION_HOST_SUFFIX} in production"
        )

    return errors
