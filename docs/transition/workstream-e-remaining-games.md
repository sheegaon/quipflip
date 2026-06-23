# Workstream E - MemeMint, Initial Reaction, and ThinkLink

> **Document type:** Implementation plan
> **Status:** Active
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Objective

Apply the verified lifecycle, database, money, privacy, reconnect, and smoke-test
guarantees to Initial Reaction (IR), MemeMint (MM), and ThinkLink (TL), then verify
the shared client and authentication behavior used by all four games.

The work is complete only when each game has:

- pure, deterministic rules;
- one transactional command for each lifecycle transition;
- database-enforced ownership, uniqueness, and retry safety;
- explicit actor-scoped response schemas;
- restart-safe reads and reconnect behavior;
- production-shaped SQLite concurrency coverage; and
- a built-server smoke loop.

## Task contract

### Problem

IR, MM, and TL contain playable implementations, but their reliability boundaries
do not yet match the target architecture:

- routers and services split individual transitions across multiple commits;
- process locks and in-memory coordination still participate in correctness;
- active-round and single-winner invariants are not consistently database-enforced;
- ledger rows do not carry stable idempotency keys;
- pre-finalization responses expose internal IDs or authorship relationships;
- lifecycle and frontend models disagree in several places; and
- current tests mostly cover happy paths or pure helpers, not retries, races,
  restarts, disclosure, or complete built-server flows.

### Expected behavior

For every public command, the server authenticates the actor, validates the
payload, and invokes one owning service command. That command re-validates state
inside a short SQLite transaction, conditionally performs the transition, writes
all ledger and lifecycle changes atomically, and returns a typed outcome.

Duplicate, concurrent, late, and stale commands must have explicit behavior.
Restarting the process or losing queue/cache state must not change ownership,
eligibility, balances, frozen snapshots, or finalization results.

### Acceptance criteria

- IR, MM, and TL each satisfy their phase gate below.
- Every mutation caller in the E0 inventory maps to exactly one command owner.
- Every charge, refund, bonus, and payout has a unique logical movement key.
- Active assignments and one-vote/one-result relationships are enforced by
  constraints or conditional updates, not by a process lock.
- Before finalization, actor projections contain no forbidden authorship, source,
  answer, match, or stable internal relationship fields.
- Reconnect/read endpoints reconstruct the same durable state without creating,
  charging, advancing, or resetting play.
- Shared client changes build and pass contract tests for QF, MM, IR, and TL.
- The required deterministic, SQLite, smoke, and review gates pass.

### Invariants

- The server owns eligibility, pricing, selection, scoring, deadlines, and
  finalization.
- SQLite remains durable truth; queues and locks are rebuildable coordination.
- No synchronous lock is held across `await`.
- External embedding, moderation, or AI work does not run inside a write
  transaction.
- Finalization is the only payout path and is stale-safe.
- Internal ORM models are never response payloads.
- Rule discrepancies are resolved against the canonical game-rules documents,
  not silently normalized across games.

### Non-goals

- Combining the games behind one generic lifecycle abstraction.
- Changing canonical game rules to fit current code.
- Replacing SQLite, introducing multiple Uvicorn workers, or making Redis durable
  truth.
- Redesigning game UIs.
- Implementing TL challenges or other documented future features.

## Dependencies and ordering

- Requires workstream A's deterministic backend/frontend gates, production-shaped
  SQLite harness, and built-server smoke runner.
- Uses workstream B's command boundary, lifecycle-version convention, migration
  discipline, ledger idempotency format, and private projections.
- Reuses proven workstream C patterns for assignment, charging, finalization, and
  negative disclosure assertions.
- Implements [ADR 0001](../decisions/0001-server-authoritative-lifecycle.md),
  [ADR 0002](../decisions/0002-private-response-projection.md),
  [ADR 0003](../decisions/0003-database-source-of-truth.md), and
  [ADR 0005](../decisions/0005-sqlite-concurrency-boundary.md).
- Work proceeds in this order:
  1. E0 inventory and rule decisions;
  2. E1 IR stabilization;
  3. E2 MM integrity;
  4. E3 TL finalization; and
  5. E4 cross-game auth and shared-client verification.
- Do not begin a game's schema/command migration until its unresolved rule
  questions are decided and recorded in its state-machine page.

## Repository anchors and verified gaps

### Shared client and CI

- `frontend/crowdcraft/src/api/client.ts` strips `/qf`, `/mm`, and `/tl` from the
  root API base but omits `/ir`.
- The shared client creates QF, MM, and TL clients, while IR still has a separate
  client and duplicated session/WebSocket logic under `frontend/ir/src`.
- `.github/workflows/testing.yml` has frontend jobs for QF, MM, and TL but no IR
  lint/build job.
- Root auth is mounted at `/auth`, `/qf/auth`, `/mm/auth`, and `/tl/auth`, but not
  `/ir/auth`; IR also exposes legacy player-auth endpoints.
- Shared `/auth/ws-token` currently authenticates without a game scope.
- Host-to-game routing is not yet the authorization boundary; URL prefixes remain
  callable independently of the request host.

### Initial Reaction

- `/ir/game/start` selects or creates a set and commits it before charging the
  player. It does not create a durable assignment, so a charged player can exist
  without an entry or reconnectable claim.
- `/ir/game/sets/{set_id}/submit` creates the entry in a later transaction.
- vote eligibility, the non-participant charge, vote insertion, counters, and
  possible finalization are split across services and commits.
- `BackronymSet.entry_count`, `vote_count`, and payout totals are mutable cached
  values without lifecycle-version checks or range constraints.
- queue updates occur after database commits and `_entry_queue` /
  `_voting_queue` are process memory.
- observer-gating intent conflicts: the data-model document describes the earliest
  creator account timestamp, while current code stores the first join timestamp.
- IR responses and shared frontend types expose player IDs, entry IDs, vote IDs,
  and chosen-entry relationships broadly.
- `IRTransaction` has no idempotency key; result collection has an existing
  uniqueness pattern in `uq_ir_result_view_player_set`.
- two IR transaction tests are skipped because their expected service methods do
  not exist.

### MemeMint

- vote-round selection, charge, and creation run under a synchronous process lock;
  correctness depends on `SELECT ... FOR UPDATE`, which is ineffective on SQLite.
- `MMVoteRound` has no explicit status, lifecycle version, deadline, or active-round
  uniqueness.
- the start-vote response includes `author_username` before voting, contrary to
  the MM rule that authorship is hidden until reveal.
- vote validation, caption counters, seen rows, first-voter arbitration, circle
  bonus suppression, author payouts, and round completion are one large service
  path without ledger movement keys.
- `first_vote_awarded` is a mutable boolean with no database single-winner command.
- caption submission accepts any owned round and does not prove the vote was
  completed or that the round has not already produced a caption.
- free-caption consumption, fee charging, caption creation, and submission logging
  rely on a process lock and need database uniqueness.
- the API returns an `expires_at` value equal to `created_at`, while the router says
  vote rounds never expire.
- circles affect selection and payout suppression; those reads must be evaluated
  in the owning command so alternate/admin paths cannot bypass them.
- `MMTransaction` has no idempotency key.

### ThinkLink

- `TLRound` has status checks and strike bounds, but no lifecycle version, active
  round uniqueness, or idempotent command key.
- a round snapshot stores answer and cluster IDs plus total weight. Guess matching
  and coverage later reload mutable `TLAnswer` rows, so edits, pruning, deletes,
  cluster reassignment, or weight changes can alter an in-progress round.
- start, guess, abandon, and finalization use ORM read-modify-write without a
  compare-and-swap winner.
- finalization writes payout and answer statistics without a ledger idempotency key.
- a duplicate finalizer can update answer statistics or balances twice.
- current code auto-finalizes at 95% coverage, while the canonical rule only names
  100% as an optional auto-end.
- current code marks three-strike completion as `completed`; API documentation
  describes `abandoned`.
- canonical rules allow manual quit at any time; current code permits the 95-coin
  refund only before the first guess. The payout/refund behavior after guesses is
  unresolved.
- play/detail responses expose prompt IDs and matched cluster IDs. Those are
  internal relationships and are not needed by the player UI.
- `TLTransaction` is a separate ledger implementation without movement keys or
  cached balance-after fields.
- `tests/test_tl_similarity_debug.py` contains diagnostic-style tests and service
  logs include embedding type/sample diagnostics that should not be part of the
  normal gate.

## E0 - Contract, state machines, and baseline

### Deliverables

Create these reviewed state-machine pages:

- `docs/initialreaction/IR_STATE_MACHINE.md`
- `docs/mememint/MM_STATE_MACHINE.md`
- `docs/thinklink/TL_STATE_MACHINE.md`

Each page must record, for every state:

- actor and public command;
- owning backend command;
- in-transaction preconditions;
- status/version predicate;
- deadline and late-command behavior;
- rows inserted or updated;
- ledger movement keys;
- returned actor projection;
- forbidden fields;
- duplicate/concurrent/stale outcome;
- reconnect projection; and
- all mutation callers that must be migrated or deleted.

### Initial state-machine baseline

| Game | Aggregate | States | Required owning commands |
| --- | --- | --- | --- |
| IR | assignment | `assigned`, `submitted`, `expired`, `cancelled` | assign, submit, expire/cancel |
| IR | backronym set | `open`, `voting`, `finalizing`, `finalized`, `cancelled` | accept entry, open voting, accept vote, deadline fill, finalize |
| MM | vote round | `active`, `voted`, `captioned`, `closed`, `abandoned` | start, vote, submit caption, close/abandon |
| MM | caption | `active`, `retired`, `removed` | create, record vote, retire/remove |
| TL | round | `active`, `finalizing`, `completed`, `abandoned` | start, submit guess, quit, finalize |
| TL | corpus answer | `active`, `inactive` | accept/cluster answer, prune |

The exact state names may change during E0, but status semantics must not remain
implicit combinations of nullable fields.

### Rule decisions required before implementation

Record each decision in the relevant canonical rules or state-machine page.

#### IR

- Is the 100-coin fee charged when an assignment is created or when the backronym
  is submitted? What refund applies to an expired unsubmitted assignment?
- Is non-participant eligibility based on account creation before the first
  creator's account creation or before the first creator joined the set?
- In Standard mode, what deadline applies when no human vote has yet occurred?
- Are creator payouts automatic at finalization or credited on first result view?
- Do AI entries contribute entry fees, receive payouts, or only affect vote share?
- Is the per-guest lifetime non-participant vote cap canonical or only rate-limit
  scaffolding?

#### MM

- Do vote rounds have an authoritative deadline? If not, remove `expires_at` from
  the protocol instead of manufacturing one.
- Is caption submission allowed only after a successful vote, and exactly once per
  vote round?
- Does abandoning an unvoted round refund any of the 5-coin entry fee?
- Is `correct` meaningful in `SubmitVoteResponse`, or should the field be removed?
- Which result/reveal payload is allowed to expose caption and parent authorship?
- Reconcile the riff threshold conflict between automatic classification (`> 0.5`)
  and near-duplicate rejection (`>= 0.7`).

#### TL

- At manual quit after one or more guesses, does the round finalize using current
  coverage, receive no payout, or receive a defined refund?
- Is the three-strike terminal status `completed` or `abandoned`?
- Is auto-completion enabled at exactly 100% coverage, disabled, or intentionally
  set to another threshold?
- Is the match boundary `> 0.55` or `>= 0.55`?
- Does an accepted player guess enter the future answer corpus, and if so when?
- Which answer/match details may be revealed after finalization?

### Mutation and projection inventories

Inventory at least these callers:

- REST routers under `backend/routers/{ir,mm,tl}`;
- startup and cleanup cycles in `backend/main.py`;
- IR backup/AI orchestration;
- MM cleanup, circles, admin/config paths, and seed/import scripts;
- TL admin seed/prune and cleanup paths;
- result-view, dashboard, history, statistics, and leaderboard reads;
- all game contexts, polling/reconnect paths, and notification/WebSocket clients;
- direct service calls in tests and operational scripts.

Mark each caller `command`, `projection`, `discovery-only`, `external-work`, or
`delete`.

### Regression baseline

Before behavior changes, add failing regressions for:

- IR charged-without-assignment, double start, fifth-entry race, fifth-participant
  vote race, duplicate non-participant charge, stale timeout, and duplicate payout;
- MM double start/charge, duplicate vote, first-voter race, duplicate author payout,
  duplicate caption/free-slot consumption, pre-vote author disclosure, and circle
  bonus bypass;
- TL double start/charge, duplicate guess, third-strike race, quit/finalize race,
  mutable snapshot, duplicate payout, duplicate answer-stat update, and stale
  finalizer.

### Focused test commands

Add markers in `pytest.ini` and apply them to the game suites:

```bash
pytest -m ir
pytest -m mm
pytest -m tl
pytest -m sqlite_integration
pytest -m smoke
```

Keep `tests/test_ir_*`, `tests/test_mm_*`, and `tests/test_tl_*` compatible during
the transition so CI can move to markers in a separate, reviewable change.

### E0 gate

- [ ] All three state-machine pages are reviewed.
- [ ] Every mutation caller has a disposition and intended owner.
- [ ] Rule questions are decided or explicitly block the affected phase.
- [ ] Each known reliability defect has a focused regression test or named test
      task.
- [ ] Per-game commands run independently.

## E1 - Initial Reaction stabilization

### E1.1 Frontend and protocol alignment

- Add `ir` to root-prefix normalization in
  `frontend/crowdcraft/src/api/client.ts`.
- Add a pure client-base regression covering bare origin and all four prefixed
  `VITE_API_URL` forms.
- Move IR onto the shared root auth/session client; retain a temporary adapter only
  if a current route consumer is named with a removal task.
- Add `/ir/auth` only if the shared deployment contract requires prefixed auth;
  otherwise migrate IR callers to canonical `/auth` and document that decision.
- Reconcile `backend/schemas/backronym.py`,
  `backend/routers/ir/schemas.py`, `frontend/crowdcraft/src/api/types.ts`, and
  `frontend/ir/src/api/client.ts`.
- Add an IR frontend lint/build job to CI and include it in `notify-success`.
- Remove generated duplicate Vite config artifacts only in a separate mechanical
  cleanup if they are proven unused.

### E1.2 Pure IR rules

Create `backend/services/ir/rules.py` with no FastAPI, SQLAlchemy, network,
wall-clock, or global-random dependencies. Cover:

- assignment/set eligibility and queue ordering;
- backronym shape and initial-letter validation;
- participant and observer vote eligibility;
- self-vote and duplicate-vote rejection;
- non-participant cap and fee;
- voting-completion decision;
- popular-choice/tie calculation;
- non-participant reward allocation;
- creator proportional allocation, rounding, and forfeiture;
- vault split and pool conservation; and
- deadline selection by mode.

Pass `now`, configuration, and seeded tie/random inputs explicitly.

### E1.3 Durable assignment and schema migration

Prefer a dedicated `IRAssignment` row over treating an unpaid/unsubmitted entry as
an assignment. The migration should add:

- assignment ID or actor-scoped token, player ID, set ID, status, version,
  assigned/submitted/expired timestamps, and charge/refund keys;
- one active assignment per player;
- one assignment per player/set;
- set status and mode checks;
- lifecycle `version` and explicit entry/vote deadlines on `BackronymSet`;
- range checks for cached counters and non-negative pool fields;
- a composite constraint proving a vote's chosen entry belongs to the same set
  (add the supporting unique key on entry `(entry_id, set_id)`);
- ledger `idempotency_key` uniqueness; and
- cleanup queries for charged-without-entry cases, duplicate active work, invalid
  counters, cross-set votes, and duplicate result rows.

Do not enable a uniqueness constraint until existing rows are classified and the
repair policy is reviewed.

### E1.4 IR lifecycle commands

Implement command modules under `backend/services/ir/commands/`:

- `assign_backronym(player_id, mode, command_id, now)`
- `submit_backronym(player_id, assignment_token, words, command_id, now)`
- `expire_assignment(assignment_id, expected_version, deadline, now)`
- `open_voting(set_id, expected_version, now)`
- `submit_vote(player_id, vote_token, entry_token, command_id, now)`
- `fill_due_entries(set_id, expected_version, now)`
- `fill_due_votes(set_id, expected_version, now)`
- `finalize_set(set_id, expected_version, now)`
- `collect_result(player_id, set_id, command_id, now)` only if rules retain
  collection-time credit.

Required command behavior:

- assignment selection, claim, charge, and deadline are one transaction;
- submission proves assignment ownership and expected version;
- the fifth accepted entry conditionally opens voting once;
- non-participant eligibility, slot claim, fee, and vote insertion are atomic;
- the fifth creator vote or due-deadline command may win finalization, never both;
- AI generation occurs outside the write transaction and submits through the same
  commands with expected version/deadline;
- queues become database-derived discovery and notifications only;
- every duplicate movement returns the existing typed outcome; and
- stale deadline work is a no-op without queue, balance, or result changes.

### E1.5 IR private projections and reconnect

Create explicit schemas for:

- assignment/start;
- active assignment/reconnect;
- set tracking;
- voting ballot;
- dashboard and pending result;
- finalized result;
- statistics/leaderboards; and
- admin/operational views.

Before finalization:

- use actor-scoped opaque assignment and entry tokens;
- do not expose other players' IDs, vote IDs, authorship, chosen-entry
  relationships, payout fields, or internal queue/version fields;
- expose only the word to the assigned creator;
- randomize ballot order deterministically per voter without returning canonical
  entry IDs.

Reconnect must restore the same assignment token, word, submitted state, ballot,
vote state, status, and deadline.

### E1.6 IR verification

- pure rule boundary/tie/conservation tests;
- multi-connection assignment, fifth-entry, vote-cap, finalization, and ledger-key
  races;
- duplicate, late, stale, and restart command tests;
- negative disclosure assertions for every pre-finalization response;
- reconnect during assignment, tracking, and voting;
- built-server Rapid loop through assignment, submission, AI/deterministic fill,
  voting, finalization, result, and balance reconciliation;
- Standard-mode deadline test without wall-clock sleeps;
- `npm run build:ir` and every shared-client consumer build.

### E1 gate

- [ ] IR models, schemas, frontend types, and canonical rules agree.
- [ ] Start cannot charge without creating a reconnectable assignment.
- [ ] Entry/vote/finalization races produce one owner and one movement per key.
- [ ] Queue loss and restart preserve claimable work and deadlines.
- [ ] IR privacy, reconnect, SQLite, frontend, and smoke gates pass.

## E2 - MemeMint integrity

### E2.1 Pure MM rules

Create `backend/services/mm/rules.py` and split only genuinely pure calculations:

- image/caption eligibility;
- circle-first partitioning;
- seeded weighted sampling without replacement;
- quality score and retirement decision;
- riff/original classification and deterministic tie handling;
- base and writer-bonus split for original/riff/parent authors;
- per-author circle bonus suppression;
- caption lifetime wallet/vault threshold split;
- first-voter and local-crowd-favorite eligibility;
- free-slot/paid submission pricing; and
- ledger conservation for one completed vote.

Network embedding/moderation adapters may produce inputs for these functions but
must not be imported by the rule module.

### E2.2 MM round and ledger migration

Add to `MMVoteRound`:

- explicit status and lifecycle version;
- authoritative deadline only if retained by the rule decision;
- voted, captioned, closed, and abandoned timestamps;
- command/idempotency references for start, vote, caption, and abandon;
- one active round per player; and
- one caption submission per eligible completed vote round.

Add or strengthen:

- status/kind/caption-parent consistency checks;
- unique `(round_id, player_id)` ownership support;
- unique seen relation `(player_id, caption_id)` (already represented by the
  composite primary key; add direct constraint tests);
- unique accepted caption text normalization per image if duplicate prevention is
  canonical;
- daily-state non-negative/range checks;
- database arbitration for first-vote bonus;
- ledger `idempotency_key` uniqueness; and
- payout attribution columns or a normalized payout-event row sufficient to audit
  round, winning caption, earning caption, earning role, wallet/vault destination,
  and circle suppression.

Migration cleanup must detect duplicate open rounds, multiple accepted submissions
per round, duplicate seen rows, invalid parent links, negative counters, and
ledger/cached-balance divergence.

### E2.3 MM commands

Implement:

- `start_vote_round(player_id, command_id, now, rng)`
- `submit_vote(player_id, round_token, caption_token, command_id, now)`
- `submit_caption(player_id, round_token, text, command_id, now)`
- `abandon_or_expire_round(round_id, expected_version, now)` if retained;
- `retire_caption(caption_id, expected_stats_version, reason, now)`; and
- explicit circle membership commands for create, request, approve, deny, add,
  remove, and leave.

`start_vote_round` must:

- derive eligible images/captions and current circle mates from durable rows;
- select and claim the round inside the decisive transaction;
- atomically charge the entry fee and persist the ordered ballot;
- return a private ballot projection; and
- avoid process-lock correctness.

`submit_vote` must atomically:

- prove ownership, active status/version, deadline, and ballot membership;
- compute pre-vote popularity from the transaction snapshot;
- claim first-voter bonus with one database winner;
- update chosen-caption picks, all shown-caption shows, and seen rows;
- evaluate circle suppression per earning author;
- write all author, parent, voter, and vault movements with unique keys;
- update caption lifetime aggregates;
- transition the round once; and
- return a post-vote reveal projection.

`submit_caption` must atomically:

- prove the round is eligible and has no accepted caption submission;
- persist an external-work intent before embedding/moderation when those calls are
  required;
- accept the completed external result only for the same round/version;
- claim the daily free slot or charge once;
- create the caption and submission record once; and
- transition the round.

### E2.4 MM projections and disclosure

Define:

- vote assignment/reconnect;
- post-vote reveal;
- caption submission state;
- dashboard/availability;
- caption history/statistics;
- circles and membership;
- admin/moderation; and
- balance/ledger summaries.

The pre-vote ballot must omit:

- author username/player ID;
- circle relationship;
- caption kind and parent relationship;
- lifetime earnings and popularity counters;
- canonical caption IDs where correlation is avoidable.

After vote, reveal only the authorship and circle fields allowed by
`MM_CIRCLES.md`. Admin endpoints remain separately authorized and must not be
reused as player projections.

### E2.5 MM circles and admin ownership

- Route every membership mutation through a command with transactional role and
  status checks.
- Use unique membership/request constraints to resolve duplicate approvals and
  simultaneous join/add operations.
- Ensure archived/deleted circles do not affect selection or bonus suppression.
- Prove admin/config/image import paths cannot create an active round, vote,
  payout, or caption outside the owning commands.
- Keep seeding/import scripts explicit operational tools; inspect input before
  execution and make reruns idempotent.

### E2.6 MM verification

- pure selection/scoring/pricing/payout tests with seeded RNG;
- multi-connection start, vote, first-voter, caption/free-slot, and circle
  membership races;
- duplicate and stale movement tests for every payout role;
- ledger-to-wallet/vault/caption aggregate reconciliation;
- restart tests with no process locks or caches;
- pre-vote negative disclosure and post-vote reveal contract tests;
- circle selection and per-author suppression tests through the command boundary;
- built-server loop: start, private ballot, vote, reveal, optional caption,
  balances, history, and reconnect;
- `npm run build:mm` plus all shared consumers.

### E2 gate

- [ ] Concurrent starts create one active round and one charge.
- [ ] One vote produces one set of counters, seen rows, bonuses, and payouts.
- [ ] Caption submission consumes at most one free slot or one fee.
- [ ] Authorship and circle relationships remain hidden until reveal.
- [ ] MM money, circles, SQLite, reconnect, frontend, and smoke gates pass.

## E3 - ThinkLink finalization

### E3.1 Pure TL rules

Create `backend/services/tl/rules.py`:

- phrase-shape and significant-word checks that do not require external services;
- match-boundary classification from supplied similarities;
- unique matched-cluster accumulation;
- strike and terminal-state decision;
- answer and cluster weights;
- weighted coverage;
- payout curve and vault split;
- corpus usefulness and deterministic pruning order; and
- cluster join/new-cluster decision from supplied similarities.

Pass thresholds and tie-break inputs explicitly. Keep embedding generation,
moderation, and topic checks behind adapters.

### E3.2 Immutable snapshot model

Replace mutable-ID-only snapshots with durable snapshot rows:

- `tl_round_snapshot_answer`: round ID, opaque snapshot-answer ID, source answer ID
  for audit, frozen embedding, frozen cluster token, and frozen answer weight;
- `tl_round_snapshot_cluster`: round ID, opaque cluster token, frozen weight; and
- round-level frozen total weight and snapshot version.

Gameplay reads only snapshot rows after start. Source answer edits, pruning,
deactivation, reassignment, or deletion must not alter matching or scoring for an
active round.

Do not expose snapshot/source IDs to the player protocol.

### E3.3 TL lifecycle and ledger migration

Add:

- round lifecycle version and explicit finalizing state;
- one active/finalizing round per player;
- command key or normalized command-result table for retriable start/guess/quit;
- a client guess ID unique within a round;
- finalization key and answer-stat application key;
- ledger movement key uniqueness for entry, payout, vault, and refund;
- status/result consistency checks; and
- indexes for due/active/history reads.

Cleanup queries must classify duplicate active rounds, finalized rows missing
payouts, duplicate payouts, impossible status/result combinations, and snapshots
whose source rows no longer exist.

### E3.4 TL commands and external work

Implement:

- `start_round(player_id, command_id, now, rng)`
- `prepare_guess(player_id, round_token, client_guess_id, text, now)`
- `accept_guess_analysis(round_id, expected_version, client_guess_id, analysis)`
- `quit_round(player_id, round_token, command_id, now)`
- `finalize_round(round_id, expected_version, reason, now)`
- `accept_corpus_answer(...)` if the E0 decision adds guesses to the corpus; and
- `prune_corpus(prompt_id, command_id, now)`.

Start performs prompt selection, immutable snapshot creation, active-round claim,
charge, and assignment in one transaction.

Guess processing uses a two-step command because embedding/moderation is external:

1. `prepare_guess` validates ownership/status, pure phrase rules, duplicate
   client-guess ID, and records a durable analysis intent.
2. External adapters compute moderation, topic, self-similarity, embedding, and
   snapshot matches outside the write transaction.
3. `accept_guess_analysis` conditionally applies the result only if the
   round/version and intent are still current.

The acceptance command inserts one guess, updates matched clusters/strikes, and
either leaves the round active or invokes the single finalization owner.

Finalization conditionally claims `active -> finalizing`, freezes final coverage,
writes payout/vault movements and answer-stat events once, then marks the round
completed. A retry observes and returns the stored result.

Quit uses the same finalizer or a distinct stale-safe abandon transition according
to the resolved rule; it must never race into both refund and payout.

### E3.5 TL projections

Define:

- start/active play;
- reconnect;
- guess outcome;
- finalized result;
- history;
- dashboard/balance; and
- admin corpus health/prune.

Player play/reconnect responses include the prompt text, strikes, coverage,
display-safe matched count, accepted guess history, and durable state needed by
the UI. They omit source answer IDs, cluster IDs, embeddings, weights, prompt ID,
player IDs, command versions, and final answers/matches not yet allowed by the
rules.

Admin corpus projections are separately authorized and bounded; never return raw
embedding vectors.

### E3.6 TL verification

- pure matching-boundary, clustering, coverage, payout, tie, and pruning tests;
- snapshot immutability tests after source edit, prune, deactivate, re-cluster, and
  restart;
- multi-connection start, duplicate guess, third-strike, quit/finalize, finalizer,
  and ledger races;
- stale external-analysis rejection;
- duplicate answer-stat application and ledger reconciliation;
- reconnect at zero guesses, after matches, after strikes, and after finalization;
- negative disclosure tests for play, reconnect, history, result, and admin;
- built-server loop with a deterministic fake embedding adapter from assignment
  through finalized result and balance update;
- remove or convert diagnostic similarity tests/logging;
- `npm run build:tl` plus all shared consumers.

### E3 gate

- [ ] Active rounds use immutable snapshots.
- [ ] Start, guess acceptance, quit, and finalization each have one command owner.
- [ ] Quit/finalize and duplicate-finalizer races cannot double-refund, double-pay,
      or double-apply answer statistics.
- [ ] TL rules, SQLite, privacy, reconnect, frontend, and smoke gates pass.

## E4 - Cross-game auth, host scope, and shared client

### E4.1 One shared client contract

- Extract pure base-URL helpers that accept explicit environment/location inputs.
- An absent production override resolves to `window.location.origin`.
- Strip any one of `/qf`, `/mm`, `/ir`, or `/tl` exactly once from a configured
  root; append only the selected game prefix.
- Derive WebSocket scheme/host from `window.location`.
- Send `game_type` on root auth/session/refresh/logout calls where game-scoped
  player data is required.
- Close and do not retry WebSockets after policy/auth close code `1008`.
- Remove IR's duplicate client/session/WebSocket implementations after all named
  consumers migrate.
- Do not use local storage for access or refresh tokens.

### E4.2 Validated host-to-game scope

Introduce one server host-context resolver:

- exact configured host maps to one `GameType`;
- localhost/test hosts require an explicit test/development policy;
- unknown production hosts are rejected;
- a game-prefixed route verifies that its prefix matches validated host context;
- root auth derives or verifies game scope from host context rather than trusting
  an arbitrary client query alone; and
- WebSocket tokens carry the validated game scope and are rejected on another
  game's channel.

The resolver is used by REST, WebSocket, auth/session, online-user tracking, and
static dispatch. Do not duplicate host inference in middleware and routers.

### E4.3 Cookie and logout contract

- Use shared host-only HttpOnly cookies with explicit secure/same-site settings.
- Verify cookies do not use a parent domain that spans game hosts.
- Logout revokes the presented refresh token and clears the same cookie names/path
  on every game.
- Logging out of one game host must not mutate another host's session.
- Refresh cannot use a token issued for a different host/game scope.
- Guest upgrade preserves the current game's durable active assignment/round.

### E4.4 Error and reconnect contracts

- Shared errors contain stable public codes and bounded user-safe detail.
- Validation errors do not include ORM representations, SQL, embeddings, internal
  IDs, stack traces, or another game's data.
- Every game context boots from `/auth/session` plus its read-only reconnect
  projection.
- Reconnect reads do not create work, charge, reset timers, consume allowances, or
  advance lifecycle.
- Contract tests cover cancellation, one refresh retry, logout on terminal auth
  failure, and no retry loop after `1008`.

### E4.5 Cross-game verification

- host/prefix matrix: four valid pairs and all invalid cross-game pairs;
- auth/session/refresh/logout cookie matrix for all four hosts;
- REST and WebSocket token scope tests;
- shared API base tests for bare and prefixed URLs;
- reconnect contract tests for QF, MM, IR, and TL;
- redacted error-shape tests;
- all four frontend lint/build commands after any shared protocol change; and
- one smoke loop per game against the same built backend.

### E4 gate

- [ ] Host and game scope cannot disagree.
- [ ] One game's cookie/token cannot authorize another game's route or socket.
- [ ] All four clients use the same base, auth, error, and reconnect contracts.
- [ ] The four-game built-server smoke matrix passes.

## Migration and rollout plan

Use separate Alembic revisions per game after shared ledger support lands:

1. shared transaction idempotency primitives from workstream B;
2. IR assignment/lifecycle/constraint migration;
3. MM round/payout/constraint migration;
4. TL immutable snapshot/lifecycle/constraint migration; and
5. optional cleanup revisions only after reconciliation evidence is recorded.

For each revision:

- run read-only duplicate/orphan/balance reports first;
- define repair or quarantine behavior for every violating row;
- rehearse against a production-shaped backup;
- run `upgrade`, application reconciliation, and restore/downgrade checks;
- verify foreign keys and indexes with SQLite pragmas;
- record table-rebuild and data-retention impact; and
- stop if cleanup would discard unclassified money or ownership history.

Use expand/migrate/contract sequencing when a frontend protocol or active row
cannot be changed atomically. Compatibility fields must have a named consumer and
removal issue.

## Proposed delivery slices

Keep each pull request to one behavioral objective:

1. E0 state machines, rule decisions, markers, and failing regressions.
2. IR client/CI model alignment.
3. IR assignment and lifecycle commands.
4. IR finalization, ledger, private projections, and smoke.
5. MM pure rules and regressions.
6. MM round/vote atomicity and private ballot.
7. MM caption/free-slot, circles, payout reconciliation, and smoke.
8. TL pure rules and immutable snapshots.
9. TL command/finalization/ledger migration.
10. TL private projections, reconnect, and smoke.
11. shared client/auth/host isolation and four-game smoke matrix.

Schema and protocol slices may be split further, but do not merge a schema that no
live command uses or a command that lacks its constraint/retry test.

## Required verification

Run focused tests while editing. Before each game phase is reported complete, run:

```bash
pytest -m ir                       # for IR
pytest -m mm                       # for MM
pytest -m tl                       # for TL
pytest -m sqlite_integration
pytest
npm run build:qf
npm run build:mm
npm run build:ir
npm run build:tl
git diff --check
```

Also run:

- the affected built-server smoke loop;
- migration rehearsal and ledger reconciliation for schema/money changes;
- browser verification for changed user-visible or reconnect behavior; and
- the four-game smoke matrix after shared client/auth changes.

Do not describe a marker, smoke command, browser check, or migration rehearsal as
passing until workstream A provides it and it was actually run.

## Independent review

Obtain review before each high-risk phase merges:

- IR: lifecycle/concurrency, money, and disclosure;
- MM: lifecycle/concurrency, money, disclosure, and circles authorization;
- TL: lifecycle/concurrency, immutable snapshot/scoring, money, and disclosure;
- E4: security/auth, WebSocket, and shared-client architecture.

Use two independent reviewers for a slice that spans more than one consequential
high-risk category. Give reviewers the task contract, state-machine page, migration,
and diff before the implementer's rationale. Resolve findings or record them as
explicit blockers.

## Exit criteria

- [ ] IR, MM, and TL each pass pure-rule, lifecycle, privacy, reconnect,
      production-SQLite, reconciliation, frontend, and built-server smoke gates.
- [ ] IR assignment and MM/TL round starts cannot charge without durable ownership.
- [ ] MM and TL finalization cannot duplicate payouts, bonuses, refunds, result
      rows, or statistics.
- [ ] TL active-round scoring is unaffected by later corpus mutation.
- [ ] Shared code changes are verified across all four frontends.
- [ ] Cross-game host/session/API/WebSocket isolation has automated coverage.
- [ ] Migration rehearsal and independent review evidence are recorded.
