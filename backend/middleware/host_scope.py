"""Exact-host ASGI boundary and production static SPA fallback."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path
from typing import Any

from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import Headers

from backend.runtime.config import resolve_runtime_paths
from backend.runtime.host_scope import (
    HostScope,
    build_host_scope_map,
    game_from_path,
    is_reserved_api_path,
    normalize_host_header,
    safe_static_candidate,
    static_release_dir,
    resolve_host_scope,
)


logger = logging.getLogger(__name__)

_ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
_INDEX_CACHE_CONTROL = "no-cache, max-age=0, must-revalidate"
_NO_STORE_CACHE_CONTROL = "no-store"


def _hash_host(hostname: str | None) -> str:
    if not hostname:
        return "<missing>"
    return hashlib.sha256(hostname.encode("utf-8")).hexdigest()[:12]


def _reject_http(status_code: int, detail: str) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content={"detail": detail})
    response.headers["Cache-Control"] = _NO_STORE_CACHE_CONTROL
    return response


def _add_static_headers(response: FileResponse, *, cache_control: str) -> FileResponse:
    response.headers["Cache-Control"] = cache_control
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


class HostScopeMiddleware:
    """Validate exact hosts once and reuse them across HTTP and WebSocket scopes."""

    def __init__(self, app: Any, *, settings: Any | None = None) -> None:
        self.app = app
        self.settings = settings
        if self.settings is None:
            from backend.config import get_settings

            self.settings = get_settings()

        self.production = getattr(self.settings, "environment", "") == "production"
        self.host_map = build_host_scope_map(self.settings)
        self.runtime_paths = resolve_runtime_paths(self.settings)

    async def __call__(self, scope: dict[str, Any], receive, send) -> None:
        scope_type = scope.get("type")
        if scope_type not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        raw_host = headers.get("host")
        hostname = normalize_host_header(raw_host)
        host_scope = resolve_host_scope(raw_host, self.host_map)

        state = scope.setdefault("state", {})
        state["host_scope"] = host_scope

        if self.production and host_scope is None:
            self._log_rejection("unknown_host", hostname, scope.get("path", ""))
            if scope_type == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            response = _reject_http(404, "Not Found")
            await response(scope, receive, send)
            return

        path = scope.get("path", "") or "/"
        foreign_game = game_from_path(path)
        if self.production and host_scope is not None and foreign_game is not None and foreign_game != host_scope.game:
            self._log_rejection("foreign_game_prefix", hostname, path)
            if scope_type == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            response = _reject_http(404, "Not Found")
            await response(scope, receive, send)
            return

        if scope_type == "http" and self.production and scope.get("method") in {"GET", "HEAD"}:
            static_response = self._maybe_serve_static(scope, headers, host_scope)
            if static_response is not None:
                await static_response(scope, receive, send)
                return

        await self.app(scope, receive, send)

    def _log_rejection(self, category: str, hostname: str | None, path: str) -> None:
        logger.warning(
            "Rejected request during host-scope validation",
            extra={
                "host_hash": _hash_host(hostname),
                "path_class": category,
                "path_prefix": path[:48],
            },
        )

    def _maybe_serve_static(
        self,
        scope: dict[str, Any],
        headers: Headers,
        host_scope: HostScope | None,
    ) -> FileResponse | None:
        if host_scope is None:
            return None

        path = scope.get("path", "") or "/"
        if is_reserved_api_path(path):
            return None

        static_dir = static_release_dir(self.runtime_paths.static_root, host_scope)
        index_path = static_dir / "index.html"
        if not index_path.is_file():
            return _reject_http(503, "Static release is unavailable")

        candidate = safe_static_candidate(static_dir, path)
        if candidate is not None and candidate.is_file():
            return self._prepare_static_response(candidate, path)

        if self._should_serve_index(path, headers.get("accept")):
            return self._prepare_static_response(index_path, path, index=True)

        return None

    def _should_serve_index(self, path: str, accept_header: str | None) -> bool:
        if path in {"", "/"}:
            return True

        if Path(path).suffix:
            return False

        if not accept_header:
            return True

        accept = accept_header.lower()
        return "text/html" in accept or "application/xhtml+xml" in accept or "*/*" in accept

    def _prepare_static_response(self, file_path: Path, request_path: str, *, index: bool = False) -> FileResponse:
        response = FileResponse(file_path)
        filename = file_path.name.lower()

        if index or filename == "index.html" or filename in {"manifest.webmanifest", "manifest.json", "service-worker.js", "sw.js"}:
            cache_control = _INDEX_CACHE_CONTROL
        else:
            cache_control = _ASSET_CACHE_CONTROL

        media_type, _ = mimetypes.guess_type(str(file_path))
        if media_type:
            response.media_type = media_type

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = cache_control

        return response
