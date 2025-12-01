# Initial Reaction Frontend Contexts

The Initial Reaction (IR) frontend uses a lightweight context layer focused on session management and gameplay for backronym battles.

## AppProviders

`AppProviders` composes the IR providers and currently wraps the application tree with `NetworkProvider → TutorialProvider → IRGameProvider → NotificationProvider → NavigationHistoryProvider`.

```tsx
export const AppProviders: React.FC<AppProvidersProps> = ({ children }) => {
  return (
    <NetworkProvider>
      <TutorialProvider>
        <IRGameProvider>
          <NotificationProvider>
            <NavigationHistoryProvider>{children}</NavigationHistoryProvider>
          </NotificationProvider>
        </IRGameProvider>
      </TutorialProvider>
    </NetworkProvider>
  );
};
```

This provider stack keeps IR-specific state isolated from the Quipflip contexts used by the main app while also supplying network resiliency, tutorial progress, notifications, and back-navigation helpers to every screen.

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

### Session Detection Flow

`IRGameProvider` runs `detectUserSession` on mount before rendering routes. The helper:

- Differentiates **new visitors**, **returning visitors**, and **authenticated users** by combining a persisted `visitorId` with a stored username hint.
- Avoids network calls for first-time visitors without a stored username; otherwise probes `/player/balance` (cookie auth) and downgrades to unauthenticated states on 401.
- Persists a generated `ir_visitor_id` plus the last-known username, and associates that visitor ID with a player on guest creation or registration.
- Exposes the `sessionState` (`checking | new | returning_visitor | returning_user`) so the router can block with a loading screen until detection finishes.

If an authenticated balance lookup succeeds, a minimal `player` stub is built from wallet/vault/daily bonus fields so the UI can render before a full dashboard fetch completes.

## NetworkContext

**Purpose**: Detect connectivity quality and manage a durable offline queue.

- Tracks `isOnline`, `isOffline`, `wasOffline`, and a coarse `connectionQuality` derived from the browser’s effective connection type.
- Queues non-auth mutating requests (POST/PUT/PATCH/DELETE) via `offlineQueue` when offline, persisting up to 100 actions in `localStorage`.
- On reconnection, replays queued requests through the shared Axios client, removing successful actions, dropping permanent 4xx errors (except 429), and incrementing retry counts for transient failures.
- Exposes `retryFailedRequests()` (auto-invoked when coming back online) and `clearOfflineQueue()` for manual recovery/cleanup.

## NotificationContext

**Purpose**: Establish a WebSocket connection for push notifications after authentication.

- Fetches a short-lived WS token from `/auth/ws-token` using the configured API base (respecting the `/ir` prefix), then connects to `${base}/notifications/ws?token=…`.
- Silently ignores connection failures or malformed messages; there are no reconnect attempts or user-facing errors.
- Appends parsed notifications to in-memory state with incremental IDs, and exposes `addNotification`, `removeNotification`, and `clearAll` helpers. Rendering is delegated to `NotificationDisplay`.

## TutorialContext

**Purpose**: Coordinate the onboarding tutorial lifecycle.

- Uses stored username as a guard; skips backend calls when no username is present (i.e., before login/guest creation).
- Fetches status on mount (with abort support) and exposes lifecycle flags (`inactive`, `active`, `completed`, `error`).
- Provides actions to start, advance (calculates next step client-side), skip/complete, reset, and refresh progress via `/tutorial` endpoints, surfacing friendly error messages when calls fail.

## NavigationHistoryContext

**Purpose**: Maintain a lightweight navigation stack for back buttons independent of browser history.

- Records path changes, collapses duplicate entries, and trims the stack on manual back navigations.
- Clears history whenever the user lands on `/dashboard`, making dashboard the neutral “home” destination.
- Exposes `canGoBack`, `goBack()` (falls back to dashboard if stack is empty), and `clearHistory()` for components such as headers/subheaders.
