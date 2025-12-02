# Frontend Consolidation Plan: QF + MM → Crowdcraft

## Executive Summary

This plan consolidates duplicate code between QuipFlip (QF) and MemeMint (MM) frontends into the shared crowdcraft library. Analysis reveals **~40-50% code duplication** across components, contexts, utilities, and API clients that can be eliminated.

**Impact**: Reduced maintenance burden, consistent patterns across games, easier addition of new games.

## Key Findings from Analysis

### Verified Duplications

1. **NavigationHistoryContext**: MM version is more sophisticated (tracks full location state). Use MM version as base.
2. **LoadingSpinner**: ✅ Already shared via crowdcraft (both games import from `@crowdcraft`)
3. **smartPolling.ts**: 99% identical. MM has extra `ROUND_AVAILABILITY` config. Easy merge.
4. **Components**: ~18 pure UI components are strong candidates for consolidation
5. **Contexts**: 5 contexts likely identical or near-identical (NotificationContext, TutorialContext, QuestContext, ResultsContext, AppProviders)
6. **API Clients**: ~70% of endpoints are shared between games

### Architecture Already Established

- Crowdcraft exports via `@crowdcraft/*` path aliases ✅
- Games import shared code successfully ✅
- Pattern of "base + game-specific extension" exists for API client ✅

## Consolidation Strategy

### Phase 1: Low-Risk Utilities (Week 1)

**Status: ✅ Completed.** Utilities are centralized in `frontend/crowdcraft/src/utils/` with QF/MM importing from crowdcraft exports. Legacy per-game copies for these helpers were removed.

**Move to crowdcraft as-is:**

1. **smartPolling.ts** - Merge both versions (add MM's ROUND_AVAILABILITY config) ✅
   - Source: `frontend/qf/src/utils/smartPolling.ts` + `frontend/mm/src/utils/smartPolling.ts`
   - Target: `frontend/crowdcraft/src/utils/smartPolling.ts`
   - Action: Added ROUND_AVAILABILITY from MM to PollConfigs and updated QF/MM imports to consume the shared version

2. **errorMessages.ts** - Identical implementation ✅
   - Source: `frontend/qf/src/utils/errorMessages.ts`
   - Target: `frontend/crowdcraft/src/utils/errorMessages.ts`
   - Action: QF/MM now import from crowdcraft; per-game duplicates removed

3. **errorReporting.ts** - Identical implementation ✅
   - Source: `frontend/qf/src/utils/errorReporting.ts`
   - Target: `frontend/crowdcraft/src/utils/errorReporting.ts`
   - Action: Consolidated into crowdcraft and removed per-game copies

4. **gameKeys.ts** - Likely identical (needs verification) ✅
   - Source: `frontend/qf/src/utils/gameKeys.ts`
   - Target: `frontend/crowdcraft/src/utils/gameKeys.ts`
   - Action: Verified identical, centralized, and updated QF/MM imports

5. **phrasesetHelpers.ts** - Likely identical (needs verification) ✅
   - Source: `frontend/qf/src/utils/phrasesetHelpers.ts`
   - Target: `frontend/crowdcraft/src/utils/phrasesetHelpers.ts`
   - Action: Verified identical, centralized, and updated QF/MM imports

6. **reviewHelpers.ts** - Likely identical (needs verification) ✅
   - Source: `frontend/qf/src/utils/reviewHelpers.ts`
   - Target: `frontend/crowdcraft/src/utils/reviewHelpers.ts`
   - Action: Verified identical, centralized, and removed per-game copies

**Parameterize for game-specific branding:**

7. **brandedMessages.ts** - Factory pattern for game-specific strings ✅
   ```typescript
   export const createBrandedMessages = (config: {
     gameName: string;
     currencyName: string;
     coinImagePath: string;
   }) => ({ /* messages using config */ });
   ```
   - Added factory + default brand configs in `frontend/crowdcraft/src/utils/brandedMessages.ts`; QF now consumes the shared module

### Phase 2: Simple Contexts (Week 2)

**Status: ✅ Completed.** All shared contexts now live in `frontend/crowdcraft/src/contexts/` with factory helpers that accept per-game configuration hooks. QF/MM wrap these factories to plug in game-specific tutorial data, notification settings, and quest/result fetching logic.

**Moved to crowdcraft with per-game wrappers:**

1. **NavigationHistoryContext** - MM version adopted as the base (tracks pathname/search/hash/state)
   - Source: `frontend/mm/src/contexts/NavigationHistoryContext.tsx`
   - Target: `frontend/crowdcraft/src/contexts/NavigationHistoryContext.tsx`
   - Wrappers: `frontend/qf/src/contexts/NavigationHistoryContext.tsx`, `frontend/mm/src/contexts/NavigationHistoryContext.tsx`

2. **NotificationContext** - Unified and parameterized via `createNotificationContext`
   - Wrappers inject WebSocket paths, party session hooks, and enablement flags per game

3. **TutorialContext** - Shared `createTutorialContext` with injected tutorial steps/status typing
   - Wrappers: `frontend/qf/src/contexts/TutorialContext.tsx`, `frontend/mm/src/contexts/TutorialContext.tsx`

4. **QuestContext** - Shared state/actions consumed through wrappers in each game

5. **ResultsContext** - Shared cache/selector logic with wrappers delegating to game-specific providers

### Phase 3: Pure UI Components (Week 2-3)

**Already shared:**
- ✅ LoadingSpinner (both import from crowdcraft)

**Status: ✅ Completed.** All pure UI components now live in `frontend/crowdcraft/src/components/` with game wrappers delegating to the shared implementations.

**Moved to crowdcraft:**

1. Timer.tsx
2. ProgressBar.tsx
3. StatusBadge.tsx
4. CurrencyDisplay.tsx (configurable icon alt/src to support game branding)
5. ErrorNotification.tsx
6. SuccessNotification.tsx
7. NotificationDisplay.tsx (accepts notification/action props; game wrappers supply routing)
8. NotificationToast.tsx (action label/callback configurable)
9. PingNotificationDisplay.tsx (action callback configurable)
10. OfflineBanner.tsx
11. ThumbFeedbackButton.tsx
12. EditableConfigField.tsx
13. QuestCard.tsx
14. QuestProgressBar.tsx

**May need branding parameters:**
15. NewUserWelcomeOverlay.tsx
16. UpgradeGuestAccount.tsx
17. BetaSurveyModal.tsx

**Tutorial components:**
18. Tutorial/TutorialOverlay.tsx
19. Tutorial/TutorialWelcome.tsx

### Phase 4: Parameterized Components (Week 3)

**Status: ✅ Completed.** `Header` and `SubHeader` are centralized under `frontend/crowdcraft/src/components/` with configurable menu items, icon props, and callbacks. QF/MM wrappers pass their route handlers, tutorial flags, survey gating, and quest indicator data while reusing the shared layout and accessibility behaviors.

**Implementation notes:**
- Shared `Header` renders brand logo/back arrow, wallet/vault balances, dropdown menus (sections + footer items), and guest logout handling via callbacks.
- Shared `SubHeader` renders the in-progress/results/quest indicators with optional callbacks for leaderboard, tutorial, and quests; buttons are hidden automatically when handlers are not provided.
- QF renders `SubHeader` on the dashboard; MM composes it in `App` to mirror previous layout.

### Phase 5: API Client Consolidation (Week 4)

**Status: ✅ Completed.** Shared API logic now lives in `frontend/crowdcraft/src/api/BaseApiClient.ts`, centralizing axios configu
ration, interceptors (logging, token refresh, offline queueing), credential helpers, and ~70% of the endpoints used by both ga
mes. QF/MM clients extend the base class to add only their game-specific endpoints.

**Implementation notes:**
- `BaseApiClient` exposes common auth, player, tutorial, quest, leaderboard, phraseset, admin, and notification-adjacent endpo
ints plus helpers (`extractErrorMessage`, `clearStoredCredentials`).
- QuipFlip now subclasses the base client and only implements Party Mode endpoints; the shared interceptors handle retries/log
ging for those calls.
- MemeMint subclasses the base client, reuses the shared endpoints, and layers on MemeMint-specific vote/caption aliases, QF o
nline-user lookups (with absolute URLs), and circle management endpoints.
- Both clients export their axios instances via the base class to keep NetworkContext hooks working unchanged.

**Benefits:**
- Eliminates ~30KB duplication per game
- Single source of truth for common endpoints
- Type safety maintained

### Phase 6: GameContext (Complex - Week 5-6)

**Recommended Approach: Extract Common Logic**

Rather than creating a complex factory pattern, extract shared hooks:

```typescript
// frontend/crowdcraft/src/hooks/useSessionManagement.ts
export const useSessionManagement = () => {
  // Login, logout, token refresh logic
  // Returns: { isAuthenticated, username, player, login, logout }
};

// frontend/crowdcraft/src/hooks/useSmartPollingSetup.ts
export const useSmartPollingSetup = (polls: PollConfig[]) => {
  // Setup smart polling with cleanup
};

// frontend/crowdcraft/src/hooks/useDashboardPolling.ts
export const useDashboardPolling = (callback: () => Promise<void>) => {
  // Dashboard-specific polling logic
};
```

**Game contexts compose these:**

```typescript
// frontend/qf/src/contexts/GameContext.tsx
export const GameProvider = ({ children }) => {
  const session = useSessionManagement();
  const polling = useSmartPollingSetup([/* QF polls */]);

  // QF-specific state and actions
  const [activeRound, setActiveRound] = useState(null);

  const startPromptRound = async () => { /* QF-specific */ };

  return (
    <GameContext.Provider value={{
      ...session,
      activeRound,
      startPromptRound,
      // ... QF-specific
    }}>
      {children}
    </GameContext.Provider>
  );
};
```

**Alternative: Factory Pattern** (if composition proves insufficient)
- Create `createGameContext<TState, TActions>(config)` factory
- Higher complexity, only pursue if composition approach has limitations

### Phase 7: AppProviders (Week 6)

**Parameterize provider composition:**

```typescript
// frontend/crowdcraft/src/contexts/AppProviders.tsx
export interface AppProvidersConfig {
  gameProvider: React.ComponentType<{ children: React.ReactNode }>;
  additionalProviders?: React.ComponentType<{ children: React.ReactNode }>[];
}

export const createAppProviders = (config: AppProvidersConfig) => {
  const AppProviders = ({ children }) => {
    const GameProvider = config.gameProvider;

    return (
      <ErrorBoundary>
        <NetworkProvider>
          <GameProvider>
            <NotificationProvider>
              <QuestProvider>
                <ResultsProvider>
                  <TutorialProvider>
                    <NavigationHistoryProvider>
                      {config.additionalProviders?.map((Provider, i) => (
                        <Provider key={i}>{children}</Provider>
                      )) ?? children}
                    </NavigationHistoryProvider>
                  </TutorialProvider>
                </ResultsProvider>
              </QuestProvider>
            </NotificationProvider>
          </GameProvider>
        </NetworkProvider>
      </ErrorBoundary>
    );
  };

  return AppProviders;
};
```

## Directory Structure After Consolidation

```
frontend/crowdcraft/src/
├── api/
│   ├── BaseApiClient.ts          # NEW: Base client with ~60 common methods
│   ├── client.ts                 # Existing
│   └── types.ts                  # Existing
├── components/
│   ├── Header.tsx                # NEW: Parameterized
│   ├── SubHeader.tsx             # NEW: Parameterized
│   ├── LoadingSpinner.tsx        # Existing ✅
│   ├── Timer.tsx                 # NEW
│   ├── ProgressBar.tsx           # NEW
│   ├── StatusBadge.tsx           # NEW
│   ├── CurrencyDisplay.tsx       # NEW
│   ├── ErrorNotification.tsx     # NEW
│   ├── SuccessNotification.tsx   # NEW
│   ├── NotificationDisplay.tsx   # NEW
│   ├── NotificationToast.tsx     # NEW
│   ├── OfflineBanner.tsx         # NEW
│   ├── PingNotificationDisplay.tsx  # NEW
│   ├── NewUserWelcomeOverlay.tsx    # NEW
│   ├── UpgradeGuestAccount.tsx      # NEW
│   ├── BetaSurveyModal.tsx         # NEW
│   ├── ThumbFeedbackButton.tsx     # NEW
│   ├── EditableConfigField.tsx     # NEW
│   ├── QuestCard.tsx               # NEW
│   ├── QuestProgressBar.tsx        # NEW
│   ├── Tutorial/                   # NEW
│   │   ├── TutorialOverlay.tsx
│   │   └── TutorialWelcome.tsx
│   ├── [existing components...]
├── contexts/
│   ├── NavigationHistoryContext.tsx # NEW (from MM)
│   ├── NotificationContext.tsx     # NEW
│   ├── TutorialContext.tsx         # NEW
│   ├── QuestContext.tsx            # NEW
│   ├── ResultsContext.tsx          # NEW
│   ├── AppProviders.tsx            # NEW: Factory version
│   ├── NetworkContext.tsx          # Existing ✅
├── hooks/
│   ├── useSessionManagement.ts     # NEW
│   ├── useSmartPollingSetup.ts     # NEW
│   ├── useDashboardPolling.ts      # NEW
│   ├── useHeaderIndicators.ts      # NEW
│   ├── [existing hooks...]
├── utils/
│   ├── smartPolling.ts             # NEW (merged QF+MM)
│   ├── errorMessages.ts            # NEW
│   ├── errorReporting.ts           # NEW
│   ├── gameKeys.ts                 # NEW
│   ├── phrasesetHelpers.ts         # NEW
│   ├── reviewHelpers.ts            # NEW
│   ├── brandedMessages.ts          # NEW (factory)
│   ├── [existing utils...]
└── index.ts                        # UPDATE: Export all new items
```

## Migration Checklist (Per Item)

For each file being consolidated:

- [ ] **Compare**: Diff QF vs MM versions, document differences
- [ ] **Decide**: Move as-is, merge, or parameterize
- [ ] **Create**: Add to `frontend/crowdcraft/src/`
- [ ] **Export**: Add to `frontend/crowdcraft/src/index.ts`
- [ ] **Update QF**: Change imports to `@crowdcraft/*`, test, delete old file
- [ ] **Update MM**: Change imports to `@crowdcraft/*`, test, delete old file
- [ ] **Test**: Run tests for both games, manual smoke testing
- [ ] **Validate**: Check bundle size impact

## Risk Mitigation

### High-Risk Items
1. GameContext refactor - Most complex, touches everything
2. API Client refactor - Core infrastructure
3. Header component - User-facing, brand-critical

### Mitigation Strategies
1. **Incremental rollout** - One phase at a time with validation
2. **Keep old code** - Don't delete until new version validated in both games
3. **Comprehensive testing** - Unit + integration + E2E for each phase
4. **Git strategy** - Create branches per phase, tag before/after states

## Success Metrics

### Quantitative
- **Code Reduction**: Target 40-50% reduction in duplicate code
- **Bundle Size**: Monitor (should stay similar or smaller)
- **Test Coverage**: Maintain >80% coverage
- **Build Time**: Should not significantly increase

### Qualitative
- Easier to add new games
- Faster bug fixes (one place to fix)
- Improved code consistency

## Critical Files to Review Before Implementation

### For detailed comparison:
1. `frontend/qf/src/contexts/NotificationContext.tsx` vs `frontend/mm/src/contexts/NotificationContext.tsx`
2. `frontend/qf/src/contexts/TutorialContext.tsx` vs `frontend/mm/src/contexts/TutorialContext.tsx`
3. `frontend/qf/src/contexts/QuestContext.tsx` vs `frontend/mm/src/contexts/QuestContext.tsx`
4. `frontend/qf/src/contexts/ResultsContext.tsx` vs `frontend/mm/src/contexts/ResultsContext.tsx`
5. `frontend/qf/src/api/client.ts` vs `frontend/mm/src/api/client.ts` - Full API method inventory
6. `frontend/qf/src/components/Header.tsx` vs `frontend/mm/src/components/Header.tsx`

### For game-specific understanding:
7. `frontend/qf/src/contexts/GameContext.tsx` - QF game logic patterns
8. `frontend/mm/src/contexts/GameContext.tsx` - MM game logic patterns

## Open Questions for User

(To be confirmed before starting implementation)

1. **Scope**: Implement all phases or prioritize specific phases first?
2. **Timeline**: Any deadlines or urgency considerations?
3. **GameContext approach**: Preference for composition (recommended) vs factory pattern?
4. **Testing requirements**: Existing test coverage? Need to add tests before refactoring?
5. **Risk tolerance**: Comfortable with phased approach or prefer more cautious/slower rollout?
