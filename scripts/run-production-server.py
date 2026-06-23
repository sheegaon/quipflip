#!/usr/bin/env python3
"""Production server wrapper for the Crowdcraft deployment."""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
UVICORN_CANDIDATES = (
    ROOT_DIR / ".venv" / "bin" / "uvicorn",
    Path(sys.executable).with_name("uvicorn"),
)


def _select_uvicorn_executable() -> str:
    for candidate in UVICORN_CANDIDATES:
        if candidate.is_file():
            return str(candidate)

    return sys.executable


def _validate_production_settings() -> None:
    from backend.config import get_settings
    from backend.runtime.config import validate_runtime_settings

    settings = get_settings()
    errors = validate_runtime_settings(settings)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    os.chdir(ROOT_DIR)
    _validate_production_settings()

    uvicorn_executable = _select_uvicorn_executable()
    if Path(uvicorn_executable).name == "uvicorn":
        argv = [
            uvicorn_executable,
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--workers",
            "1",
            "--proxy-headers",
            "--forwarded-allow-ips",
            "127.0.0.1",
        ]
    else:
        argv = [
            uvicorn_executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--workers",
            "1",
            "--proxy-headers",
            "--forwarded-allow-ips",
            "127.0.0.1",
        ]

    os.execv(uvicorn_executable, argv)


if __name__ == "__main__":
    main()
