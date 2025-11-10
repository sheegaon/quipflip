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
    revision_pattern = re.compile(r"revision:\s*.*?['\"]([^'\"]+)['\"]")
    down_revision_pattern = re.compile(r"down_revision:\s*.*?=\s*(.+)")

    revisions: dict[str, str | None] = {}
    for path in VERSIONS_DIR.glob("*.py"):
        text = path.read_text()

        revision_match = revision_pattern.search(text)
        if not revision_match:
            raise AssertionError(f"Missing revision identifier in {path.name}")

        down_match = down_revision_pattern.search(text)
        down_revision = None
        if down_match:
            down_value = down_match.group(1).strip()
            # Handle different down_revision formats
            if down_value in {"None", "''", '""'}:
                down_revision = None
            elif down_value.startswith("(") and down_value.endswith(")"):
                # Handle tuple format for merge migrations like ('rev1', 'rev2')
                # Extract all quoted strings from the tuple
                tuple_revisions = re.findall(r"['\"]([^'\"]+)['\"]", down_value)
                # For the test, we'll treat merge migrations as having multiple parents
                # but we'll track all referenced revisions
                down_revision = tuple_revisions if tuple_revisions else None
            elif "'" in down_value or '"' in down_value:
                # Handle single quoted string
                string_match = re.search(r"['\"]([^'\"]*)['\"]", down_value)
                if string_match:
                    down_revision = string_match.group(1) if string_match.group(1) else None

        revision = revision_match.group(1)
        revisions[revision] = down_revision

    return revisions


def test_migrations_have_single_head() -> None:
    revisions = _parse_revisions()

    # Collect all referenced revisions, handling both single strings and tuples
    referenced = set()
    for down in revisions.values():
        if down:
            if isinstance(down, list):
                # Handle merge migrations with multiple parents
                referenced.update(down)
            else:
                referenced.add(down)

    # Every down revision should correspond to a known migration (except None).
    missing = {
        ref for ref in referenced if ref not in revisions
    }
    assert not missing, f"Missing migration files referenced by down_revision: {missing}"

    # The head is any revision that is never referenced as a down revision.
    heads = sorted(set(revisions) - referenced)
    assert len(heads) == 1, f"Multiple migration heads detected: {heads}"

    # Follow the chain from head to ensure migrations are reachable
    # Note: This simplified check works for linear chains and basic merges
    seen: set[str] = set()
    
    def visit_revision(current: str | None) -> None:
        if not current or current in seen:
            return
        seen.add(current)
        down = revisions[current]
        if isinstance(down, list):
            # Handle merge migrations - visit all parents
            for parent in down:
                visit_revision(parent)
        else:
            visit_revision(down)
    
    visit_revision(heads[0])

    # Check that all revisions are reachable from the head
    unreachable = set(revisions) - seen
    assert not unreachable, (
        "Some migrations are unreachable from the head revision: "
        f"{sorted(unreachable)}"
    )
