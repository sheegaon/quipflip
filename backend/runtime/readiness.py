"""Bounded readiness checks for deployment gates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.config import get_settings
from backend.runtime.config import resolve_runtime_paths, validate_runtime_settings
from backend.version import APP_VERSION


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    """A single readiness check and bounded diagnostic detail."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    """Structured readiness result returned by /readyz."""

    version: str
    environment: str
    release_id: str
    expected_revision: str
    checks: tuple[ReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.ok for check in self.checks)

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": "ok" if self.ready else "error",
            "version": self.version,
            "environment": self.environment,
            "release_id": self.release_id,
            "expected_revision": self.expected_revision,
            "checks": [
                {
                    "name": check.name,
                    "ok": check.ok,
                    "detail": check.detail,
                }
                for check in self.checks
            ],
        }


async def build_readiness_report(
    *,
    engine: AsyncEngine | None = None,
    settings: Any | None = None,
    static_root: Path | None = None,
) -> ReadinessReport:
    """Collect production readiness checks without mutating application state."""

    settings = settings or get_settings()
    paths = resolve_runtime_paths(settings)
    target_static_root = static_root or paths.static_root

    if engine is None:
        from backend.database import engine as default_engine

        engine = default_engine

    checks = [
        _runtime_config_check(settings),
        await _database_check(engine),
        await _alembic_revision_check(engine, paths.expected_revision),
        _static_assets_check(paths.runtime_root, target_static_root, paths.release_id),
    ]

    return ReadinessReport(
        version=APP_VERSION,
        environment=str(getattr(settings, "environment", "unknown")),
        release_id=paths.release_id,
        expected_revision=paths.expected_revision,
        checks=tuple(checks),
    )


def _runtime_config_check(settings: Any) -> ReadinessCheck:
    errors = validate_runtime_settings(settings)
    return ReadinessCheck(
        name="runtime_config",
        ok=not errors,
        detail="ok" if not errors else "; ".join(errors),
    )


async def _database_check(engine: AsyncEngine) -> ReadinessCheck:
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            if engine.dialect.name == "sqlite":
                pragma_errors = await _check_sqlite_pragmas(conn)
                if pragma_errors:
                    return ReadinessCheck(
                        name="database",
                        ok=False,
                        detail="; ".join(pragma_errors),
                    )
    except Exception as exc:  # pragma: no cover - exercised via failure tests
        return ReadinessCheck(
            name="database",
            ok=False,
            detail=f"database connection failed: {exc.__class__.__name__}",
        )

    return ReadinessCheck(name="database", ok=True, detail="database connection ok")


async def _check_sqlite_pragmas(conn: AsyncConnection) -> list[str]:
    errors: list[str] = []

    fk = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
    if fk != 1:
        errors.append(f"PRAGMA foreign_keys={fk!r}, expected 1")

    jm = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
    if (jm or "").lower() != "wal":
        errors.append(f"PRAGMA journal_mode={jm!r}, expected 'wal'")

    bt = (await conn.execute(text("PRAGMA busy_timeout"))).scalar()
    if (bt or 0) < 5000:
        errors.append(f"PRAGMA busy_timeout={bt!r}, expected >=5000")

    sync = (await conn.execute(text("PRAGMA synchronous"))).scalar()
    if sync != 2:
        errors.append(f"PRAGMA synchronous={sync!r}, expected 2 (FULL)")

    return errors


async def _alembic_revision_check(engine: AsyncEngine, expected_revision: str) -> ReadinessCheck:
    if not expected_revision:
        return ReadinessCheck(
            name="alembic_revision",
            ok=False,
            detail="expected Alembic revision is not configured",
        )

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            current_revisions = {
                version_num for version_num in result.scalars().all() if version_num
            }
    except Exception as exc:  # pragma: no cover - exercised via failure tests
        return ReadinessCheck(
            name="alembic_revision",
            ok=False,
            detail=f"could not read alembic_version: {exc.__class__.__name__}",
        )

    if current_revisions != {expected_revision}:
        found = ", ".join(sorted(current_revisions)) if current_revisions else "none"
        return ReadinessCheck(
            name="alembic_revision",
            ok=False,
            detail=f"expected {expected_revision}, found {found}",
        )

    return ReadinessCheck(
        name="alembic_revision",
        ok=True,
        detail=f"revision {expected_revision}",
    )


def _static_assets_check(runtime_root: Path, static_root: Path, release_id: str) -> ReadinessCheck:
    if not static_root.exists():
        return ReadinessCheck(
            name="static_assets",
            ok=False,
            detail=f"static root does not exist: {static_root}",
        )

    if not static_root.is_dir():
        return ReadinessCheck(
            name="static_assets",
            ok=False,
            detail=f"static root is not a directory: {static_root}",
        )

    if not release_id:
        return ReadinessCheck(
            name="static_assets",
            ok=False,
            detail="release id is not configured",
        )

    expected_static_root = runtime_root / "static" / "releases" / release_id
    resolved_static_root = static_root.resolve(strict=False)
    if resolved_static_root != expected_static_root:
        return ReadinessCheck(
            name="static_assets",
            ok=False,
            detail=f"active release {resolved_static_root} does not match expected {expected_static_root}",
        )

    release_record_path = runtime_root / "releases" / f"{release_id}.json"
    if not release_record_path.is_file():
        return ReadinessCheck(
            name="static_assets",
            ok=False,
            detail=f"missing release record: {release_record_path}",
        )

    try:
        release_record = json.loads(release_record_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exercised via failure tests
        return ReadinessCheck(
            name="static_assets",
            ok=False,
            detail=f"could not read release record: {exc.__class__.__name__}",
        )

    recorded_release_id = str(release_record.get("release_id", "") or "")
    if recorded_release_id != release_id:
        return ReadinessCheck(
            name="static_assets",
            ok=False,
            detail=(
                f"release record {release_record_path} reports {recorded_release_id or 'missing'}"
            ),
        )

    missing_games = [
        game
        for game in ("qf", "mm", "ir", "tl")
        if not (resolved_static_root / game / "index.html").is_file()
    ]

    if missing_games:
        return ReadinessCheck(
            name="static_assets",
            ok=False,
            detail=f"missing built SPAs in {resolved_static_root}: {', '.join(missing_games)}",
        )

    return ReadinessCheck(
        name="static_assets",
        ok=True,
        detail=f"active release {release_id} present under {resolved_static_root}",
    )
