# Dependency Policy

> **Status:** Active

This repository has two dependency surfaces: the Python backend (`requirements.txt`)
and the npm workspaces for the four frontends + shared library (`package-lock.json`).

- **Install reproducibly.** Backend: install from `requirements.txt` and remove
  unbounded ranges before calling it locked (`openai>=2.4.0` is currently not a
  reproducible pin). Frontend: `npm ci` from the committed
  lockfiles in CI. Never hand-edit `package-lock.json`.
- **Keep dependency upgrades separate** from feature and refactor changes.
- **Group routine patch/minor updates;** treat majors as explicit migrations with
  release-note review (FastAPI, SQLAlchemy, Pydantic, Alembic, Vite, React, and
  Tailwind majors all carry breaking-change risk).
- **Run the full gate for dependency changes:** deterministic verify, production-
  SQLite integration, smoke when runtime behavior changes, all four frontend
  builds, and security audits (`npm audit --audit-level=high` and `pip-audit`).
- **Pin third-party GitHub Actions to full immutable commit SHAs** and use minimal
  workflow permissions.
- **Explain every new runtime dependency,** its trust surface, and why existing code
  is insufficient. Prefer the standard library / already-present packages.
- Dependabot may propose updates, but passing automation does not replace review of
  behavior and supply-chain impact.
