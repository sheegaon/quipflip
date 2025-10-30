# Guest Account Plan

## What to allow (guest capabilities)

* Full core loop: Prompt / Copy / Vote, timers, payouts, and results.
* Auto-generated display name (you already do this).
* Auto-generated email `guest[1234]@quipflip.xyz` where [1234] is a random string of 4 numbers and password `QuipGuest`

## Nudge to convert

* Custom first tutorial screen notifying user of their auto-generated email and password and instructions on how to upgrade (see below).


## Backend changes

* **Player model**: add `is_guest: bool` (default `false`).
* **Create guest**: add `POST /player/guest` that:

  * Creates a `Player` with `is_guest=true`, random email/password, same starting balance and pseudonym generation.
  * Issues access + refresh JWTs exactly like normal accounts (short access, long refresh).
* **Upgrade guest**: add `POST /player/upgrade` that accepts `{email, password}`.

  * Validates uniqueness, sets credentials, flips `is_guest=false`, continues same `player_id` (balance, stats, outstanding rounds preserved).
  * Returns a fresh token pair.
* **Rate limits** (guest scope): per-IP + per-device (fingerprint/cookie) buckets that are stricter than for registered users.

## Frontend changes

* Landing screen: two primary CTAs
  **Play instantly (no sign-up)** → calls `/player/guest` and stores tokens.
  **Sign in / Create account** → your current email/password path.
* Storage: keep using access token in memory/localStorage and refresh token via HTTP-only cookie.
* “Upgrade” flow UX: a simple card to input email and password on the statistics page.

## Security & anti-sybil checklist

* Per-IP + per-device rate limiting (stricter for guests).
* Do not allow voting on phrasesets created in the last hour.

## Analytics to watch

* Guest start → first submission rate.
* Guest → upgrade conversion rate (overall and by trigger point).
* Retention D1/D7 for guests vs registered.
* Abuse flags: guest vote velocity, duplicate device/IP patterns.
* Impact on queue health (copy/vote depth) and economics.

## Rollout order (1 sprint)

1. Backend: `/player/guest`, `/player/upgrade`, `is_guest` flag; add guest-scoped rate limits.
2. Frontend: “Play Instantly” CTA, upgrade banner, simple upgrade modal.