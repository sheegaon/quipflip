# Frontend Implementation Plan

## Overview

This document provides high-level guidance for implementing a Quipflip frontend. The backend API is complete and documented in [API.md](API.md). This plan focuses on the minimum viable frontend and logical phasing.

**STATUS: Phase 1 MVP is COMPLETE** ✅

The frontend is fully functional with:
- JWT authentication (access + refresh tokens with HTTP-only cookies)
- All three round types (Prompt, Copy, Vote) with timers and feedback
- Results viewing and prize claiming
- Phraseset tracking dashboard
- Prompt feedback system (like/dislike with improved mobile UI)
- Responsive UI with custom branding and optimized mobile experience
- Automatic token refresh and error handling
- Enhanced username display (larger on desktop, matches flipcoin color)

**Recent Updates:**
- Prompt feedback buttons smaller on mobile (text-lg) for better UX
- Prompt box height increased (min-h-[120px]) for better readability
- Username font size larger on desktop (md:text-lg) and color matches balance (text-quip-turquoise)

**Next Steps:** Phase 2 enhancements (Settings page, Transaction history, Enhanced statistics)

---

## Phase 1: MVP Frontend (Core Gameplay) ✅ COMPLETE

### Essential Screens

1. ✅ **Landing / Authentication**
   - Register new player (POST /player) → receive access + refresh tokens (legacy API key included for fallback)
   - Login form for returning players (POST /auth/login)
   - Automatic refresh handling via `/auth/refresh` + HTTP-only cookie
   - Store short-lived access token client-side (localStorage) and rely on refresh token cookie
   - Automatic token refresh on 401 errors with retry logic

2. ✅ **Dashboard / Home**
   - Display current balance with coin emoji
   - Show daily bonus notification if available
   - Display active round status (if any)
   - Notification badges for pending results and unclaimed prizes
   - Round selection buttons (Prompt / Copy / Vote)
   - Button state based on availability (GET /rounds/available)
   - Phraseset tracking navigation
   - Custom branding with logo and themed colors

3. ✅ **Prompt Round**
   - Display prompt text with custom styling
   - Text input for phrase submission (1-5 words, 2-100 chars)
   - Countdown timer (3 minutes / 180 seconds) with color-coded warnings
   - Submit button (disabled after timeout)
   - Validation feedback
   - Like/Dislike prompt feedback buttons
   - Visual feedback for submitted feedback

4. ✅ **Copy Round**
   - Display original phrase to copy
   - Display cost (\$100 or \$90 if discount) with visual indicator
   - Text input for copy phrase
   - Countdown timer (3 minutes / 180 seconds)
   - Submit button with duplicate detection feedback
   - Clear error messaging

5. ✅ **Vote Round**
   - Display prompt text
   - Three phrase buttons (randomized order per voter)
   - Countdown timer (60 seconds, visual urgency states)
   - Immediate feedback after vote (correct/incorrect, payout)
   - Payout amount display

6. ✅ **Results View**
   - Display prompt text
   - Show all three phrases with vote counts
   - Highlight original phrase
   - Show your phrase, role, points, and payout
   - Claim prizes button (separate action)
   - Visual vote distribution
   - Navigate between multiple unclaimed results

7. ✅ **Phraseset Tracking** (NEW)
   - View all phrasesets by role (prompt/copy/vote)
   - Filter by status (pending/open/closing/finalized)
   - Status badges with color coding
   - Click to view details
   - Count summaries for each category
   - Pagination support

8. ✅ **Tutorial System** (NEW)
   - Interactive onboarding for new players
   - Welcome modal with game overview
   - Step-by-step guided tour through dashboard and rounds
   - Spotlight effect highlighting key UI elements
   - Progress tracking with backend persistence
   - Skip and navigation options
   - Mobile-responsive overlay design

### Core Components

✅ **Timer Component** (COMPLETE)
- Calculate remaining time from `expires_at` timestamp
- Update every second
- Visual states: normal (blue) → warning (yellow, <30s) → urgent (red/pulsing, <10s) → expired
- Don't show grace period to users
- Custom hook `useTimer` for reusable logic

✅ **Balance Display** (COMPLETE)
- Show current balance prominently with coin emoji
- Update after each action
- Integrated into Header component
- Real-time updates via GameContext

✅ **Round State Manager** (COMPLETE)
- Poll GET /player/current-round on app load
- Resume active round if exists via GameContext
- Handle reconnection gracefully with AbortController
- Automatic cleanup on unmount

✅ **Error Handler** (COMPLETE)
- Map API error codes to user-friendly messages via extractErrorMessage
- ErrorNotification component with auto-dismiss
- Handle insufficient balance → suggest daily bonus
- 401 errors trigger automatic token refresh

### State Management

✅ **Implemented Global State (via GameContext):**
- `isAuthenticated` (JWT token status)
- `username` (stored in localStorage)
- `player` / `balance` (from GET /player/balance)
- `activeRound` (from GET /player/current-round)
- `pendingResults` (from GET /player/pending-results)
- `phrasesetSummary` (from GET /player/phrasesets/summary)
- `unclaimedResults` (from GET /player/unclaimed-results)
- `roundAvailability` (from GET /rounds/available)
- `loading` / `error` states

✅ **Polling Strategy (Implemented):**
- Balance & round availability: Every 60s
- Pending results, phraseset summary, unclaimed results: Every 90s
- All data fetched immediately on authentication
- Automatic cleanup with AbortController

### User Flow

✅ **Implemented Flow:**
```
1. First visit → Register (username/email/password) → Store tokens → Dashboard
2. Return visit → Auto-refresh access token → GET /player/balance → Dashboard
3. Dashboard → Check daily bonus → Claim if available (separate button)
4. Dashboard → Check active round → Resume if exists (automatic)
5. Dashboard → Select round type → Start round (disabled if unavailable)
6. In round → Submit phrase → Provide feedback (prompt only) → Return to dashboard
7. Dashboard → Notification badge → View unclaimed results → Claim prizes
8. Dashboard → Phraseset tracking → View all phrasesets by role/status
```

---

## Phase 2: Polish & User Experience (PARTIAL)

### Enhanced Features

1. **Transaction History** (NOT STARTED)
   - List of recent transactions with types and amounts
   - Filter by type (earnings, costs, bonuses)
   - Running balance column

2. ✅ **Improved Round Selection** (PARTIAL - showing availability)
   - ⏸️ Show queue depths (X prompts waiting, Y phrasesets waiting)
   - ✅ Copy discount indicator when active
   - ⏸️ Estimated wait time hints
   - ✅ Disabled state for unavailable round types

3. ✅ **Enhanced Results** (PARTIAL)
   - ✅ Vote distribution display
   - ✅ Points and payout breakdown
   - ⏸️ Visual chart/graph of vote distribution
   - ⏸️ Share results feature
   - ✅ History via phraseset tracking page

4. **Settings / Account** (NOT STARTED)
   - Legacy API key rotation UI
   - Export transaction history
   - Game statistics preview
   - Account management (email, password change)
   - Logout functionality (currently implemented inline)

5. ✅ **Better Error Handling** (COMPLETE)
   - ✅ Clear error messages with extractErrorMessage
   - ✅ Reconnection handling with state preservation
   - ✅ Automatic token refresh on auth errors
   - ⏸️ Graceful offline mode

6. ✅ **Loading States** (PARTIAL)
   - ✅ Loading indicators on buttons
   - ✅ Disabled states during API calls
   - ⏸️ Skeleton screens
   - ⏸️ Optimistic updates

### UX Improvements

- Animations on balance changes
- Sound effects (optional, user toggle)
- Haptic feedback on mobile
- Dark mode support
- ✅ **Tutorial/onboarding flow** (COMPLETE - Interactive guided tour)
- Keyboard shortcuts
- Accessibility (ARIA labels, keyboard navigation)

---

## Phase 3: Advanced Features

### ✅ Player Statistics Dashboard (COMPLETE)
- ✅ Win rate by role (prompt/copy/voter) with bar charts
- ✅ Total earnings breakdown with pie charts
- ✅ Play frequency metrics (rounds per day, days active)
- ✅ Role performance comparison with radar charts
- ✅ Top earning prompts and best performing phrases
- ✅ Interactive charts using Recharts library
- ✅ Accessible from dashboard via "View Statistics" button
- ✅ Backend endpoint: GET /player/statistics
- ✅ Frontend page: /statistics route

### Social Features
- Leaderboards (daily/weekly/all-time)
- Achievement badges
- Share results to social media
- Friend system (if backend supports)

### Premium Experience
- Progressive Web App (PWA)
- Push notifications for results ready
- Offline caching
- Native mobile apps (React Native / Flutter)

### Real-time Updates
- WebSocket connection for live updates (requires backend Phase 3)
- Live vote counts as they come in
- Real-time queue depth changes
- Instant result notifications

---

## Technical Considerations

### Framework Recommendations

**Web:**
- React / Next.js (most popular, good ecosystem)
- Vue / Nuxt (simpler learning curve)
- Svelte / SvelteKit (performance-focused)

**Mobile:**
- React Native (cross-platform, shares code with web)
- Flutter (high performance, native feel)
- Native iOS/Android (best UX, more effort)

### State Management Options

**Simple (MVP):**
- React Context API
- Vue Composition API
- Svelte stores

**Advanced (Phase 2+):**
- Redux Toolkit (React)
- Pinia (Vue)
- Zustand (lightweight, React)

### API Client

Create a typed API client using the TypeScript definitions in [API.md](API.md#frontend-integration). Consider:
- Axios or Fetch API wrapper
- Automatic retry logic
- Request/response interceptors for Authorization header injection
- Error transformation to user-friendly messages

### Offline Strategy

**Phase 1:**
- Show error message when offline
- Preserve access token metadata (with refresh fallback)

**Phase 2+:**
- Queue actions for later submission
- Cache recent results
- Service worker for PWA

---

## Testing Strategy

### Phase 1 Testing

**Manual Testing:**
- Complete game flow (prompt → copy → vote → results)
- Timer expiration handling
- Error scenarios (insufficient balance, invalid words)
- Reconnection after disconnect

**Automated Testing:**
- API client unit tests
- Component tests for timer logic
- Integration tests for critical flows
- E2E tests for happy path

### Phase 2+ Testing

- Visual regression testing
- Performance testing (bundle size, load time)
- Accessibility audits
- Cross-browser testing
- Mobile device testing

---

## Deployment

### Phase 1 MVP
- Static hosting (Vercel, Netlify, GitHub Pages)
- Environment variables for API URL
- CORS configuration with backend
- HTTPS required for secure token transport

### Phase 2+
- CDN for assets
- Analytics integration
- Error tracking (Sentry)
- Performance monitoring

---

## Design Guidelines

### Visual Hierarchy
- Balance and timer should be most prominent
- Clear call-to-action buttons
- Consistent color coding (green=success, red=error, blue=info)

### Responsive Design
- Mobile-first approach
- Touch-friendly tap targets (minimum 44x44px)
- Readable font sizes (minimum 16px)
- Landscape and portrait support

### Performance
- Minimize bundle size
- Lazy load routes
- Optimize images
- Debounce API calls

### Accessibility
- Semantic HTML
- ARIA labels for interactive elements
- Keyboard navigation support
- Screen reader friendly
- Color contrast ratios (WCAG AA minimum)

---

## Development Workflow

### Phase 1 Priorities (Week 1-2)
1. Set up project structure and routing
2. Implement authentication flow
3. Create dashboard with round selection
4. Build prompt/copy/vote round components
5. Implement timer logic
6. Add results viewing
7. Polish error handling and edge cases

### Phase 2 Priorities (Week 3-4)
1. Add transaction history
2. Improve loading states
3. Add animations and transitions
4. Implement settings/account page
5. Add offline handling
6. Accessibility improvements

### Phase 3+ (Post-MVP)
- Statistics dashboard
- Social features
- PWA conversion
- Mobile apps
- Real-time features

---

## API Integration Checklist

**Authentication:**
- ✅ POST /player (create account)
- ✅ POST /auth/login (username/password login)
- ✅ POST /auth/refresh (automatic token refresh)
- ✅ POST /auth/logout (clear refresh token)
- ✅ Store access tokens securely (localStorage + HTTP-only cookies)
- ✅ Include Authorization: Bearer header in all requests
- ✅ Handle 401 errors (automatic refresh + retry)

**Player Management:**
- ✅ GET /player/balance
- ✅ POST /player/claim-daily-bonus
- ✅ GET /player/current-round
- ✅ GET /player/pending-results
- ✅ GET /player/phrasesets (with filtering)
- ✅ GET /player/phrasesets/summary
- ✅ GET /player/unclaimed-results
- ✅ GET /player/statistics
- ✅ GET /player/tutorial/status
- ✅ POST /player/tutorial/progress
- ✅ POST /player/tutorial/reset
- ⏸️ POST /player/rotate-key (Phase 2 - UI needed)

**Round Management:**
- ✅ GET /rounds/available
- ✅ POST /rounds/prompt
- ✅ POST /rounds/copy
- ✅ POST /rounds/vote
- ✅ POST /rounds/{round_id}/submit
- ✅ POST /rounds/{round_id}/feedback (like/dislike)
- ✅ GET /rounds/{round_id}/feedback

**Voting & Results:**
- ✅ POST /phrasesets/{phraseset_id}/vote
- ✅ GET /phrasesets/{phraseset_id}/results
- ✅ GET /phrasesets/{phraseset_id}/details
- ✅ POST /phrasesets/{phraseset_id}/claim

---

## Success Metrics

### Phase 1 (MVP)
- Users can complete full game flow without confusion
- <2 second response time for API calls
- 90%+ uptime
- Zero critical bugs in production

### Phase 2+
- Average session length > 5 minutes
- Daily active user retention > 30%
- <1% error rate on API calls
- Lighthouse score > 90

---

## Common Pitfalls to Avoid

1. **Timer Sync Issues**
   - Always calculate from server `expires_at`, not client-side countdown
   - Account for network latency
   - Don't trust client time

2. **Race Conditions**
   - Handle rapid button clicks (disable while processing)
   - Optimistic updates with rollback on error
   - Check current round state before starting new round

3. **State Staleness**
   - Refresh balance after every transaction
   - Poll for round availability changes
   - Handle concurrent session detection (if needed)

4. **API Key Security**
   - Never log access or refresh tokens
   - Clear from memory on logout
   - Don't expose in URLs
   - Use HTTPS only

5. **Error Handling**
   - Always handle network errors gracefully
   - Provide actionable error messages
   - Allow retry for transient failures
   - Distinguish between client and server errors

---

## Next Steps

1. **Choose your framework** - React, Vue, or Svelte
2. **Set up project** - Use create-react-app, Vite, or Next.js
3. **Create API client** - TypeScript wrapper around fetch/axios
4. **Build authentication** - Landing page + token management
5. **Implement dashboard** - Balance display + round selection
6. **Add round screens** - Prompt → Copy → Vote
7. **Build results view** - Vote breakdown + payout display
8. **Test full flow** - End-to-end user journey
9. **Deploy** - Static hosting with environment config
10. **Iterate** - Gather feedback and improve

See [API.md](API.md) for complete API reference and [MVP_SUMMARY.md](MVP_SUMMARY.md) for backend status.
