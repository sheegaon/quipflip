# Autonomous Agent Workflow

> **Status:** Active
> **Audience:** task authors, builders, and reviewers

This document expands the universal rules in the root [`AGENTS.md`](../../AGENTS.md).
Important requirements belong in executable checks whenever practical; prose explains
intent but is not an enforcement mechanism.

## Task contract

Every task should be one reviewable behavioral objective and use this structure:

```markdown
## Problem

## Expected behavior

## Acceptance criteria

## Relevant files or subsystem

## Invariants that must remain true

## Non-goals

## Required verification

## Documentation impact
```

If the contract is missing a security-, lifecycle-, money-, or disclosure-sensitive
detail, investigate before editing. Ask for a decision rather than inventing game
behavior or economy rules.

## Change discipline

- Prefer the smallest complete diff and explain material growth beyond the expected
  scope.
- Do not mix behavior changes with broad formatting, dependency upgrades, or
  mechanical extraction.
- Preserve unrelated local changes. Never reset or overwrite work to simplify a task
  (this repo often has in-flight branches such as `party-refactor`).
- Do not add compatibility layers without a named current consumer and a removal
  condition.
- Delete superseded implementations and temporary `debug_*`/`fix_*` scripts. Move
  newly discovered work to a follow-up task rather than silently expanding scope.
- Inspect the complete diff and any generated artifacts before completion.

## Verification evidence

Use focused checks during development. Before completion, run the full `pytest`
suite, build the affected frontends, run the smoke loop when lifecycle/transport
behavior changed, and do a browser check when user-visible behavior changed. A
failing check remains a failure unless its environmental limitation is documented
with evidence; pre-existing failures do not authorize weakening tests.

Tests should prove claims at the lowest useful layer — see
[testing strategy](testing-strategy.md). Disclosure and money-integrity invariants
require negative assertions, not only happy-path coverage.

## Independent review

The implementer must not be the only reviewer for substantial or high-risk changes.
Give the reviewer the task contract and diff before the builder's rationale.

- **Architecture:** dependency direction, lifecycle ownership, module boundaries.
- **Concurrency/lifecycle:** single command path, locking across read-decide-write,
  idempotent finalizers, reconnect-restores-state.
- **Money:** transaction-per-movement, idempotent refunds/payouts, no double
  distribution.
- **Disclosure/privacy:** response schemas never leak pre-finalization information.
- **Security:** credentials, authorization, untrusted inputs, logging, dependencies,
  CI.
- **UI:** rendered behavior, accessibility, responsive interaction.

Use two independent reviews for consequential changes spanning more than one
high-risk category. Findings must be resolved or explicitly recorded before merge.

## Stop conditions

Stop editing and investigate when:

- a credential or private player information may have been exposed;
- requested behavior conflicts with the game rules or tests;
- ownership of a lifecycle transition is unclear or duplicated;
- a response change could disclose pre-finalization information;
- a flipcoin movement could be double-applied;
- a migration could destroy or orphan data;
- test output is non-deterministic or cannot reproduce the reported failure;
- the change requires bypassing validation, authorization, locking, or a gate.

## Completion report

Use the [pull-request template](../../.github/pull_request_template.md) as the
evidence package. Include exact commands and outcomes, browser evidence or why it
was not applicable, known limitations, and files deliberately excluded. Never
describe an unrun check as passing.
