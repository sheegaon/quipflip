# Guest Account Plan

## What to allow (guest capabilities)

* Full core loop: Prompt / Copy / Vote, timers, payouts, and results.
* Auto-generated display name (you already do this).
* Local persistence only (lose access if they clear storage or switch devices).

## What to gate (nudge to convert)

* Daily bonus after day 1 (e.g., let them claim the first bonus only).
* Leaderboards, friend features, and advanced stats.
* API key/refresh recovery (warn they can lose progress).
* Any high-throughput behavior (see abuse controls below).

## Backend changes

* **Player model**: add `is_guest: bool` (default `false`). Keep `email`/`password_hash` nullable.
* **Create guest**: add `POST /player/guest` that:

  * Creates a `Player` with `is_guest=true`, no email/password, same starting balance and pseudonym generation.
  * Issues access + refresh JWTs exactly like normal accounts (short access, long refresh).
* **Upgrade guest**: add `POST /player/upgrade` that accepts `{email, password}`.

  * Validates uniqueness, sets credentials, flips `is_guest=false`, continues same `player_id` (balance, stats, outstanding rounds preserved).
  * Returns a fresh token pair.
* **Rate limits** (guest scope): per-IP + per-device (fingerprint/cookie) buckets that are stricter than for registered users.
* **Abuse rules** (guest scope):

  * Hard cap on concurrent active rounds (e.g., 1), and lower “outstanding prompts” ceiling (e.g., 3–5 vs 10).
  * Optional CAPTCHA on bursty actions (e.g., repeated /rounds/vote).
  * Minimum account age or velocity checks before allowing repeated voting on different sets.
  * Keep your existing “no self-voting” and one-vote-per-phraseset rules.

## Frontend changes

* Landing screen: two primary CTAs
  **Play instantly (no sign-up)** → calls `/player/guest` and stores tokens.
  **Sign in / Create account** → your current email/password path.
* Storage: keep using access token in memory/localStorage and refresh token via HTTP-only cookie. Make it clear to guests that “progress is on this device only.”
* Conversion moments (modal or banner):

  * After first completed phraseset (“Save your progress—add an email”).
  * When trying to claim day-2 daily bonus.
  * When opening gated features (leaderboard, export, stats).
* “Upgrade” flow UX: a simple in-app dialog; on success, silently rehydrate context from the new tokens.

## Security & anti-sybil checklist

* Per-IP + per-device rate limiting (stricter for guests).
* Soft-limits that escalate to CAPTCHA if tripped.
* Cool-downs between creating a guest and voting on the same user’s phraseset.
* Velocity heuristics (e.g., unusual vote streaks across many phrasesets).
* Continue forbidding contributors from voting on their own set (already in place).

## Analytics to watch

* Guest start → first submission rate.
* Guest → upgrade conversion rate (overall and by trigger point).
* Retention D1/D7 for guests vs registered.
* Abuse flags: guest vote velocity, duplicate device/IP patterns.
* Impact on queue health (copy/vote depth) and economics.

## Rollout order (1 sprint)

1. Backend: `/player/guest`, `/player/upgrade`, `is_guest` flag; add guest-scoped rate limits.
2. Frontend: “Play instantly” CTA, upgrade banner, simple upgrade modal.
3. Analytics + guardrails: event tracking + basic CAPTCHA hook.
4. Tune gates based on data (e.g., when to prompt upgrade).

## Trade-offs (brief)

* **Pros**: Lower friction, faster aha moment, more DAU to stabilize queues; email collection happens after users already care.
* **Cons**: Higher abuse surface; solve with scoped limits/CAPTCHA and preserve the existing anti-self-vote rules.
* **Data risk**: Guests can lose accounts if they clear storage—warn clearly and offer quick upgrade.