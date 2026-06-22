# Documentation

> **Document type:** Index
> **Status:** Active
> **Audience:** Maintainers, contributors, and agents

Use this page to find the authoritative document for a task. The root
[README](../README.md) is the project entry point; the
[reliability and deployment plan](transition-plan.md) is the active roadmap.

## Active engineering guidance

- [Agent guide](../AGENTS.md) — repository rules, invariants, and verification.
- [Codebase organization](development/codebase-organization.md) — target layering,
  SQLite correctness boundary, lifecycle ownership, and protocol rules.
- [Autonomous workflow](development/autonomous-agent-workflow.md) — task contracts,
  change discipline, evidence, and independent review.
- [Testing strategy](development/testing-strategy.md) — deterministic, production-
  SQLite, smoke, stress, and browser tiers.
- [Security and secrets](development/security-and-secrets.md) — credentials,
  logging, money integrity, and transport security.
- [Dependency policy](development/dependency-policy.md) — lockfiles, audits, and CI.
- [Architecture decisions](decisions/README.md) — durable design intent.

## Deployment

- [Current Heroku/Vercel deployment](DEPLOYMENT.md) — current hosting model only;
  the backend was in maintenance mode during the 2026-06-22 review.
- [Target Mac/Cloudflare operations](development/persistent-startup-services.md) —
  target runbook; it is not active until the cutover exit criteria pass.
- [Transition plan](transition-plan.md) — migration sequence, gates, rollback, and
  dated baseline evidence.
- [Transition workstream plans](transition/README.md) — phased implementation
  checklists for verification, lifecycle invariants, each game group, and
  deployment.

## Current implementation references

These documents describe the implementation but may lag code. For endpoint truth,
compare them with the generated FastAPI OpenAPI schema and tests before changing a
client.

- [Architecture](ARCHITECTURE.md)
- [API overview](API.md)
- [Data models](DATA_MODELS.md)
- [WebSockets](WEBSOCKET.md)
- [AI service](AI_SERVICE.md)
- [Cleanup and repair tools](CLEANUP_SCRIPTS.md)

## Canonical game rules

- QuipFlip: [rules](quipflip/QF_GAME_RULES.md),
  [API reference](quipflip/QF_API.md),
  [data models](quipflip/QF_DATA_MODELS.md), and
  [frontend contexts](quipflip/QF_FRONTEND_CONTEXTS.md).
- MemeMint: [rules](mememint/MM_GAME_RULES.md),
  [API reference](mememint/MM_API.md),
  [data models](mememint/MM_DATA_MODELS.md), and
  [circles design](mememint/MM_CIRCLES.md).
- Initial Reaction: [rules](initialreaction/IR_GAME_RULES.md),
  [API reference](initialreaction/IR_API.md),
  [data models](initialreaction/IR_DATA_MODELS.md), and
  [UX flow](initialreaction/IR_UX_FLOW.md).
- ThinkLink: [rules](thinklink/TL_GAME_RULES.md),
  [API reference](thinklink/TL_API.md),
  [data models](thinklink/TL_DATA_MODELS.md), and
  [quick facts](thinklink/TL_QUICK_FACTS.md).

When a game-rules document and code disagree, the rules describe intended behavior
and code/tests describe implemented behavior. Resolve the discrepancy explicitly;
do not silently redefine the economy from current bugs.

## Historical and migration material

These files provide context and do not override active guidance or game rules:

- [Heroku migration lessons](HEROKU_MIGRATION_LESSONS.md)
- [Global player refactor plan](GLOBAL_PLAYER_REFACTOR_PLAN.md)
- [QuipFlip claim-to-receive migration](quipflip/CLAIM_TO_RECEIVE_MIGRATION_GUIDE.md)
- [Deleted-user display repair](quipflip/FIX_DELETED_USER_DISPLAY.md)
- [Party design archive](quipflip/party/)
- [MemeMint circles implementation notes](mememint/MM_CIRCLES_IMPLEMENTATION.md)
- [Initial Reaction MVP plan](initialreaction/IR_MVP_PLAN.md)
- [ThinkLink implementation plan and development spec](thinklink/IMPLEMENTATION_PLAN.md)

## Authority order

1. Direct task instructions and applicable `AGENTS.md` files.
2. Accepted ADRs and active engineering guidance.
3. Running code and tests for implemented behavior.
4. Canonical per-game rules for intended gameplay/economy.
5. Current reference documents.
6. Target plans, migration guides, and historical material.

Use the [documentation guide](documentation-guide.md) when adding or retiring a
document.
