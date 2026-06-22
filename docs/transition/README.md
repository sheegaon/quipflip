# Transition Workstream Plans

> **Document type:** Plan index
> **Status:** Active
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

The [transition roadmap](../transition-plan.md) defines sequencing and system-wide
exit criteria. These documents turn each roadmap workstream into an independently
executable phased plan:

- [A - Trustworthy verification](workstream-a-trustworthy-verification.md)
- [B - Lifecycle inventory and database invariants](workstream-b-lifecycle-invariants.md)
- [C - QuipFlip solo hardening](workstream-c-quipflip-solo.md)
- [D - QuipFlip Party Mode](workstream-d-quipflip-party.md)
- [E - MemeMint, Initial Reaction, and ThinkLink](workstream-e-remaining-games.md)
- [F - Mac and Cloudflare deployment](workstream-f-mac-cloudflare-deployment.md)

## How to use these plans

- Complete phases in order within a workstream unless its plan explicitly permits
  parallel work.
- Treat unchecked items as planned work, not proof that the behavior is absent.
- Check an item only in the change that supplies the evidence. Add a short link to
  the relevant pull request, test, ADR, runbook, or dated verification note.
- Do not check a phase gate while any required command is failing or unrun.
- Record newly discovered scope in the relevant plan before broadening an
  implementation change.
- The roadmap remains authoritative for cross-workstream ordering and cutover.

## Shared completion contract

Every implementation slice must follow the
[autonomous workflow](../development/autonomous-agent-workflow.md), preserve the
[codebase invariants](../development/codebase-organization.md), and report results
with the repository pull-request template. High-risk lifecycle, money, disclosure,
authentication, migration, CI, and deployment changes require the independent
review specified by the workflow.
