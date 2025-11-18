# Quipflip Frontend Context Architecture

This document describes the current state of the Quipflip frontend context architecture, which is organized into specialized contexts for different domains of application state.

## Overview

The Quipflip frontend uses a modular context architecture that separates concerns across different domains:

- **NetworkContext**: Network status, offline queueing, and reconnection helpers
- **GameContext**: Core game state, authentication, and round management
- **NotificationContext**: WebSocket notifications for round activity
- **NavigationHistoryContext**: Client-side back-navigation stack
- **QuestContext**: Quest system, rewards, and progression tracking
- **TutorialContext**: Tutorial system and user onboarding
- **ResultsContext**: Results tracking, statistics, and completed rounds
- **AppProviders**: Orchestration layer that combines all contexts

## Context Hierarchy

```
AppProviders
├── NetworkProvider
    └── TutorialContext
        └── GameProvider
            └── InnerProviders
                ├── NotificationProvider
                ├── NavigationHistoryProvider
                ├── ResultsProvider
                └── ContextBridge
                    └── QuestProvider
                        └── Application Components
```

## NetworkContext

**Purpose**: Tracks connectivity, exposes connection quality, and replays queued API requests when the user comes back online.

### State Structure

```typescript
interface NetworkContextType {
  isOnline: boolean;
  isOffline: boolean;
  wasOffline: boolean;
  connectionQuality: 'fast' | 'slow' | 'offline';
  queueSize: number;
  retryFailedRequests: () => Promise<void>;
  clearOfflineQueue: () => void;
}
```

### Features

- **Offline Queue**: Subscribes to `offlineQueue` to track and replay queued Axios requests
- **Auto-Retry**: Automatically retries queued actions after reconnecting if any are pending
- **Retry Safety**: Drops actions that exceed retry limits or fail with permanent 4xx errors (except 429)
- **Connection Quality**: Exposes a derived `fast | slow | offline` status for UI hints

### Usage

```typescript
import { useNetwork } from '../contexts/NetworkContext';

const { isOffline, queueSize, retryFailedRequests } = useNetwork();
```

## GameContext

**Purpose**: Manages core game functionality, authentication, and active gameplay.

### State Structure

```typescript
interface GameState {
  isAuthenticated: boolean;
  username: string | null;
  player: Player | null;
  activeRound: ActiveRound | null;
  pendingResults: PendingResult[];
  phrasesetSummary: PhrasesetDashboardSummary | null;
  unclaimedResults: UnclaimedResult[];
  roundAvailability: RoundAvailability | null;
  copyRoundHints: string[] | null;
  loading: boolean;
  error: string | null;
  sessionState: SessionState;
  visitorId: string | null;
}
```

### Key Actions

- `startSession(username)`: Initialize user session
- `logout()`: Clear session and reset state
- `refreshDashboard(signal?)`: Update dashboard data
- `refreshBalance(signal?)`: Update player balance
- `claimBonus()`: Claim daily bonus
- `clearError()`: Clear error state
- `navigateAfterDelay(path, delay?)`: Navigate to path after optional delay
- `startPromptRound()`: Start a new prompt round
- `startCopyRound()`: Start a new copy round
- `startVoteRound()`: Start a new vote round
- `fetchCopyHints(roundId)`: Fetch AI-generated hints for a copy round
- `claimPhrasesetPrize(phrasesetId)`: Claim completed round prize
- `flagCopyRound(roundId)`: Report a problematic copy round for moderation
- `abandonRound(roundId)`: Abandon the active prompt or copy round and trigger a partial refund

### Features

- **Smart Polling**: Automatically polls dashboard and balance data
- **Authentication Management**: Handles token validation and session state
- **Session Detection**: Detects returning visitors, auto-creates guest accounts for new visitors, and stores visitor IDs
- **Round State Management**: Tracks active rounds and their progression
- **Round Control Actions**: Supports flagging problematic copy rounds and abandoning active rounds with automatic refunds
- **bfcache Awareness**: Refreshes dashboard data after browser back/forward cache restores
- **Error Handling**: Centralized error management with detailed logging
- **Navigation Utilities**: Delayed navigation helpers

### Usage

```typescript
import { useGame } from '../contexts/GameContext';

const { state, actions } = useGame();
const { isAuthenticated, player, activeRound } = state;
const { startPromptRound, claimBonus } = actions;
```

## NotificationContext

**Purpose**: Manages WebSocket notifications about phrase interactions and exposes a simple notification list API.

### State Structure

```typescript
interface NotificationContextType {
  notifications: NotificationMessage[];
  addNotification: (message: NotificationMessage) => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
}
```

### Features

- **Auth-Aware Lifecycle**: Opens the WebSocket when the player is authenticated and cleans up on logout/unmount
- **Token-Based Connection**: Fetches a short-lived token via REST before establishing the socket
- **Silent Failure**: Swallows connection errors and avoids noisy retries
- **Manual Controls**: Exposes helpers to append, remove, or clear notifications for UI components

### Usage

```typescript
import { useNotifications } from '../contexts/NotificationContext';

const { notifications, removeNotification } = useNotifications();
```

## NavigationHistoryContext

**Purpose**: Maintains a lightweight navigation stack to power consistent back navigation across the app.

### State Structure

```typescript
interface NavigationHistoryContextType {
  canGoBack: boolean;
  goBack: () => void;
  clearHistory: () => void;
}
```

### Features

- **Dashboard Reset**: Clears history when landing on `/dashboard` to avoid looping back
- **Back Navigation**: Handles manual/browser back operations by maintaining a stack of visited paths
- **Fallback Safety**: Falls back to `/dashboard` when no history is available

### Usage

```typescript
import { useNavigationHistory } from '../contexts/NavigationHistoryContext';

const { canGoBack, goBack } = useNavigationHistory();
```

## QuestContext

**Purpose**: Manages the quest system, including active quests, rewards, and progression.

### State Structure

```typescript
interface QuestState {
  quests: Quest[];
  activeQuests: Quest[];
  claimableQuests: Quest[];
  loading: boolean;
  error: string | null;
  lastUpdated: number | null;
  hasClaimableQuests: boolean;
}
```

### Key Actions

- `refreshQuests()`: Load all quest data
- `claimQuest(questId)`: Claim quest reward
- `clearQuestError()`: Clear error state

### Features

- **Auto-loading**: Automatically loads quests when user authenticates
- **Reward Claiming**: Handles quest completion and reward distribution
- **State Synchronization**: Coordinates with GameContext for dashboard updates
- **Error Recovery**: Handles authentication errors gracefully

### Usage

```typescript
import { useQuests } from '../contexts/QuestContext';

const { state, actions } = useQuests();
const { activeQuests, claimableQuests, loading } = state;
const { claimQuest, refreshQuests } = actions;
```

## TutorialContext

**Purpose**: Manages user onboarding and tutorial progression with backend-synced state.

### State Structure

```typescript
interface TutorialState {
  status: TutorialStatus | null;
  tutorialStatus: TutorialLifecycleStatus;
  isActive: boolean;
  currentStep: TutorialProgress | null;
  loading: boolean;
  error: string | null;
}
```

Where `TutorialLifecycleStatus` is: `'loading' | 'inactive' | 'active' | 'completed' | 'error'`

### Tutorial Steps

The tutorial follows a linear progression through these steps:

1. **not_started**
2. **welcome**
3. **dashboard**
4. **prompt_round**
5. **copy_round**
6. **vote_round**
7. **completed_rounds_guide**
8. **completed**

### Key Actions

- `startTutorial()`: Begin tutorial (sets progress to 'welcome')
- `advanceStep(stepId?)`: Advance to next step or specific step
- `skipTutorial()`: Skip entire tutorial (marks as completed)
- `completeTutorial()`: Mark tutorial as completed
- `resetTutorial()`: Reset tutorial progress to beginning
- `refreshStatus(options?)`: Refresh tutorial status from backend

### Features

- **Backend-Synced Progress**: Tutorial progress is stored on the backend and synced across devices
- **Forward-Only Progression**: Users can only advance through steps, not go backwards
- **Lifecycle States**: Clear status tracking (loading, inactive, active, completed, error)
- **Authentication-Aware**: Automatically handles unauthenticated users gracefully
- **Auto-Loading**: Automatically loads tutorial status on mount

### Usage

```typescript
import { useTutorial } from '../contexts/TutorialContext';

const { state, actions } = useTutorial();
const { currentStep, isActive, tutorialStatus } = state;
const { startTutorial, advanceStep, skipTutorial } = actions;
```

## ResultsContext

**Purpose**: Manages results tracking, statistics, completed rounds, and phraseset data.

### State Structure

```typescript
interface ResultsState {
  pendingResults: PendingResult[];
  viewedResultIds: Set<string>;
  playerPhrasesets: Record<string, PhrasesetListCacheEntry>;
  phrasesetDetails: Record<string, PhrasesetDetailsCacheEntry>;
  phrasesetResults: Record<string, PhrasesetResultsCacheEntry>;
  statistics: StatisticsData | null;
  statisticsLoading: boolean;
  statisticsError: string | null;
  lastStatisticsUpdate: number | null;
}
```

### Key Actions

- `refreshPlayerPhrasesets(params?, options?)`: Load player's phraseset list
- `refreshPhrasesetDetails(phrasesetId, options?)`: Load specific phraseset details
- `refreshPhrasesetResults(phrasesetId, options?)`: Load phraseset voting results
- `getStatistics(signal?)`: Load player statistics
- `markResultsViewed(phrasesetIds)`: Mark results as viewed
- `clearResultsCache()`: Clear all cached data
- `setPendingResults(results)`: Update pending results from GameContext

### Features

- **Caching System**: Intelligent caching of phraseset data with timestamps
- **Viewed Tracking**: Persistent tracking of viewed results in sessionStorage
- **Statistics Management**: Player performance and earnings statistics
- **Leaderboard Integration**: Statistics view combines context-managed stats with the `/player/statistics/weekly-leaderboard` API so the weekly net earnings snapshot respects backend caching rules.
- **State Synchronization**: Syncs with GameContext pending results
- **Cache Invalidation**: Force refresh options for all data types

### Usage

```typescript
import { useResults } from '../contexts/ResultsContext';

const { state, actions } = useResults();
const { pendingResults, phrasesetResults, statistics } = state;
const { refreshPhrasesetResults, markResultsViewed } = actions;
```

## AppProviders

**Purpose**: Orchestration layer that combines all contexts and manages inter-context communication.

### Architecture

The `AppProviders` component uses a nested structure to ensure proper dependency injection:

1. **NetworkProvider**: Provides online/offline state and offline queue data
2. **TutorialProvider**: Runs outside GameContext to bootstrap tutorial status checks
3. **GameProvider** *(inside an error boundary)*: Core auth and dashboard provider
4. **InnerProviders**: Collection of contexts that depend on GameContext state
5. **NotificationProvider**: Opens notification WebSocket when authenticated
6. **NavigationHistoryProvider**: Tracks route stack for consistent back navigation
7. **ResultsProvider**: Needs authentication state for player data
8. **ContextBridge**: Syncs tutorial status, pending results, and dashboard triggers
9. **QuestProvider**: Needs authentication and dashboard triggers for refreshes

### Inter-Context Communication

- **Dashboard Triggers**: GameContext actions notify QuestContext, which can request dashboard/balance refreshes
- **Authentication Propagation**: Auth state flows from GameContext to child contexts, including notification socket setup
- **Data Synchronization**: Pending results sync from GameContext to ResultsContext; tutorial status refreshes after auth changes
- **Offline Awareness**: NetworkContext exposes queue size/connection quality for UI components throughout the tree

### Usage

```typescript
import { AppProviders } from '../contexts/AppProviders';

function App() {
  return (
    <AppProviders>
      <Router>
        {/* Your app components */}
      </Router>
    </AppProviders>
  );
}
```

## Debugging and Logging

All contexts include comprehensive logging with emoji indicators:

- 🎯 Action calls
- 📞 API calls
- ✅ Successful operations
- ❌ Errors and failures
- 🔄 State updates
- 💾 Persistence operations
- 🚪 Authentication events
- 🧹 Cleanup operations

### Log Examples

```
🎯 GameContext startSession called: { username: "player123" }
📞 Making dashboard API call...
✅ Dashboard data received successfully: { playerBalance: 150, ... }
🔄 Setting loading to false
```

## Best Practices

### Context Selection

- **GameContext**: Use for authentication, core game state, and round management
- **QuestContext**: Use for quest-related UI and actions
- **TutorialContext**: Use for onboarding flows and help systems
- **ResultsContext**: Use for results pages, statistics, and historical data

### Performance Considerations

- Contexts use `useCallback` and `useMemo` to prevent unnecessary re-renders
- Caching systems reduce API calls
- Dependencies are carefully managed to avoid infinite loops
- State updates are batched where possible

### Error Handling

- Each context handles its own errors with appropriate user messages
- Authentication errors are propagated to trigger logout
- Network errors include retry mechanisms where appropriate
- Loading states prevent user confusion during async operations

## Migration Notes

This architecture replaced a monolithic GameContext that managed all state. The current design provides:

- Better separation of concerns
- Improved performance through targeted re-renders
- Enhanced debugging capabilities
- More maintainable and testable code
- Clearer data flow and dependencies

## Future Considerations

- Consider adding RTK Query or SWR for more sophisticated caching
- Implement optimistic updates for better user experience
- Add context-specific middleware for advanced state management
- Consider state persistence strategies for offline support
