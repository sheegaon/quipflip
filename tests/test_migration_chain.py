"""Sanity checks for Alembic migration ordering.

This test ensures the migrations in ``backend/migrations/versions`` form a
single linear upgrade path with no missing or duplicate revisions.  It guards
against accidentally creating multiple heads or referencing a down revision
that does not exist, both of which break ``alembic upgrade head``.
"""

from __future__ import annotations

from pathlib import Path
import re


VERSIONS_DIR = Path(__file__).resolve().parents[1] / "backend" / "migrations" / "versions"


def _parse_revisions() -> dict[str, str | None]:
    revision_pattern = re.compile(r"revision:\s*.*?['\"]([0-9a-f]+)['\"]")
    down_revision_pattern = re.compile(r"down_revision:\s*.*?['\"]([^'\"]*)['\"]")

    revisions: dict[str, str | None] = {}
    for path in VERSIONS_DIR.glob("*.py"):
        text = path.read_text()

        revision_match = revision_pattern.search(text)
        if not revision_match:
            raise AssertionError(f"Missing revision identifier in {path.name}")

        down_match = down_revision_pattern.search(text)
        down_revision = down_match.group(1) if down_match else None
        if down_revision in {"", "None"}:
            down_revision = None

        revision = revision_match.group(1)
        revisions[revision] = down_revision

    return revisions


def test_migrations_have_single_head() -> None:
    revisions = _parse_revisions()

    # Every down revision should correspond to a known migration (except None).
    missing = {
        down for down in revisions.values() if down and down not in revisions
    }
    assert not missing, f"Missing migration files referenced by down_revision: {missing}"

    # The head is any revision that is never referenced as a down revision.
    referenced = {down for down in revisions.values() if down}
    heads = sorted(set(revisions) - referenced)
    assert len(heads) == 1, f"Multiple migration heads detected: {heads}"

    # Follow the chain from head to ensure every migration is reachable exactly once.
    seen: set[str] = set()
    current = heads[0]
    while current:
        assert current not in seen, f"Cycle detected in migration chain at {current}"
        seen.add(current)
        current = revisions[current]

    assert len(seen) == len(revisions), (
        "Some migrations are unreachable from the base revision: "
        f"{sorted(set(revisions) - seen)}"
    )
