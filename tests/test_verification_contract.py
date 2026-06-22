"""Executable checks for the repository verification contract."""

from __future__ import annotations

import configparser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_default_pytest_gate_excludes_environment_dependent_tiers() -> None:
    config = configparser.ConfigParser()
    config.read(ROOT / "pytest.ini")
    addopts = config["pytest"]["addopts"]

    for marker in ("sqlite_integration", "smoke", "stress", "external"):
        assert f"not {marker}" in addopts


def test_localhost_suites_are_not_named_like_default_tests() -> None:
    localhost_suites = sorted((ROOT / "tests").glob("test_*localhost*.py"))
    assert localhost_suites
    assert all("_localhost" in path.stem for path in localhost_suites)
