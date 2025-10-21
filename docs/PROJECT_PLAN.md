# Implementation Plan

## Implementation Priorities

### Phase 1 - MVP (Core Gameplay) ✅ COMPLETE
1. ✅ **Player accounts and authentication** - JWT access + refresh tokens with HTTP-only cookies
2. ✅ **Email-based login** - Players authenticate with email/password
3. ✅ **Player pseudonyms** - Auto-generated hidden names shown to other players in results
4. ✅ **Balance management and transactions** - Full amount deducted immediately, refunds on timeout
5. ✅ **Core game loop** - Prompt (random assignment), copy, vote with full lifecycle
6. ✅ **Word validation** - NASPA dictionary (191k words) with 1-5 words, 4-100 chars, A-Z only
7. ✅ **Queue system** - FIFO with Redis/in-memory fallback
8. ✅ **Scoring and payouts** - Proportional distribution with rounding
9. ✅ **One-round-at-a-time enforcement** - Via active_round_id in player table
10. ✅ **Results viewing and prize collection** - Separate claim endpoint for payouts
11. ✅ **Essential API endpoints** - All endpoints documented in API.md
12. ✅ **Daily login bonus** - UTC date-based, 100f once per day (excluding creation date)
13. ✅ **Copy discount system** - 90f when prompts_waiting > 10, system contributes 10f
14. ✅ **Grace period handling** - 5-second backend grace on all submissions
15. ✅ **Outstanding prompts limit** - Max 10 phrasesets in 'open' or 'closing' status
16. ✅ **Vote timeline state machine** - 3rd vote (10 min window), 5th vote (60 sec window)
17. ✅ **Copy abandonment** - Return to queue, prevent same player retry (24h cooldown)
18. ✅ **Self-voting prevention** - Filter at assignment time
19. ✅ **Health check endpoint** - GET /health for monitoring
20. ✅ **Error standardization** - Consistent JSON error format across all endpoints
21. ✅ **Suggested usernames** - GET /auth/suggest-username for registration convenience (deprecated - usernames now auto-generated)
22. ✅ **Frontend MVP** - Complete React + TypeScript frontend with all game flows
23. ✅ **Prompt feedback system** - Like/dislike feedback on prompts
24. ✅ **Phraseset tracking** - Dashboard to view all phrasesets by role and status (renamed to "Tracking")
25. ✅ **Unclaimed results** - Separate endpoint for unclaimed prizes with claim functionality
26. ✅ **Automatic username generation** - Usernames randomly generated, cannot be changed by users
27. ✅ **Enhanced header navigation** - Username clickable (goes to stats), daily bonus as treasure chest icon
28. ✅ **Statistics page improvements** - Email address shown alongside username

### Phase 2 - Polish & Enhancements
1. ✅ **JWT authentication** - Secure token-based auth with automatic refresh (COMPLETE)
2. ✅ **AI copy providers (OpenAI + Gemini)** - Configurable AI backup system (COMPLETE)
3. ✅ **Player statistics system** - Comprehensive win rates, earnings breakdown, performance metrics with charts (COMPLETE)
4. ✅ **Tutorial/onboarding flow** - Interactive tutorial with guided tours for new players (COMPLETE)
5. ✅ **Quest/Achievement system** - 16 achievement types with automatic progress tracking and rewards (COMPLETE - Backend done, UI in progress)
6. ✅ **UI Enhancement Plan** - Mobile responsiveness, currency icon replacement, navigation improvements (PLANNED in UI_ENHANCEMENT_PLAN.md)
7. **Transaction history endpoint** - GET /player/transactions with pagination
8. **Advanced rate limiting** - Per-endpoint, per-player rate limits
9. **Prompt management** - Track usage_count, avg_copy_quality for rotation
10. **Admin API endpoints** - Manual injection for testing (AI backup simulation)
11. **Settings page** - User preferences, account management
12. **Enhanced results visualization** - Charts, graphs, vote distribution graphics
13. **Dark mode** - Theme toggle with persistent preference

### Phase 3 - AI & Advanced Features
1. 🔄 **AI backup copies** - Automated generation after 10 minutes (IN PROGRESS - service ready, needs scheduler)
2. ✅ **AI provider infrastructure** - OpenAI + Gemini with automatic fallback (COMPLETE)
3. ✅ **AI backup votes** - Automated voting when voters unavailable (COMPLETE)
4. ✅ **AI metrics tracking** - Comprehensive usage, cost, and success rate monitoring (COMPLETE)
5. ✅ **Integration tests** - 17 test cases for AI service (COMPLETE)
6. **Background job scheduler** - Celery/APScheduler for AI backup cycles and cleanup
7. **Metrics dashboard API** - Endpoints for viewing AI analytics
8. **Performance optimization** - Query optimization, caching, connection pooling
9. **Database-based queue fallback** - Alternative to Redis for true distributed setup

### Phase 4 - Social & Engagement
1. **Player statistics dashboard** - Detailed win rates, earnings, patterns
2. **Leaderboards** - Daily/weekly/all-time top earners
3. **Achievement system** - Badges for milestones
4. **Social features** - Friends, challenges, sharing
5. **Premium prompts** - Special categories with higher stakes
6. **Seasonal events** - Themed prompts and bonuses
7. **User-submitted prompts** - Community content (moderated)
8. **OAuth integration** - Google, Twitter, etc.

---

## AI Copy Service Implementation

### Overview
The AI copy service provides automated backup copy generation when human players are unavailable. The system supports multiple AI providers with automatic fallback and configurable behavior.

### Supported Providers
1. **OpenAI** (Default)
   - Model: GPT-5 Nano (configurable)
   - Fast, high-quality responses
   - Requires `OPENAI_API_KEY`

2. **Gemini**
   - Model: gemini-2.5-flash-lite (configurable)
   - Cost-effective alternative
   - Requires `GEMINI_API_KEY`

### Architecture
```
ai_service.py          # Main orchestrator
├── openai_api.py          # OpenAI provider implementation
├── gemini_api.py          # Gemini provider implementation
└── prompt_builder.py      # Shared prompt construction logic
```

### Configuration
Environment variables in `.env`:
```bash
AI_PROVIDER=openai           # "openai" or "gemini"
OPENAI_API_KEY=sk-...            # OpenAI API key
GEMINI_API_KEY=...               # Gemini API key
AI_OPENAI_MODEL=gpt-5-nano  # Model override (optional)
AI_GEMINI_MODEL=gemini-2.5-flash-lite  # Model override (optional)
AI_TIMEOUT_SECONDS=30       # API timeout
AI_BACKUP_DELAY_MINUTES=10       # Wait time before AI backup
```

### Key Features
- **Provider Selection**: Automatic based on config and available API keys
- **Fallback Logic**: Falls back to alternate provider if primary unavailable
- **Transaction Safety**: Proper transaction management in `run_backup_cycle()`
- **Validation**: All AI phrases validated same as human submissions
- **Error Handling**: Graceful degradation if AI services unavailable

### Implementation Status
- ✅ Provider infrastructure (OpenAI + Gemini)
- ✅ Shared prompt builder (eliminates duplication)
- ✅ Configuration system
- ✅ Error handling and fallbacks
- ✅ Phrase validation integration
- ⏸️ Background scheduler integration (Phase 3)
- ⏸️ AI voting support (Phase 3)

### Next Steps
1. Integrate with background job scheduler (Celery or APScheduler)
2. Add monitoring and metrics for AI usage
3. Implement AI voting for complete backup coverage
4. Add cost tracking and optimization
5. A/B testing between providers for quality comparison

---

## Quest System Implementation

### Overview
The quest system provides 16 achievement types that automatically track player progress and award bonus coins. All quest tracking is fully automated through integration with existing game services.

### Implementation Status
- ✅ **Database Models** - Quest and QuestTemplate tables with migration
- ✅ **Quest Service** - Complete implementation with all 16 quest types
- ✅ **Quest Templates** - Pre-seeded in database with rewards and targets
- ✅ **API Endpoints** - 5 endpoints for viewing and claiming quests
- ✅ **Service Integration** - Automatic tracking in vote, round, player, and feedback services
- ✅ **Transaction Integration** - Quest rewards create proper transaction records
- ✅ **Frontend API Types** - TypeScript types and API client methods
- 🔄 **Frontend UI** - Components and pages (IN PROGRESS)

### Quest Categories

**Streak Quests (3 quests)**:
- Hot Streak (5), Blazing Streak (10), Inferno Streak (20) - Consecutive correct votes

**Quality Quests (2 quests)**:
- Master Deceiver (75%+ copy votes), Clear Original (85%+ original votes)

**Activity Quests (4 quests)**:
- Quick/Active/Power Player (5/10/20 rounds in 24h), Balanced Player (varied round types)

**Engagement Quests (1 quest)**:
- Week Warrior (7 day login streak)

**Milestone Quests (6 quests)**:
- Feedback contributions, total votes/prompts/copies, popular phrasesets

### Automatic Integration Points
- **Vote Service** (`vote_service.py:283-294`, `vote_service.py:431-448`)
  - Updates hot streak after each vote
  - Checks milestone vote quests
  - Triggers quality quests on phraseset finalization

- **Round Service** (`round_service.py:186-194`, `round_service.py:424-432`)
  - Tracks round completion for activity quests
  - Increments prompt/copy milestone counters

- **Player Service** (`player_service.py:148-154`)
  - Updates login streak on daily bonus claims

- **Feedback Router** (`prompt_feedback.py:81-87`)
  - Increments feedback contribution quests

### Reward Economics
Total available quest rewards: **1,485f** across all 16 quests
- Encourages sustained engagement (login streaks, activity)
- Rewards skill (vote accuracy, quality performance)
- Provides long-term goals (milestones)

### Database Schema
```sql
quest_templates (
  template_id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100),
  description VARCHAR(500),
  reward_amount INTEGER,
  target_value INTEGER,
  category VARCHAR(20)
)

quests (
  quest_id UUID PRIMARY KEY,
  player_id UUID REFERENCES players,
  quest_type VARCHAR(50),
  status VARCHAR(20), -- active, completed, claimed
  progress JSON,      -- flexible tracking per quest type
  reward_amount INTEGER,
  created_at, completed_at, claimed_at TIMESTAMP
)
```

### API Endpoints
- `GET /quests` - List all quests with counts (active, completed, claimed)
- `GET /quests/active` - Get active quests only
- `GET /quests/claimable` - Get completed but unclaimed quests
- `GET /quests/{quest_id}` - Get single quest details
- `POST /quests/{quest_id}/claim` - Claim quest reward

See [QUEST_SYSTEM_PLAN.md](QUEST_SYSTEM_PLAN.md) for complete implementation details.

---

## Testing Considerations

### Load Testing Scenarios
1. **Queue Imbalance**: Simulate 100 prompt players, 10 copy players
2. **Voting Rush**: 20 voters hitting same word set simultaneously
3. **Grace Period**: Submissions arriving 1-6 seconds after expiry
4. **Copy Discount**: Toggle when queue crosses 10 threshold

### Edge Cases to Test
1. Player disconnects mid-round, reconnects
2. Two copy players submit identical words (both should be rejected for duplicate)
3. Word set receives exactly 3 votes and sits for 10 minutes
4. Word set receives 5 votes immediately (should trigger 60s window)
5. 20 voters queue up simultaneously (should cap at 20)
6. Player balance exactly \$100 or \$1 (boundary conditions)
7. Daily bonus at midnight boundary
8. Clock skew between client and server

### Economic Testing
1. Monitor average earnings by role (prompt/copy/voter)
2. Track queue wait times
3. Measure copy discount activation frequency
4. Validate prize pool math (should always sum correctly)
5. Detect economic exploits or imbalances

---

## Security Considerations

### Authentication & Authorization (Phase 1)
- **API Key-based**: UUID v4 keys, unique per player, stored securely
- **HTTPS only**: Enforce in production (Heroku provides this)
- **Header-based**: `X-API-Key` header required for all authenticated endpoints
- **Validation**: Check Authorization header (or legacy key) on every request, return 401 if invalid/missing
- **Rate limiting (Planned)**: Prevent brute force on tokens/keys, limit requests per identifier
- **No password storage**: MVP has no passwords, just keys (simpler, mobile-friendly)
- **Future**: Phase 2+ adds JWT with refresh tokens for enhanced security

### Anti-Cheat Measures
- Server-side timer validation (grace period but not exploitable)
- Prevent self-voting (check contributor IDs)
- Prevent duplicate voting (one vote per word set per player)
- Word validation server-side only (don't trust client)
- Transaction validation (ensure balance sufficient before deducting)

### Data Integrity
- **Atomic transactions**: All balance updates use database transactions
- **Idempotent prize collection**: ResultView table tracks payout_claimed flag
- **Transaction ledger**: Every balance change creates Transaction record with balance_after
- **Optimistic locking**: Prevent race conditions on concurrent operations
- **Distributed locks**: Use Redis (or fallback) for critical sections (balance updates, queue operations)

---

## Monitoring & Analytics

### Key Metrics to Track

**Economic Metrics:**
- Average payout by role (prompt/copy/voter)
- Win rate by role
- Player balance distribution
- Daily bonus claim rate
- Copy discount activation frequency
- Rake collected vs. prizes distributed

**Queue Health:**
- Prompts waiting for copies (alert if >20)
- Word sets waiting for votes (alert if >50)
- Average wait time: prompt → first copy
- Average wait time: word set creation → 3 votes
- Average wait time: 3 votes → finalization

**Player Engagement:**
- Daily active users
- Average rounds per player per day
- Round type distribution (prompt/copy/vote %)
- Retention: D1, D7, D30
- Churn: players reaching \$0 balance

**Performance:**
- API response times (p50, p95, p99)
- Failed submissions (by error type)
- Grace period usage frequency
- Timeout/abandonment rate by round type

**Game Balance:**
- Voter accuracy (% correct votes)
- Original vs. copy win rates
- Word similarity quality (measured by vote distribution)
- Most/least profitable prompts

### Alerts to Configure
1. Queue imbalance: >20 prompts waiting
2. Economic imbalance: any role avg payout <\$80 over 1000 rounds
3. Low voter participation: <3 votes per word set avg
4. High abandonment: >20% timeout rate
5. Server errors: >1% of requests failing
6. Balance depletion: >10% of active players under \$100

---

## Future Enhancements (Post-MVP)

### Gameplay Additions
1. **Difficulty Tiers**: Easy/Medium/Hard prompts with adjusted payouts
2. **Themed Rounds**: Holiday, pop culture, or category-specific prompts
3. **Team Mode**: 2v2 copy rounds with shared payouts
4. **Streak Bonuses**: Consecutive correct votes earn multipliers
5. **Power-ups**: "See one copy's vote distribution" for \$10
6. **Speed Bonuses**: Submit within 10 seconds for extra points

### Economic Features
1. **Subscription**: \$10/month for no rake on votes, daily \$200 bonus
2. **Tournaments**: Weekly competitions with prize pools
3. **Referral Bonuses**: \$50 for each friend who joins
4. **Bundle Pricing**: Buy 10 prompt rounds for \$900
5. **Dynamic Rake**: Lower rake during off-peak hours

### Social Features
1. **Friends System**: See friends' activity, challenge them
2. **Chat**: Post-round discussion of word choices
3. **Leaderboards**: Daily/weekly/all-time top earners
4. **Replay Sharing**: Share interesting word sets on social media
5. **Spectator Mode**: Watch live rounds (no voting)

### Advanced Matching
1. **Skill-Based Matching**: Match similar-skill copy players
2. **ELO Ratings**: Track player skill, display ranks
3. **Ranked Mode**: Competitive ladder with seasons
4. **Private Rooms**: Create custom games with friends

### Analytics for Players
1. **Personal Stats**: Win rates, favorite prompts, earnings over time
2. **Word History**: All words you've played, which got most votes
3. **Insights**: "Your copies fool voters 65% of the time"
4. **Achievements**: "Voted correctly 50 times in a row"

### Content Management
1. **User-Submitted Prompts**: Community creates prompts (moderated)
2. **Prompt Voting**: Rate prompts, promote good ones
3. **Seasonal Rotations**: Fresh prompt sets every month
4. **Banned Words**: Block inappropriate or problematic words
5. **Word of the Day**: Featured prompt with bonus payouts

---

## Database Indexes

### Suggested Indexes for Performance

**Players Table:**
- `player_id` (primary key)
- `api_key` (unique, indexed) - for authentication lookups
- `active_round_id` (for checking one-at-a-time constraint)
- `last_login_date` (for daily bonus queries)

**Rounds Table** (unified for prompt/copy/vote):
- `round_id` (primary key)
- `player_id` (for user's round history)
- `round_type` (for filtering by type)
- `status, created_at` (composite, for queue queries)
- `expires_at` (for timeout cleanup jobs)
- `prompt_round_id` (for copy rounds, linking to original)
- `phraseset_id` (for vote rounds, linking to assigned phraseset)

**Word Sets Table:**
- `phraseset_id` (primary key)
- `status, vote_count` (composite, for voting queue)
- `third_vote_at, fifth_vote_at` (for timeline calculations)
- `prompt_round_id, copy_round_1_id, copy_round_2_id` (for linking)

**Votes Table:**
- `vote_id` (primary key)
- `phraseset_id` (for aggregating votes)
- `player_id, phraseset_id` (composite unique, prevent duplicate voting)
- `created_at` (for vote timeline tracking)

**Transactions Table:**
- `transaction_id` (primary key)
- `player_id, created_at` (composite, for transaction history)
- `type` (for filtering by transaction type)
- `reference_id` (for linking to rounds/phrasesets)

**Result Views Table:**
- `player_id, phraseset_id` (composite unique, for idempotent collection)
- `payout_claimed` (for finding pending results)

---

### Visual Design Principles
1. **Clear Timers**: Large, visible countdown with color coding (green >30s, yellow 10-30s, red <10s)
2. **Cost Transparency**: Always show costs and potential earnings upfront
3. **Queue Visibility**: Show how many prompts/word sets are waiting
4. **Progress Indicators**: Show round status (submitted, waiting for results)
5. **Celebratory Feedback**: Animations for wins, uplifting messages
6. **Loss Mitigation**: Frame losses gently ("Better luck next time! Only -\$1")
7. **Discount Highlighting**: Make \$90 copy rounds visually prominent with badges

---

## Launch Checklist

### Pre-Launch Testing
- [ ] Load test with 1000 concurrent users
- [ ] Verify queue management under stress
- [ ] Test all timeout/abandonment scenarios
- [ ] Validate scoring math across 100+ word sets
- [ ] Test grace period edge cases
- [ ] Verify daily bonus logic across date boundaries
- [ ] Test copy discount activation/deactivation
- [ ] Security audit (SQL injection, XSS, auth bypass)
- [ ] Mobile browser compatibility (iOS Safari, Android Chrome)
- [ ] Network disconnection recovery testing

### Launch Day Prep
- [ ] Database backups automated
- [ ] Monitoring dashboards configured
- [ ] Alert thresholds set
- [ ] Customer support scripts prepared
- [ ] FAQ page published
- [ ] Terms of service and privacy policy finalized
- [ ] Payment processing (if real money) tested and certified
- [ ] Rate limiting plan documented (feature pending implementation)
- [ ] CDN configured for static assets
- [ ] Logging infrastructure ready

### Week 1 Monitoring
- [ ] Track queue balance hourly
- [ ] Monitor economic metrics daily
- [ ] Review player feedback and bug reports
- [ ] Adjust copy discount threshold if needed
- [ ] Watch for exploits or gaming patterns
- [ ] Measure voter accuracy and adjust point ratios if needed
- [ ] Track timeout/abandonment rates
- [ ] Ensure prize pools always balance correctly