# Workstream D - QuipFlip Party Mode

> **Document type:** Implementation plan
> **Status:** Active
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Objective

Make Party Mode a server-authoritative, deadline-driven, reconnect-safe
multi-client lifecycle with stale-command rejection and deterministic tests.

## Starting point

Party Mode has a separate backend and frontend surface. Current phase advancement
contains incompatible async/synchronous lock usage and lacks direct regression
coverage. In-flight branch intent exists in `party-refactor` and
`refactor-round-names`, but those branches are evidence to reconcile, not changes
to merge blindly.

## Dependencies and boundaries

- Requires workstream A's deterministic/fake-clock and built-server smoke support.
- Uses workstream B's lifecycle versions, conditional commands, and explicit
  projections.
- QF solo behavior belongs in workstream C.
- Preserve intended behavior from the
  [Party documentation](../quipflip/party/party_overview.md), resolving conflicts
  against running code and tests explicitly.

## Repository anchors and gotchas (verified 2026-06-22)

- **The branches are on the `gh-quipflip` remote, not `origin`.** This checkout's
  only remote is `gh-quipflip` (`https://github.com/sheegaon/quipflip.git`). Inspect
  with `git log --stat gh-quipflip/party-refactor` and
  `git log --stat gh-quipflip/refactor-round-names` (D0); there is no
  `origin/party-refactor`.
- **The broken-lock site is exact: `backend/services/qf/party_session_service.py:959`**
  uses `async with lock_client.lock(...)` against a synchronous `@contextmanager`
  (`backend/utils/lock_client.py`), which raises `AttributeError` whenever that path
  runs — which is why it has no working test today (roadmap finding 6). This is D1's
  "replace broken synchronous lock usage."
- **Party state and services are already substantial.** Models:
  `backend/models/qf/{party_session,party_participant,party_round,party_phraseset}.py`
  (`party_phraseset` already has `uq_party_phrasesets_session_phraseset`). Services:
  `backend/services/qf/{party_session_service,party_coordination_service,party_scoring_service,party_websocket_manager}.py`
  — these are the oversized boundaries D2 splits along command/projection/rule lines.
  Docs: `docs/quipflip/party/{architecture-overview,party_api,party_services,party_data_models_and_schemas,party_overview}.md`.
- **A leftover `backend/migrations/cleanup_party_tables.sql` exists** — confirm its
  status and whether it is still referenced during D0.
- **Existing coverage**: `tests/test_party_session_service.py` and `tests/party/`;
  reconcile rather than replace.
- Implements [ADR 0001](../decisions/0001-server-authoritative-lifecycle.md) and
  [ADR 0002](../decisions/0002-private-response-projection.md).

## Implementation blueprint

### Behavioral contract

The implementation should preserve the existing Party match shape while replacing
its coordination mechanism:

```text
LOBBY --start--> PROMPT --complete/timeout--> COPY
      --expire--> ABANDONED                  |
                                               --complete/timeout--> VOTE
                                                                     |
                                               RESULTS <---finalize---+
```

- `PartySession.status` is the aggregate status:
  `OPEN | IN_PROGRESS | COMPLETED | ABANDONED`.
- `PartySession.current_phase` is the non-terminal presentation phase:
  `LOBBY | PROMPT | COPY | VOTE | RESULTS`.
- Completion is represented by `status=COMPLETED, current_phase=RESULTS`; do not
  retain the current extra `RESULTS -> COMPLETED` phase transition.
- `LOBBY` and `RESULTS` are untimed unless a separately approved product rule adds
  a lobby/results timeout. `PROMPT`, `COPY`, and `VOTE` have durable deadlines.
- A participant's membership, readiness, assignments, submissions, and votes are
  durable facts. Socket presence is a separate hint and cannot alter any of them.
- Every command receives the actor, session ID, an idempotency key, and the
  expected lifecycle version when it can race with a phase transition.
- A duplicate command returns the original successful result. A stale command
  returns a typed `stale_party_version` conflict. A command that is validly repeated
  after its effect is visible returns a typed no-op rather than mutating again.
- Notifications are emitted only after commit and carry the resulting lifecycle
  version. They prompt clients to refetch a projection; they are not lifecycle
  authority.

The current code does not define Party phase durations or what incomplete human
slots do at a phase deadline. Those are game rules, not implementation details.
Before D1/D2 merge, approve and document:

1. `party_prompt_phase_seconds`, `party_copy_phase_seconds`, and
   `party_vote_phase_seconds`.
2. Whether a deadline forfeits incomplete slots, fills them with AI, or abandons
   the match.
3. Who pays for an AI-filled slot and whether the original participant receives
   any payout/credit.
4. Whether an explicit mid-game leave forfeits the player's remaining slots or
   keeps the participant eligible to reconnect.

Until those decisions are approved, implement the state/version/deadline machinery
and test it with injected policy objects; do not choose economy or forfeiture
behavior implicitly.

### Current mutation inventory and target owner

| Current caller | Current mutation | Target command |
| --- | --- | --- |
| `POST /party/create` | session + host participant | `create_party_session` |
| `POST /party/join`, `POST /party/{id}/join` | participant insert | `join_party_session` |
| `POST /party/{id}/ready` | participant readiness | `set_party_ready` |
| `POST /party/{id}/add-ai` | AI player + participant | `add_party_ai_participant` |
| `POST /party/{id}/start` | status/phase + participant status | `start_party_session` |
| `POST /party/{id}/leave` | participant/session deletion | `leave_party_session` |
| `POST /party/{id}/rounds/*` | core round + party link | `claim_party_assignment` |
| `POST /rounds/{id}/submit` | core submission + counter + phase advance | `submit_party_phrase` |
| `POST /phrasesets/{id}/vote` | vote + counter + phase advance | `submit_party_vote` |
| `POST /party/{id}/process-ai` | direct AI orchestration | `request_party_ai_fill` |
| `PartyCoordinationService` | three copies of auto-advance | `advance_party_phase` |
| `PartyCoordinationService.process_ai_submissions` | start/submit/advance loop | AI job runner calling normal commands |
| Party WebSocket connect/disconnect | presence, readiness, activity | `record_party_presence` only |
| `QFCleanupService` | deletes inactive participants | remove; use expiry commands |
| `party_maintenance` | expires sessions and deletes participants | `expire_party_session`, due-phase commands |
| logout cleanup | deletes active membership | `record_party_presence` or explicit leave only |

`PartySessionService.advance_phase`, `advance_phase_atomic`,
`increment_participant_progress`, `link_round_to_party`, and
`link_phraseset_to_party` are transitional APIs. Delete them after all callers use
the commands above.

### State-machine command matrix

| Command | Actor | Expected state | Durable effect | Duplicate/stale result |
| --- | --- | --- | --- | --- |
| create | authenticated player | no active membership | create `OPEN/LOBBY` session and host membership | replay original session |
| join | authenticated player | `OPEN/LOBBY`, capacity available | insert membership | return existing same-session membership; conflict for another active session |
| ready | participant | `OPEN/LOBBY` | set durable `ready_at`/readiness | no-op when already ready |
| add AI | host | `OPEN/LOBBY`, capacity available | reserve AI identity and insert ready membership | replay inserted participant |
| start | host | expected `OPEN/LOBBY/version` | CAS to `IN_PROGRESS/PROMPT`, set deadline, freeze roster | stale conflict or replay |
| claim assignment | participant/AI runner | expected phase/version, slot available | create or return one core round bound to one slot | return existing active assignment |
| submit phrase | assignment owner | assignment active, matching phase/version, before grace cutoff | core submission, complete slot, optionally enqueue phase advance | replay submitted projection |
| submit vote | assignment owner | vote assignment active, matching phase/version | core vote, complete slot, optionally enqueue finalization | replay submitted projection |
| advance | system after submission | all required slots settled, expected phase/version | CAS next phase, create deadline/jobs | no-op if already advanced; stale conflict for mismatched version |
| timeout | scheduler/system | expected phase/version/deadline and `now >= deadline` | settle incomplete slots according to approved policy, then CAS phase | stale no-op |
| accept AI fill | AI runner | persisted job still matches phase/version/slot | submit through the normal assignment command | stale result rejected |
| finalize | system | `VOTE`, all vote slots settled or timeout policy complete | finalize Party results once, CAS to `COMPLETED/RESULTS` | return existing final result |
| leave | participant | lobby, or approved mid-game policy | lobby removal/host reassignment; never implicit on disconnect | replay leave result |
| expire session | scheduler/admin | expected status/version and inactivity deadline | CAS to `ABANDONED`; settle active core rounds through owning commands | stale no-op |

The command layer should return typed outcomes:

```python
PartyCommandOutcome = Applied[T] | Replayed[T] | NoOp[T]
```

Expected failures should be typed domain errors mapped centrally by the router:
`party_not_found`, `not_party_member`, `not_party_host`, `party_full`,
`wrong_party_phase`, `stale_party_version`, `party_deadline_passed`,
`party_assignment_unavailable`, and `party_command_conflict`.

### Schema and migration

Add one Alembic migration after workstream B's SQLite pragma/cleanup work. Rehearse
it against a production-shaped copy before enabling the new commands.

#### `party_sessions`

Add:

- `lifecycle_version INTEGER NOT NULL DEFAULT 0`
- `phase_expires_at DATETIME NULL` (the model already declares it, but the migration
  chain and production schema must be verified before relying on it)
- `roster_locked_at DATETIME NULL`; migrate `locked_at` into this field or document
  `locked_at` as its canonical name
- `abandoned_at DATETIME NULL`
- `abandon_reason VARCHAR(40) NULL`

Add checks:

- allowed `status`
- allowed `current_phase`
- positive min/max/quota values and `min_players <= max_players`
- `phase_expires_at IS NOT NULL` for `IN_PROGRESS` timed phases
- terminal timestamps agree with terminal status

Add an index for deadline discovery:

```text
(status, current_phase, phase_expires_at, lifecycle_version)
```

#### `party_participants`

Keep `(session_id, player_id)` unique. Separate durable membership from presence:

- replace overloaded `status` with `membership_status`:
  `JOINED | READY | ACTIVE | LEFT | FORFEITED | COMPLETED`
- retain `connection_status`, `disconnected_at`, and `last_activity_at` only as
  presence/diagnostic fields
- add `left_at`, `forfeited_at`, and optional `forfeit_reason`

Do not delete in-progress participant rows. Historical rounds and result attribution
depend on them.

Enforce one active Party membership per player with a SQLite-compatible
denormalized `active_membership` boolean plus partial unique index:

```text
UNIQUE(player_id) WHERE active_membership = 1
```

Commands clear this flag when a session becomes terminal or a lobby member leaves.

The three submitted counters may remain as cached projection fields during
migration, but command tests must reconcile them against settled assignment rows.
Once all reads use assignment rows, either remove the counters or keep them as
explicitly documented caches updated in the same transaction.

#### `party_rounds`

Make this the durable assignment record rather than only a link:

- `phase_version INTEGER NOT NULL`
- `slot_index INTEGER NOT NULL`
- `assignment_status VARCHAR(20) NOT NULL`:
  `ASSIGNED | SUBMITTED | EXPIRED | FORFEITED`
- `assignment_token_hash VARCHAR(64) NOT NULL`
- `assigned_at`, `settled_at`
- optional `ai_job_id`

Constraints:

- unique `(session_id, participant_id, phase, phase_version, slot_index)`
- unique `round_id`
- check that `round_type` matches `phase`
- unique `assignment_token_hash`

The client receives an opaque signed assignment token, never `party_round_id`.
Submission resolves that token back to the actor, session, phase version, slot, and
core round.

#### New `party_command_receipts`

Store retriable command results:

- `receipt_id`
- `session_id`
- `actor_player_id` nullable for system commands
- `command_name`
- `idempotency_key`
- `expected_version`
- `result_code`
- bounded JSON result sufficient to replay the public response
- `created_at`

Unique `(command_name, actor_player_id, idempotency_key)`. System deadline keys use
the stable format:

```text
party:{session_id}:phase:{phase}:version:{version}:timeout
```

#### New `party_ai_jobs`

Persist AI intent before network work:

- `job_id`, `session_id`, `participant_id`, `phase`, `phase_version`, `slot_index`
- `status`: `PENDING | RUNNING | SUCCEEDED | FAILED | STALE`
- `attempt_count`, `available_at`, `lease_expires_at`
- prompt/input reference that does not duplicate hidden plaintext unnecessarily
- generated result only if operationally required and with bounded retention
- `created_at`, `completed_at`, `last_error_code`

Unique `(session_id, participant_id, phase, phase_version, slot_index)`. A job
runner leases due rows, performs AI/network work outside a write transaction, then
submits through `accept_party_ai_fill`. A phase/version mismatch marks the result
`STALE` without modifying gameplay or money.

#### Cleanup before constraints

The migration must report and resolve:

- duplicate active memberships for one player
- duplicate party-round links
- party rounds whose participant belongs to another session
- terminal sessions with non-terminal participants
- invalid phase/status combinations
- missing `phase_expires_at` for in-progress timed phases
- orphaned Party rows exposed by `foreign_keys=ON`

Delete `backend/migrations/cleanup_party_tables.sql`. It is an unguarded destructive
historical repair script, is not referenced by runtime code, and conflicts with the
Alembic-only migration rule.

### Backend module layout

Split by responsibility without moving unrelated QF solo code:

```text
backend/services/qf/party/
  commands.py          # public transactional commands
  command_types.py     # outcomes and domain errors
  rules.py             # pure phase/eligibility/deadline decisions
  projections.py       # actor-scoped response builders
  assignments.py       # internal assignment selection helpers
  ai_jobs.py           # durable job discovery/lease/result acceptance
  deadlines.py         # due-row discovery only
  events.py            # post-commit notification payloads
  scoring.py           # pure aggregation + final result persistence
  presence.py          # presence writes, never lifecycle writes
```

Keep compatibility imports in `backend/services/qf/__init__.py` only while callers
are migrated, with a named removal issue. Do not preserve the existing broad
services as permanent forwarding layers.

`rules.py` should be synchronous and receive all inputs explicitly:

- `next_phase(current_phase)`
- `phase_duration(phase, policy)`
- `required_slots(session_config, phase)`
- `participant_phase_complete(assignments, required_slots)`
- `session_phase_complete(participants, assignments, policy)`
- `can_claim_slot(...)`
- `deadline_resolution(...)`

Commands receive an injected clock. Random assignment ordering receives an injected
seed/RNG. No Party module should call `datetime.now`, `random`, or `asyncio.sleep`
directly.

### Transaction boundaries

Each command owns one short transaction and rechecks all state inside it. The core
pattern is:

```sql
UPDATE party_sessions
SET current_phase = :next_phase,
    lifecycle_version = lifecycle_version + 1,
    phase_started_at = :now,
    phase_expires_at = :deadline
WHERE session_id = :session_id
  AND status = 'IN_PROGRESS'
  AND current_phase = :expected_phase
  AND lifecycle_version = :expected_version;
```

Exactly one updated row is the winner. A zero-row result is classified by rereading
the session as replay/no-op/stale conflict.

Starting and submitting a Party round must not be “core commit, Party commit” as it
is today. The QF solo commands from workstream C must support caller-owned
transactions (or an equivalent unit-of-work API) so the core round, ledger entries,
Party assignment, and Party command receipt commit atomically. No notification,
AI call, phrase-validator network request, or WebSocket send occurs inside that
write transaction.

When a successful submission makes the phase complete, either:

1. perform the phase CAS in the same transaction, or
2. insert a uniquely keyed durable `advance` intent in that transaction and let a
   worker call `advance_party_phase`.

Prefer option 1 when next-phase setup is database-only. Use option 2 when the
approved policy requires slow preparation. Do not rely on an untracked
`asyncio.create_task`.

### Deadlines and restart recovery

Add a Party due-work cycle that queries durable rows:

```text
status = IN_PROGRESS
phase in (PROMPT, COPY, VOTE)
phase_expires_at <= clock.now()
```

For each row, call `timeout_party_phase(session_id, phase, version, deadline)`.
The command rechecks all four values in its transaction. Repeated discovery,
multiple scheduler calls, and restart after commit are safe.

On application startup, run one bounded due-work pass before entering the periodic
loop. Do not reconstruct lifecycle state from socket connections, in-memory queues,
or pending tasks.

Existing per-round expiry remains authoritative for a claimed core round. Party
phase timeout must settle or abandon those rounds by calling the owning QF round
timeout command so refunds and queue effects stay idempotent. The phase deadline
does not create a second refund implementation.

### Reconnect, presence, and leave semantics

WebSocket connect/disconnect may update only:

- `connection_status`
- `disconnected_at`
- `last_activity_at`

Remove the current behavior that marks a lobby participant ready on connect and
unready on disconnect. Remove cleanup that deletes a participant after 5 or 30
minutes disconnected. Logout revokes auth and records presence; it does not leave an
in-progress Party.

Reconnect is a normal authenticated projection request:

```text
GET /party/{session_id}/state
```

It returns the actor's current session/version/deadline, membership, settled counts,
and existing active assignment if one exists. The frontend resumes that assignment
instead of starting a new round. If the phase advanced while disconnected, it
returns the new phase and no stale assignment.

An explicit leave remains a command. Lobby leave removes or tombstones membership
and reassigns the host transactionally. Mid-game leave follows the approved
forfeit/reconnect policy; navigation and socket closure are never treated as leave.

### Explicit projections and disclosure

Replace `Dict` response fields and ORM-derived dictionaries in
`backend/schemas/party.py` with typed schemas:

- `PartyLobbyHostProjection`
- `PartyLobbyParticipantProjection`
- `PartyGameplayProjection`
- `PartyReconnectProjection`
- `PartySpectatorProjection`
- `PartyAssignmentProjection`
- `PartyResultsProjection`
- `PartyEventEnvelope`

Common gameplay fields:

- `session_id`, `status`, `phase`, `lifecycle_version`
- `server_time`, `phase_started_at`, `phase_expires_at`
- actor's membership/readiness and settled/required counts
- aggregate participant progress
- optional actor-scoped active assignment

Host-only fields include start eligibility and lobby controls. Spectators receive
room metadata, phase/deadline, aggregate progress, and public display names only.
Until an authenticated spectator endpoint is deliberately exposed, use this schema
for internal tests and keep in-progress status endpoints member-only.

Before results, no projection or event may include:

- contributor/authorship relationships
- the originating prompt shown to a copy player
- which vote candidate is original
- another player's active assignment or wallet
- internal `party_round_id`, core contributor IDs, canonical candidate order, AI job
  IDs, command receipts, or lifecycle bookkeeping

The current `GET /party/{id}/status` does not verify membership and the current
round-start responses expose internal Party IDs. Both must be removed or versioned.
WebSocket events should carry `{type, session_id, lifecycle_version}` plus a minimal
hint such as `state_changed`; clients refetch their actor-scoped projection.

### REST and WebSocket contract

Keep existing URLs where semantics remain sound, but require `Idempotency-Key` for
mutating requests and `expected_version` in phase-sensitive bodies.

Add:

- `GET /party/{session_id}/state` — member/reconnect projection
- `GET /party/{session_id}/spectate` — optional read-only spectator projection
- `POST /party/{session_id}/assignments/claim`
- `POST /party/{session_id}/assignments/{assignment_token}/submit`

Deprecate and then remove:

- phase-specific round-start endpoints after the generic claim command is live
- the stub `POST /party/{session_id}/rounds/{round_id}/submit`
- direct Party detection/mutation in `routers/qf/rounds.py` and
  `routers/qf/phrasesets.py`
- host-triggered `process-ai` as a correctness mechanism

The WebSocket accepts no gameplay commands. Authentication should use the standard
short-lived QF WebSocket token and policy close code `1008`; reconnect always
follows with `GET .../state`.

### Frontend implementation

Make one server snapshot the source of truth in `PartyModeContext`:

```ts
type PartySnapshot = {
  sessionId: string;
  status: PartyStatus;
  phase: PartyPhase;
  lifecycleVersion: number;
  serverTime: string;
  phaseExpiresAt: string | null;
  membership: PartyMembership;
  progress: PartyProgress;
  activeAssignment: PartyAssignment | null;
};
```

- Do not persist authoritative progress, phase, or assignment payloads in
  `localStorage`. At most persist the session ID as a navigation convenience.
- `PartyGame` first fetches `/state`; it resumes `activeAssignment`, claims the next
  slot only when none exists, or routes to results.
- `PartyRoundModal` renders `phase_expires_at - estimatedServerOffset`; reaching
  zero disables local input and refetches, but does not advance the phase.
- A WebSocket event triggers a coalesced state refetch. Keep bounded polling as a
  fallback when disconnected.
- A stale response causes a state refetch and route correction, not a client-side
  phase transition.
- Remove the current assumption that closing the socket removes the player.
- Keep QF naming changes out of this workstream; reject the
  `refactor-round-names` branch for D.

Update the shared API types to discriminated, explicit projection types. Remove
`Record<string, unknown>`, broad `Dict`, and optional response fields used to hide
backend shape drift.

### Historical branch reconciliation

`gh-quipflip/party-refactor` contains one reusable intent: AI/network work must not
block a player HTTP response and needs its own database session. Adapt that intent
to durable `party_ai_jobs`; reject its raw `asyncio.create_task` implementation
because tasks disappear on restart and have no stale phase/version guard.

Reject the branch's lock-timeout/backoff work as a correctness mechanism. Bounded
SQLite busy retries may remain infrastructure behavior, but command correctness
comes from constraints, receipts, and CAS.

`gh-quipflip/refactor-round-names` is a broad frontend terminology rename in the old
`qf_frontend` tree. It does not solve Party lifecycle ownership and should not be
merged or cherry-picked into D.

### Delivery sequence

Implement as reviewable pull requests. Do not combine the migration, command
cutover, frontend rewrite, and cleanup into one diff.

1. **D0 inventory and regression capture**
   - Commit the command/caller diagram and branch decisions.
   - Add failing regressions for broken `advance_phase_atomic`, disconnect changing
     readiness, disconnected-participant deletion, duplicate submissions, and
     unauthorized status reads.

2. **D1 schema, rules, and CAS**
   - Add migration, clock/policy interfaces, pure rules, typed outcomes, and
     multi-connection CAS tests.
   - Keep old routers temporarily, but make new phase commands available behind
     tests.

3. **D2 lobby commands and projections**
   - Migrate create/join/ready/add-AI/start/leave and actor-scoped lobby/state reads.
   - Make WebSocket presence lifecycle-neutral.

4. **D2 assignment and submission commands**
   - Add durable slots/tokens/receipts.
   - Cut Party mutations out of the generic QF routers.
   - Reconcile Party counters against assignment rows.

5. **D2 deadlines, AI jobs, and finalization**
   - Add due-row discovery, timeout command, durable AI worker, stale-result
     rejection, restart recovery, and idempotent results persistence.

6. **D3 frontend reconnect cutover**
   - Replace local progression with snapshot/resume behavior.
   - Render server deadlines and minimal WS invalidations.
   - Remove deprecated frontend API paths after the backend cutover.

7. **D4/D5 verification and deletion**
   - Add complete deterministic, concurrency, disclosure, built-server, and browser
     coverage.
   - Delete old services, destructive SQL, duplicate cleanup, broad schemas, and
     compatibility paths.

Each pull request needs a single behavioral objective and must leave production
deployable. Use a temporary feature flag only if old and new clients must overlap;
name the consumer and removal condition.

### Test plan

#### Pure rules

- valid and invalid phase transitions
- required slot calculation for each session configuration
- completion with humans, AI, forfeited slots, and deadline policy
- deadline calculation using a fake clock
- deterministic assignment eligibility and self-content exclusion

#### Command integration

- create/join/ready/start authorization and idempotent replay
- one active membership per player
- one assignment per participant/phase/version/slot
- duplicate start/submit/vote does not double-charge or increment progress
- stale version cannot claim, submit, advance, timeout, or accept AI output
- exactly one concurrent phase CAS winner across multiple SQLite connections
- timeout rerun does not double-refund, requeue, fill, or finalize
- finalization rerun does not double-pay
- cached counters reconcile with assignment rows and ledger balances

#### Reconnect and disclosure

For LOBBY, PROMPT, COPY, VOTE, and RESULTS:

- disconnect, destroy all in-memory socket state, and reconnect
- assert membership, readiness, assignment, submission/vote state, deadline, and
  version are unchanged
- assert reconnect returns the existing assignment rather than charging for another
- assert forbidden authorship, hidden prompt, original identity, stable candidate
  order, internal IDs, and other players' private data are absent
- assert non-members cannot read the member state projection

#### AI and restart

- AI job is committed before external work
- fake AI completes through the normal command path
- result after phase advancement is marked stale with no money/progress change
- lease expiry permits safe retry
- restart with no asyncio tasks or socket state discovers due jobs/deadlines

#### Built server and browser

- host plus at least two participant browser contexts
- create/join/ready/start through results
- one mid-phase disconnect/reconnect
- one duplicate mutation using the same idempotency key
- one stale expected version
- one deadline transition under a shortened test policy
- responsive lobby/game/results views and countdown behavior
- captured diagnostics contain no token, phrase authorship, or private player data

### Definition of done by file area

Expected additions/changes include:

- `backend/models/qf/party_*.py`
- one new Alembic migration
- `backend/services/qf/party/`
- `backend/routers/qf/party.py`
- removal of Party mutation branches from `backend/routers/qf/rounds.py` and
  `backend/routers/qf/phrasesets.py`
- `backend/tasks/party_maintenance.py` reduced to due-work discovery
- `backend/schemas/party.py`
- `frontend/crowdcraft/src/api/{client,types}.ts`
- `frontend/qf/src/{contexts,hooks,pages,components/party}/`
- deterministic tests under `tests/party/`
- production-SQLite tests in the workstream A integration tier
- a Party Playwright smoke using the existing `tests/e2e/` infrastructure
- updated Party API/model/architecture docs after the protocol cutover

Deliberately avoid unrelated QF terminology renames, non-Party UI restyling, and a
new generic room framework.

## Phase D0 - Reconcile intent and current ownership

- [ ] Inspect `party-refactor` without merging it.
- [ ] Inspect `refactor-round-names` without merging it.
- [ ] Record reusable intent, obsolete assumptions, and conflicts with current
      code.
- [ ] Complete the Party state/phase diagram with commands, actors, deadlines, and
      reconnect projections.
- [ ] Inventory REST, WebSocket, scheduler, AI-fill, admin, and startup mutation
      callers.
- [ ] Identify duplicated phase-advance logic and oversized service boundaries.
- [ ] Define participant identity and reconnection rules.

Gate:

- [ ] Every Party mutation maps to one intended command and every remote-branch
      idea has an explicit keep, adapt, or reject decision.

## Phase D1 - Phase/version and deadline model

- [ ] Add an authoritative phase and monotonic lifecycle version.
- [ ] Persist an authoritative deadline for every timed phase.
- [ ] Define valid command/phase/version combinations.
- [ ] Implement conditional phase advancement with one winner.
- [ ] Make duplicate and stale advancement explicit no-ops or typed conflicts.
- [ ] Replace broken synchronous lock usage in async paths.
- [ ] Ensure socket presence never advances or rewinds lifecycle state.
- [ ] Add database constraints for session membership and per-round assignment
      uniqueness.

Gate:

- [ ] Concurrent or repeated phase commands cannot skip, repeat, or rewind a phase.

## Phase D2 - Command ownership and durable orchestration

- [ ] Implement one command each for join, ready, start, submit, vote, advance,
      timeout, AI-fill acceptance, and finalization.
- [ ] Route REST endpoints through those commands.
- [ ] Route WebSocket messages through those commands or read-only projections.
- [ ] Route deadline discovery through those commands.
- [ ] Persist AI-fill intent and reject results for stale phases.
- [ ] Keep network/AI work outside write transactions.
- [ ] Publish notifications only after commit.
- [ ] Split services along command, projection, and pure-rule boundaries while
      migrating covered behavior.

Gate:

- [ ] No router, socket handler, or scheduler performs an independent Party state
      mutation.

## Phase D3 - Reconnect and private projections

- [ ] Define explicit host, participant, spectator, and reconnect projections.
- [ ] Restore the same participant identity after reconnect.
- [ ] Restore assignment, submission, counters, vote state, allowances, phase, and
      deadline.
- [ ] Keep disconnect/reconnect presence separate from lifecycle eligibility.
- [ ] Prevent duplicate joins and duplicate commands after reconnect.
- [ ] Assert hidden prompts, authorship, and original-entry identity remain private.
- [ ] Reject stale client phase/status updates.
- [ ] Update the Party frontend to render server deadlines and projections.

Gate:

- [ ] Disconnecting and reconnecting during every phase preserves authoritative
      state and does not disclose hidden information.

## Phase D4 - Deterministic lifecycle tests

- [ ] Add fake-clock tests for join and ready.
- [ ] Add fake-clock tests for host start and phase deadlines.
- [ ] Add tests for prompt/caption submission and voting.
- [ ] Add tests for disconnect and reconnect in every phase.
- [ ] Add tests for duplicate REST and WebSocket commands.
- [ ] Add tests for stale phase/version commands.
- [ ] Add tests for timeout, AI fills, stale AI results, and finalization.
- [ ] Add multi-client tests for simultaneous commands.
- [ ] Add restart recovery tests with socket state absent.

Gate:

- [ ] The full Party lifecycle passes without wall-clock sleeps or external AI.

## Phase D5 - Built-server and browser verification

- [ ] Add a multi-client built-server Party smoke through results.
- [ ] Include a mid-phase disconnect/reconnect.
- [ ] Include a stale phase command and verify rejection.
- [ ] Include a duplicate command and verify idempotent behavior.
- [ ] Verify host and participant views in an actual browser.
- [ ] Verify responsive interaction and socket recovery.
- [ ] Record bounded diagnostics without tokens or private player data.

Gate:

- [ ] A multi-client Party smoke completes through results with reconnect and stale
      command coverage.

## Required verification

- [ ] Run Party pure-rule and fake-clock tests.
- [ ] Run production-shaped SQLite concurrency tests.
- [ ] Build the QF frontend.
- [ ] Run the Party built-server smoke.
- [ ] Perform browser verification.
- [ ] Obtain independent lifecycle/WebSocket and disclosure reviews.

## Exit criteria

- [ ] Phase/version/deadline state is durable and server-authoritative.
- [ ] Reconnect restores rather than resets.
- [ ] One command owns each transition across REST, WebSocket, jobs, and AI.
- [ ] Multi-client smoke proves completion, reconnect, duplicate, and stale paths.

## Non-goals

- Blindly merging historical Party branches.
- Replacing Party Mode with a new room framework.
- A mechanical service rewrite without behavior-preserving tests.
