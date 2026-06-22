# Private Response Projection

## Status

Accepted.

## Context

These are hidden-information games. A copy player must not see the originating
prompt; a voter must not learn which phrase/entry is the original until the
phraseset/set finalizes. Returning ORM models or over-broad payloads risks leaking
exactly the information the game depends on hiding.

## Decision

Every response is an explicit Pydantic schema that allowlists fields. Internal
SQLAlchemy models are never serialized directly. Before finalization, responses
never disclose authorship, the originating prompt to a copy player, which
phrase/entry is the original to a voter, stable canonical IDs/order that permit
cross-response correlation, or internal lifecycle/queue bookkeeping. When a later
command needs a reference to hidden state, the server issues an opaque,
actor-scoped assignment token.

## Consequences

Each endpoint and reconnect/resync path needs an explicit projection, and disclosure
is tested with negative assertions (forbidden fields absent), not only happy-path
shape. Tests also attempt correlation across list/detail/reconnect responses. A
protocol change is incomplete until both normal and reconnect responses are covered.

## Rejected alternatives

Returning ORM models; relying on the frontend not to render hidden fields; sharing
internal models to avoid duplicating schemas.

## Conditions for revisiting

Only if a mechanism provably prevents pre-finalization disclosure with equal or
stronger guarantees.
