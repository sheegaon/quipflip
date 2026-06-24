"""Smoke checks for a production-like Crowdcraft deployment."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, asdict
from typing import Any

import httpx

from backend.config import get_settings
from backend.runtime.host_scope import build_host_scope_map
from backend.utils.model_registry import GameType


TITLE_FRAGMENTS: dict[GameType, str] = {
    GameType.QF: "Quipflip",
    GameType.MM: "MemeMint",
    GameType.IR: "Initial Reaction",
    GameType.TL: "ThinkLink",
}

API_PATHS: dict[GameType, tuple[str, tuple[int, ...], str]] = {
    GameType.QF: ("/qf/health", (200,), "/mm/health"),
    GameType.MM: ("/mm/health", (200,), "/qf/health"),
    GameType.IR: ("/ir/leaderboard/creators", (401, 403), "/mm/health"),
    GameType.TL: ("/tl/game/prompts/preview", (200,), "/mm/health"),
}


@dataclass(frozen=True, slots=True)
class SmokeCase:
    host: str
    title_fragment: str
    api_path: str
    api_statuses: tuple[int, ...]
    cross_game_path: str


def build_smoke_cases(settings: Any | None = None) -> list[SmokeCase]:
    settings = settings or get_settings()
    host_map = build_host_scope_map(settings)

    cases: list[SmokeCase] = []
    for scope in host_map.values():
        title_fragment = TITLE_FRAGMENTS[scope.game]
        api_path, api_statuses, cross_game_path = API_PATHS[scope.game]
        cases.append(
            SmokeCase(
                host=scope.hostname,
                title_fragment=title_fragment,
                api_path=api_path,
                api_statuses=api_statuses,
                cross_game_path=cross_game_path,
            )
        )

    return cases


def _extract_title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _response_summary(response: httpx.Response) -> dict[str, Any]:
    title = _extract_title(response.text) if "text/html" in response.headers.get("content-type", "") else ""
    return {
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "title": title,
        "body_prefix": response.text[:200] if response.text else "",
    }


async def run_smoke(
    *,
    base_url: str = "http://127.0.0.1:8000",
    settings: Any | None = None,
    app: Any | None = None,
    cases: list[SmokeCase] | None = None,
) -> dict[str, Any]:
    """Run the host matrix against a built Crowdcraft service."""

    settings = settings or get_settings()
    selected_cases = cases or build_smoke_cases(settings)
    if not selected_cases:
        raise RuntimeError("No configured hosts available for smoke testing")

    transport = httpx.ASGITransport(app=app) if app is not None else None
    timeout = httpx.Timeout(10.0, connect=5.0)
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    async with httpx.AsyncClient(
        base_url=base_url,
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        shared_host = selected_cases[0].host
        for path in ("/livez", "/readyz"):
            response = await client.get(path, headers={"Host": shared_host, "Accept": "application/json"})
            summary = _response_summary(response)
            results.append({"host": shared_host, "path": path, **summary})
            if response.status_code != 200:
                errors.append(f"{shared_host}{path} returned {response.status_code}")

        for case in selected_cases:
            root_response = await client.get("/", headers={"Host": case.host, "Accept": "text/html"})
            root_summary = _response_summary(root_response)
            results.append({"host": case.host, "path": "/", **root_summary})
            if root_response.status_code != 200:
                errors.append(f"{case.host}/ returned {root_response.status_code}")
            elif case.title_fragment not in root_summary["title"]:
                errors.append(
                    f"{case.host}/ title {root_summary['title']!r} did not contain {case.title_fragment!r}"
                )

            api_response = await client.get(case.api_path, headers={"Host": case.host, "Accept": "application/json"})
            api_summary = _response_summary(api_response)
            results.append({"host": case.host, "path": case.api_path, **api_summary})
            if api_response.status_code not in case.api_statuses:
                errors.append(
                    f"{case.host}{case.api_path} returned {api_response.status_code}, expected one of {case.api_statuses}"
                )

            cross_game_response = await client.get(
                case.cross_game_path,
                headers={"Host": case.host, "Accept": "application/json"},
            )
            cross_game_summary = _response_summary(cross_game_response)
            results.append({"host": case.host, "path": case.cross_game_path, **cross_game_summary})
            if cross_game_response.status_code != 404:
                errors.append(
                    f"{case.host}{case.cross_game_path} returned {cross_game_response.status_code}, expected 404"
                )

    report = {
        "ok": not errors,
        "base_url": base_url,
        "cases": [asdict(case) for case in selected_cases],
        "results": results,
        "errors": errors,
    }

    if errors:
        raise RuntimeError("; ".join(errors))

    return report


def dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def run_smoke_sync(
    *,
    base_url: str = "http://127.0.0.1:8000",
    settings: Any | None = None,
    app: Any | None = None,
    cases: list[SmokeCase] | None = None,
) -> dict[str, Any]:
    return asyncio.run(run_smoke(base_url=base_url, settings=settings, app=app, cases=cases))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crowdcraft-smoke", description="Run deployment smoke checks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Base URL to smoke.")
    parser.add_argument("--json", action="store_true", help="Print the smoke report as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    report = run_smoke_sync(base_url=args.base_url)
    if args.json:
        print(dump_json(report), end="")
    else:
        print(f"Smoke passed for {report['base_url']} with {len(report['cases'])} hosts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
