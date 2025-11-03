# Frontend Context Architecture

This document describes the current state of the Quipflip frontend context architecture, which is organized into specialized contexts for different domains of application state.

## Overview

The frontend uses a modular context architecture that separates concerns across different domains:

- **GameContext**: Core game state, authentication, and round management
- **QuestContext**: Quest system, rewards, and progression tracking
- **TutorialContext**: Tutorial system and user onboarding
- **ResultsContext**: Results tracking, statistics, and completed rounds
- **AppProviders**: Orchestration layer that combines all contexts

## Context Hierarchy

```
AppProviders
├── TutorialContext
└── GameProvider
    └── InnerProviders
        ├── ResultsProvider
        └── ContextBridge
            └── QuestProvider
                └── Application Components
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
  loading: boolean;
  error: string | null;
}
```

### Key Actions

- `startSession(username, tokens)`: Initialize user session
- `logout()`: Clear session and reset state
- `refreshDashboard(signal?)`: Update dashboard data
- `refreshBalance(signal?)`: Update player balance
- `claimBonus()`: Claim daily bonus
- `startPromptRound()`: Start a new prompt round
- `startCopyRound()`: Start a new copy round
- `startVoteRound()`: Start a new vote round
- `claimPhrasesetPrize(phrasesetId)`: Claim completed round prize
- `flagCopyRound(roundId)`: Report a problematic copy round for moderation
- `abandonRound(roundId)`: Abandon the active prompt or copy round and trigger a partial refund

### Features

- **Smart Polling**: Automatically polls dashboard and balance data
- **Authentication Management**: Handles token validation and session state
- **Round State Management**: Tracks active rounds and their progression
- **Round Control Actions**: Supports flagging problematic copy rounds and abandoning active rounds with automatic refunds
- **Error Handling**: Centralized error management with detailed logging
- **Navigation Utilities**: Delayed navigation helpers

### Usage

```typescript
import { useGame } from '../contexts/GameContext';

const { state, actions } = useGame();
const { isAuthenticated, player, activeRound } = state;
const { startPromptRound, claimBonus } = actions;
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

**Purpose**: Manages user onboarding, tutorial progression, and help system.

### State Structure

```typescript
interface TutorialState {
  currentStep: string | null;
  completedSteps: Set<string>;
  availableSteps: TutorialStep[];
  isActive: boolean;
  showHints: boolean;
  tutorialMode: 'guided' | 'discovery' | 'disabled';
}
```

### Tutorial Steps

1. **welcome**: Introduction to Quipflip
2. **dashboard**: Understanding the dashboard
3. **create-prompt**: Creating engaging prompts
4. **write-copy**: Writing compelling copy
5. **vote-rounds**: Voting mechanics and rewards
6. **view-results**: Checking performance and earnings
7. **quests**: Quest system and bonus rewards (optional)

### Key Actions

- `startTutorial(mode?)`: Begin tutorial in guided or discovery mode
- `completeStep(stepId)`: Mark a tutorial step as completed
- `skipStep(stepId)`: Skip a tutorial step
- `goToStep(stepId)`: Jump to a specific tutorial step
- `nextStep()` / `previousStep()`: Navigate tutorial steps
- `endTutorial()`: Exit tutorial mode
- `resetTutorial()`: Reset all tutorial progress
- `toggleHints()`: Toggle hint visibility
- `setTutorialMode(mode)`: Change tutorial mode

### Features

- **Persistent State**: Tutorial progress saved to localStorage
- **Multiple Modes**: Supports guided tutorials and discovery learning
- **Step Navigation**: Flexible navigation between tutorial steps
- **Auto-progression**: Automatic advancement in guided mode
- **Hint System**: Contextual hints and tips

### Usage

```typescript
import { useTutorial } from '../contexts/TutorialContext';

const { state, actions } = useTutorial();
const { currentStep, isActive, showHints } = state;
const { startTutorial, completeStep } = actions;
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

1. **TutorialProvider**: Outermost, no dependencies
2. **GameProvider**: Core context with authentication
3. **InnerProviders**: Accesses GameContext for authentication state
4. **ResultsProvider**: Needs authentication state
5. **ContextBridge**: Syncs data between contexts
6. **QuestProvider**: Needs authentication and dashboard triggers

### Inter-Context Communication

- **Dashboard Triggers**: GameContext actions trigger updates in other contexts
- **Authentication Propagation**: Auth state flows from GameContext to child contexts
- **Data Synchronization**: Pending results sync from GameContext to ResultsContext

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
