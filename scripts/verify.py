#!/usr/bin/env python3
"""Canonical local verification entry points."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
PYTHON = str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable))


def run_all(commands: list[tuple[str, list[str]]]) -> int:
    failures: list[str] = []
    for label, command in commands:
        print(f"\n==> {label}: {' '.join(command)}", flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            failures.append(label)

    if failures:
        print(f"\nVerification failures: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "verify"
    modes = {
        "verify": [
            ("backend deterministic", [PYTHON, "-m", "pytest"]),
            ("frontend origin contracts", ["node", "--test", "scripts/test_frontend_origins.mjs"]),
            ("frontend lint/typecheck/build", ["node", "scripts/run_frontend_checks.mjs"]),
            ("secret scan", [PYTHON, "scripts/scan_secrets.py"]),
        ],
        "backend": [("backend deterministic", [PYTHON, "-m", "pytest"])],
        "sqlite-integration": [
            (
                "production SQLite integration",
                [PYTHON, "-m", "pytest", "-m", "sqlite_integration", "tests/sqlite_integration"],
            )
        ],
        "smoke": [
            (
                "localhost smoke",
                [PYTHON, "-m", "pytest", "-m", "smoke", "tests", "-v"],
            )
        ],
    }
    if mode not in modes:
        print(f"Unknown mode {mode!r}. Choose one of: {', '.join(modes)}", file=sys.stderr)
        return 2
    return run_all(modes[mode])


if __name__ == "__main__":
    raise SystemExit(main())
