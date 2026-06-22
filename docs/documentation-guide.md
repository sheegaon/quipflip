# Documentation Guide

> **Document type:** Engineering guidance
> **Status:** Active
> **Audience:** Maintainers and contributors

How to structure and maintain documentation in this repository, adapted from the
sibling `pixel-plagiarist` conventions.

## Structure

- `README.md` (root) is the entry point and quick start.
- `AGENTS.md` files carry operating rules: the root file holds universal rules; each
  `backend/`, `frontend/`, and `tests/` file holds subsystem rules. One canonical
  source per rule — do not duplicate a rule across files; link instead.
- `docs/README.md` is the index; every durable document is reachable from it.
- `docs/development/` holds active engineering how-to and policy.
- `docs/decisions/` holds Architecture Decision Records (ADRs).
- `docs/<game>/` holds per-game rules and design.
- Reference docs (`API.md`, `ARCHITECTURE.md`, `DATA_MODELS.md`, `WEBSOCKET.md`,
  `AI_SERVICE.md`) describe current implementation; keep them in sync with code.

## Status headers

Start each non-trivial document with a short block:

```markdown
> **Document type:** <runbook | guidance | reference | plan | ADR>
> **Status:** <Active | Target | Historical | Superseded by …>
> **Audience:** <maintainers | agents | …>
```

Mark plans and migration-target docs clearly so they are not mistaken for the
current live state (for example, the startup-services runbook is **Target** until
the Mac+Cloudflare cutover; `DEPLOYMENT.md` is the **current** state until then).

## Authority order

When documents disagree:

1. Direct task instructions and applicable `AGENTS.md` files govern the work.
2. Accepted ADRs and canonical game rules define intended architecture/behavior.
3. Running code and tests define what is implemented today.
4. Active references describe current workflows and must be checked against code.
5. Target plans, completed plans, and historical docs provide context only.

State whether a claim is **implemented**, **intended**, or **observed at a dated
baseline**. Do not turn an observed bug into a rule or describe a target runbook as
already deployed.

## Naming and maintenance

- Use kebab-case filenames for new docs (`codebase-organization.md`). Existing
  SCREAMING_CASE reference files may stay until they are next substantially revised.
- Prefer relative links between docs so they survive moves.
- When behavior changes, update the doc in the same change; a stale doc is a bug.
- Delete or mark **Superseded** rather than leaving two documents that contradict
  each other. ADRs are superseded by new ADRs, never silently rewritten.
- Do not put secrets, credentials, or private player data in any document, including
  examples and screenshots.
