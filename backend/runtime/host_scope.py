"""Immutable host-scoped deployment helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.utils.model_registry import GameType


SUPPORTED_GAMES: tuple[GameType, ...] = (
    GameType.QF,
    GameType.MM,
    GameType.IR,
    GameType.TL,
)

GAME_PREFIXES: tuple[str, ...] = tuple(f"/{game.value}" for game in SUPPORTED_GAMES)
SHARED_HTTP_PREFIXES: tuple[str, ...] = (
    "/auth",
    "/health",
    "/livez",
    "/readyz",
    "/status",
    "/users",
    "/notifications",
    "/docs",
    "/redoc",
    "/openapi.json",
)


@dataclass(frozen=True, slots=True)
class HostScope:
    """Validated host metadata derived from the production host map."""

    hostname: str
    game: GameType
    api_prefix: str
    static_dir: str
    frontend_url: str


def _normalize_hostname(hostname: str | None) -> str | None:
    if hostname is None:
        return None

    value = hostname.strip().lower()
    if not value:
        return None

    if value.startswith("["):
        closing = value.find("]")
        if closing == -1:
            return None
        candidate = value[1:closing]
        remainder = value[closing + 1 :]
        if remainder and not remainder.startswith(":"):
            return None
        return candidate or None

    if value.count(":") > 1:
        return None

    if ":" in value:
        value = value.rsplit(":", 1)[0]

    return value or None


def _extract_hostname(raw_url: str | None) -> str | None:
    if raw_url is None:
        return None

    raw_value = str(raw_url).strip()
    if not raw_value:
        return None

    parsed = urlparse(raw_value if "://" in raw_value else f"//{raw_value}", scheme="https")
    hostname = parsed.hostname
    if hostname:
        return _normalize_hostname(hostname)

    return _normalize_hostname(raw_value.split("/", 1)[0])


def build_host_scope_map(settings: Any) -> dict[str, HostScope]:
    """Build the exact host -> game mapping from application settings."""

    host_settings: dict[GameType, str] = {
        GameType.QF: str(getattr(settings, "qf_frontend_url", "") or ""),
        GameType.MM: str(getattr(settings, "mm_frontend_url", "") or ""),
        GameType.IR: str(getattr(settings, "ir_frontend_url", "") or ""),
        GameType.TL: str(getattr(settings, "tl_frontend_url", "") or ""),
    }

    host_map: dict[str, HostScope] = {}
    for game, frontend_url in host_settings.items():
        hostname = _extract_hostname(frontend_url)
        if not hostname:
            continue

        host_map[hostname] = HostScope(
            hostname=hostname,
            game=game,
            api_prefix=f"/{game.value}",
            static_dir=game.value,
            frontend_url=frontend_url,
        )

    return host_map


def normalize_host_header(host_header: str | None) -> str | None:
    """Normalize a Host header to its bare hostname."""

    return _normalize_hostname(host_header)


def resolve_host_scope(host_header: str | None, host_map: dict[str, HostScope]) -> HostScope | None:
    """Resolve a normalized host header through the immutable host map."""

    normalized = normalize_host_header(host_header)
    if not normalized:
        return None

    return host_map.get(normalized)


def host_scope_for_game(game: GameType, host_map: dict[str, HostScope]) -> HostScope | None:
    """Return the first configured host scope for the requested game."""

    for scope in host_map.values():
        if scope.game == game:
            return scope
    return None


def game_from_path(path: str) -> GameType | None:
    """Return the game selected by an API path prefix, if any."""

    normalized = path or "/"
    for game in SUPPORTED_GAMES:
        prefix = f"/{game.value}"
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return game
    return None


def is_shared_route(path: str) -> bool:
    """True when the path belongs to a shared route surface."""

    normalized = path or "/"
    return any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in SHARED_HTTP_PREFIXES
    )


def is_reserved_api_path(path: str) -> bool:
    """True when the path should never fall back to SPA HTML."""

    return is_shared_route(path) or game_from_path(path) is not None


def static_release_dir(static_root: Path, host_scope: HostScope) -> Path:
    """Return the host-specific static release directory."""

    return static_root / host_scope.static_dir


def safe_static_candidate(static_dir: Path, request_path: str) -> Path | None:
    """Resolve a request path beneath a static directory, rejecting escapes."""

    requested = request_path.lstrip("/")
    candidate = (static_dir / requested).resolve(strict=False)
    root = static_dir.resolve(strict=False)

    try:
        candidate.relative_to(root)
    except ValueError:
        return None

    return candidate
