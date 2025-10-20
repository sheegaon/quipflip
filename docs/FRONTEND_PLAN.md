# Frontend Implementation Plan - Remaining Features

## Overview

The Quipflip frontend MVP is **COMPLETE** ✅. This document outlines remaining features and enhancements to implement beyond the core gameplay experience.

**Current Status:**
- ✅ **Phase 1 MVP**: All core gameplay, authentication, statistics, and tutorial system complete
- 🔄 **Phase 2**: Quest system backend complete, UI in progress  
- ⏸️ **Phase 3**: UI enhancements and advanced features planned

---

## Phase 2: Quest System UI (HIGH PRIORITY)

**Backend Status**: ✅ Complete (database, API, service logic)  
**Frontend Status**: 🔄 In Progress (20% complete - API integration done)

### 2.1: Quest Context & State Management
**Status**: ⏸️ Not Started

**Files to Create:**
- `frontend/src/contexts/QuestContext.tsx`

**Requirements:**
```typescript
interface QuestContextType {
  quests: Quest[];
  activeQuests: Quest[];
  claimableQuests: Quest[];
  loading: boolean;
  error: string | null;
  refreshQuests: () => Promise<void>;
  claimQuest: (questId: string) => Promise<ClaimQuestRewardResponse>;
  clearError: () => void;
}
```

**Integration Points:**
- Call `refreshQuests()` after votes, round completions, feedback submissions
- Trigger success notifications when quests complete
- Update GameContext balance after quest claims

### 2.2: Quest UI Components
**Status**: ⏸️ Not Started

**Files to Create:**
1. `frontend/src/components/SuccessNotification.tsx`
   - Green/blue celebration theme
   - Auto-dismiss after 5 seconds
   - Support for quest completion messages

2. `frontend/src/components/QuestCard.tsx`
   - Display quest name, description, progress bar
   - Reward amount with flipcoin icon
   - Status indicators (active/completed/claimed)
   - Claim button for completed quests
   - Category badges and progress animation

3. `frontend/src/components/QuestProgressBar.tsx`
   - Animated progress visualization
   - Color coding by category
   - "X / Y" format display

4. `frontend/src/components/QuestFilter.tsx`
   - Category tabs: All, Streaks, Quality, Activity, Milestones
   - Filter and sort functionality

### 2.3: Quests Page
**Status**: ⏸️ Not Started

**Files to Create:**
- `frontend/src/pages/Quests.tsx`

**Layout Requirements:**
```
Header with balance and back navigation
┌─────────────────────────────────────┐
│ Quests & Achievements               │
│ [Claimable Rewards: 3] 🎁          │
│ Total Rewards Earned: 450f          │
└─────────────────────────────────────┘

[Filter: All | Streaks | Quality | Activity | Milestones]

┌── Active Quests (2) ──────────────┐
│ [QuestCard] [QuestCard]             │
└─────────────────────────────────────┘

┌── Claimable Quests (1) ───────────┐
│ [QuestCard with Claim button]      │
└─────────────────────────────────────┘

┌── Completed Quests (8) ───────────┐
│ [QuestCard] [QuestCard] [QuestCard] │
│ [Show More...]                      │
└─────────────────────────────────────┘
```

**Features:**
- Real-time progress updates
- Expandable quest details
- Filter and sort options
- Empty states with encouraging messages
- Responsive mobile layout

### 2.4: Quest Integration & Notifications
**Status**: ⏸️ Not Started

**Files to Modify:**
1. `frontend/src/App.tsx` - Add `/quests` route
2. `frontend/src/pages/Dashboard.tsx` - Add quest notification banner
3. `frontend/src/contexts/GameContext.tsx` - Integrate quest refresh triggers

**Dashboard Integration:**
```tsx
{claimableQuests.length > 0 && (
  <div className="bg-green-50 border-2 border-green-400 rounded-lg p-4 mb-4">
    <div className="flex items-center justify-between">
      <div>
        <h3 className="font-display font-semibold text-green-800">
          🎉 Quests Completed!
        </h3>
        <p className="text-green-700">
          You have {claimableQuests.length} quest(s) ready to claim
        </p>
      </div>
      <button 
        onClick={() => navigate('/quests')}
        className="btn-primary"
      >
        View Quests
      </button>
    </div>
  </div>
)}
```

**Celebration Triggers:**
- After vote submission (hot streak progress)
- After phraseset finalization (deceptive/obvious bonuses)
- After round completion milestones
- During polling refresh (detect new completed quests)

---

## Phase 3: UI Polish & Enhancements (MEDIUM PRIORITY)

### 3.1: Mobile Header Optimization
**Status**: ⏸️ Not Started

**Goal**: Improve mobile header appearance with tighter spacing

**Files to Modify:**
- `frontend/src/components/Header.tsx`

**Changes:**
- Vertical padding: `py-1.5 md:py-3`
- Logo scaling: `h-8 md:h-12`
- Balance icon: `w-6 h-6 md:w-10 md:h-10`
- Balance text: `text-xl md:text-3xl`
- Element gaps: `gap-2 md:gap-4`

### 3.2: Currency Icon Replacement
**Status**: ⏸️ Not Started

**Goal**: Replace all "$" symbols with flipcoin icons throughout UI

**Files to Create:**
- `frontend/src/components/CurrencyDisplay.tsx`

**Files to Modify:**
- `frontend/src/pages/Statistics.tsx` - Replace $ in earnings displays
- `frontend/src/pages/PhrasesetTracking.tsx` - Replace $ in prize amounts
- `frontend/src/pages/Dashboard.tsx` - Replace $ in cost displays

**Component Design:**
```tsx
interface CurrencyDisplayProps {
  amount: number;
  iconClassName?: string;
  textClassName?: string;
  showIcon?: boolean;
}

// Renders: [flipcoin icon] 1000
```

### 3.3: Navigation Improvements
**Status**: ⏸️ Not Started

**Changes:**
1. **Back Arrow in Header**
   - Create `BackArrowIcon.tsx` component
   - Show on Statistics and Tracking pages only
   - Remove "Back to Dashboard" buttons from pages

2. **Statistics Icon Next to Username**
   - Create `StatisticsIndicatorIcon.tsx` (small bar chart)
   - Add next to username in header to indicate clickability

3. **Rename PhrasesetTracking → Tracking**
   - Rename file and component
   - Update all UI labels and references
   - Keep `/phrasesets` route for compatibility

### 3.4: Balance Visual Enhancement
**Status**: ⏸️ Not Started

**Goal**: Add subtle border around balance display

**Implementation:**
```tsx
// Wrap balance in bordered container
<div className="flex items-center gap-2">
  <img src="/flipcoin.png" />
  <div className="border-2 border-quip-turquoise rounded-tile px-3 py-1">
    <BalanceFlipper value={player.balance} />
  </div>
</div>
```

---

## Phase 4: Advanced Features (LOW PRIORITY)

### 4.1: Transaction History
**Status**: ⏸️ Not Started

**Files to Create:**
- `frontend/src/pages/TransactionHistory.tsx`
- `frontend/src/components/TransactionItem.tsx`

**Features:**
- List recent transactions with types and amounts
- Filter by type (earnings, costs, bonuses, quest rewards)
- Running balance column
- Pagination or infinite scroll
- Export functionality

### 4.2: Enhanced Results Features
**Status**: ⏸️ Partially Complete

**Remaining Features:**
- Visual chart/graph of vote distribution (using Recharts)
- Share results to social media
- Results comparison with previous phrasesets

### 4.3: Settings/Account Management
**Status**: ⏸️ Not Started

**Files to Create:**
- `frontend/src/pages/Settings.tsx`

**Features:**
- API key rotation UI
- Email/password change forms
- Game preferences (sound effects, notifications)
- Export data functionality
- Account deletion

### 4.4: Social Features
**Status**: ⏸️ Not Started

**Features:**
- Leaderboards (daily/weekly/all-time)
- Achievement sharing
- Player profiles
- Friend system integration (if backend supports)

### 4.5: Progressive Web App (PWA)
**Status**: ⏸️ Not Started

**Requirements:**
- Service worker for offline caching
- Web app manifest
- Push notification support
- Install prompts
- Offline queue for actions

---

## Phase 5: Real-time Features (FUTURE)

### 5.1: WebSocket Integration
**Status**: ⏸️ Requires Backend Phase 3

**Features:**
- Live vote counts during voting rounds
- Real-time queue depth updates
- Instant result notifications
- Live activity feed

### 5.2: Enhanced Notifications
**Status**: ⏸️ Not Started

**Features:**
- Browser push notifications
- Quest completion celebrations with animations
- Sound effects (user-configurable)
- Haptic feedback on mobile

---

## Technical Debt & Optimizations

### Performance Improvements
**Status**: ⏸️ Not Started

1. **Bundle Optimization**
   - Code splitting by route
   - Lazy loading for Statistics charts
   - Image optimization
   - Tree shaking unused dependencies

2. **State Management**
   - Move from Context to Redux Toolkit (if complexity grows)
   - Implement request caching
   - Optimize re-renders

3. **Accessibility**
   - ARIA labels for all interactive elements
   - Keyboard navigation improvements
   - Screen reader testing
   - Color contrast validation

### Error Handling Improvements
**Status**: ⏸️ Partially Complete

1. **Offline Support**
   - Show offline indicator
   - Queue actions when offline
   - Retry failed requests automatically

2. **Error Boundary**
   - Add React error boundaries
   - Graceful error recovery
   - Error reporting integration

---

## Implementation Priority Queue

### Next 2 Weeks (High Priority)
1. **Quest System UI** - Complete quest context, components, and page
2. **Quest Dashboard Integration** - Add claimable quest notifications
3. **Mobile Header Optimization** - Improve mobile header spacing

### Next Month (Medium Priority)  
4. **Currency Icon Replacement** - Create CurrencyDisplay component
5. **Navigation Improvements** - Back arrows, statistics icon
6. **Balance Enhancement** - Add border styling

### Next Quarter (Low Priority)
7. **Transaction History** - Full transaction viewing page
8. **Settings Page** - Account management features
9. **PWA Implementation** - Offline support and install prompts

---

## Success Metrics

### Quest System Success
- **Engagement**: >60% of users view quest page within first week
- **Completion**: >40% of users claim at least one quest reward
- **Retention**: Quest users have 25% higher 7-day retention

### UI Enhancement Success
- **Mobile**: >90% mobile users complete full game flow
- **Navigation**: <5% bounce rate on Statistics/Tracking pages
- **Performance**: Lighthouse score remains >90

### Technical Success
- **Error Rate**: <1% API call failures
- **Load Time**: <2s initial page load
- **Bundle Size**: <500KB initial bundle

---

## Development Resources Needed

### Design Assets
- Quest category icons (4 types: streak, quality, activity, milestone)
- Back arrow icon (left-pointing, theme-consistent)
- Statistics indicator icon (small bar chart)
- Enhanced flipcoin icon variants

### Technical Skills
- React context management and optimization
- Chart.js or Recharts for progress visualizations
- CSS animations for quest celebrations
- Service worker development (for PWA)

---

## Risk Mitigation

### Quest System Risks
- **Performance**: Large quest lists may impact load time
  - *Mitigation*: Pagination and lazy loading
- **User Confusion**: Complex quest mechanics
  - *Mitigation*: Clear progress indicators and help text

### UI Enhancement Risks  
- **Mobile Compatibility**: Header changes may break on edge devices
  - *Mitigation*: Extensive mobile testing
- **Breaking Changes**: Navigation updates may confuse existing users
  - *Mitigation*: Gradual rollout with user feedback

---

## Questions for Product Decision

1. **Quest Page Priority**: Should quest system be accessible from dashboard or require separate navigation?
2. **Mobile Header**: How aggressive should mobile space optimization be?
3. **Currency Symbol**: Completely replace $ with icons, or show both in some contexts?
4. **Real-time Features**: What's the priority for WebSocket integration vs other features?
5. **PWA Timeline**: When should offline support become a priority?

---

*Document updated: January 2025*  
*Status: Planning Phase - Quest System Backend Complete*  
*Next Milestone: Quest System UI Implementation*
