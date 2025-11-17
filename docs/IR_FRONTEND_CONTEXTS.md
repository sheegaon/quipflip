# Initial Reaction Frontend Contexts

The Initial Reaction (IR) frontend uses a lightweight context layer focused on session management and gameplay for backronym battles.

## AppProviders

`AppProviders` composes the IR providers and currently wraps the application tree with `IRGameProvider`.

```tsx
export const AppProviders: React.FC<AppProvidersProps> = ({ children }) => {
  return <IRGameProvider>{children}</IRGameProvider>;
};
```

This provider stack keeps IR-specific state isolated from the Quipflip contexts used by the main app.

## IRGameContext

**Purpose**: Owns authentication, dashboard data, active set lifecycle, and player actions in the IR experience.

### State

- `isAuthenticated`: whether a player (guest or registered) has an active session
- `player`: basic profile and balances
- `activeSet`: current backronym set if the player has an ongoing session
- `pendingResults`: finalized sets awaiting review
- `loading` / `error`: request state flags
- `hasSubmittedEntry` / `hasVoted`: per-set participation flags

### Authentication Actions

- `loginAsGuest()` creates a guest account and stores player id
- `login(email, password)` authenticates returning users
- `register(username, email, password)` creates a new account
- `upgradeGuest(username, email, password)` converts a guest to a full account
- `logout()` clears session state and removes stored ids

### Gameplay Actions

- `startBackronymBattle()` starts a session and fetches authoritative set details
- `submitBackronym(setId, words)` submits a validated entry
- `validateBackronym(setId, words)` hits the validator endpoint for inline feedback
- `submitVote(setId, entryId)` records a vote and marks the set as voted in state
- `claimDailyBonus()` updates balance and availability flags

### Data Fetching

- `refreshDashboard()` pulls the dashboard payload and active session metadata
- `checkSetStatus(setId)` refreshes a single set and player participation flags

### Utilities

- `clearError()` resets the latest error message

### Notes on Usage

- Components access the context through `useIRGame()`; the provider guards protected routes in `App.tsx`.
- The context stores `player_id` and the active `set_id` in local storage helpers for reuse across views.
