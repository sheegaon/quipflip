# Comprehensive Review of Service Layer

Based on review of [round_service.py](backend/services/round_service.py), [phraseset_service.py](backend/services/phraseset_service.py), [GAME_RULES.md](docs/GAME_RULES.md), and related files, this document identifies opportunities for improvement across code quality, efficiency, and algorithmic optimization.

## Table of Contents
- [round_service.py Issues](#round_servicepy-issues)
- [phraseset_service.py Issues](#phraseset_servicepy-issues)
- [vote_service.py Issues](#vote_servicepy-issues)
- [Recommendations Summary](#recommendations-summary)

## round_service.py Issues

### Critical Issues

### 1. ~~UUID String Inconsistency Bug~~ ✅ **FIXED**
- ~~The code tries to handle both hyphenated and non-hyphenated UUID strings due to SQLite inconsistencies~~
- ~~This is a workaround for a data quality issue that should be fixed at the source~~
- ~~The raw SQL update is error-prone and bypasses ORM benefits~~
- **Resolution**: Prompt usage count updates now use ORM with SQLAlchemy's `update()` statement, eliminating brittle string matching and leveraging proper UUID handling from the adaptive column type.

### 2. ~~N+1 Query Risk in `start_copy_round`~~ ✅ **FIXED**
- ~~The retry loop can execute up to 10 database queries fetching individual rounds~~
- ~~Each iteration loads a Round object just to check if it's valid~~
- ~~This becomes inefficient under high load~~
- **Resolution**: Queue pops now performed in batches using `get_next_prompt_round_batch()` with bulk database hydration. Each batch only incurs a single round fetch, keeping retry logic efficient while preserving FIFO order.

### 3. ~~Repeated Pattern: Timezone-Aware Conversions~~ ✅ **FIXED**
- ~~The same timezone normalization pattern is repeated 3+ times~~
- ~~Should be extracted to a utility function~~
- **Resolution**: Added shared `ensure_utc()` helper function that normalizes timestamps for SQLite-derived values, eliminating duplicated conversion logic across multiple methods.

### Efficiency Improvements

### 4. Queue Rehydration Locking (Lines 948-1009)
- ✅ **Update:** `_rehydrate_prompt_queue` now acquires the shared `rehydrate_prompt_queue`
  lock with a 5-second timeout, double-checks the queue length after entering the
  critical section, and skips the expensive rehydration when another worker already
  filled the queue.
- Further improvements could include instrumentation around rehydration duration and
  queue length trends to catch slow refills early.

### 5. Complex Subquery in `start_prompt_round` (Lines 71-121)
- Three separate subqueries with UNION could be optimized
- Consider using a single CTE or temporary table for large player histories

### 6. Duplicate Flush Calls
- Multiple `await self.db.flush()` followed by `await self.db.commit()` in transactions
- Flush before commit is often redundant since commit includes flush

### Code Quality & Maintainability

### 7. ~~Method Length~~ ✅ **FIXED**
- `start_prompt_round` now delegates to `_select_prompt_for_player()` and
  `_create_prompt_round()`, reducing the orchestration method to 24 lines while
  keeping lock acquisition easy to follow.
- `start_copy_round` is down to 38 lines and hands off to helpers such as
  `_calculate_copy_round_cost()`, `_get_next_valid_prompt_round()`, and
  `_create_copy_round()` for the heavy lifting.
- Queue prefetching, eligibility checks, and locking are encapsulated in
  dedicated helpers, so each unit is independently testable.

### 8. ~~Magic Numbers~~ ✅ **FIXED**
- Retry counts, lock timeouts, and pricing thresholds are now sourced from
  `Settings` (for example `copy_round_max_attempts` and
  `round_lock_timeout_seconds`).
- Copy-round pricing looks up `QueueService.get_copy_cost()`, which respects the
  configured discount threshold rather than hard-coded values.

### 9. Error Handling Inconsistency
- Some methods use custom exceptions, others use generic `ValueError`
- Logging levels vary (debug vs info vs warning)

### 10. Denormalized Data Validation (Lines 717-731)
- Good defensive checks, but indicates potential data integrity issues
- Consider database constraints or triggers

### Algorithmic Improvements

### 11. Available Prompts Query (Lines 869-921)
- Complex raw SQL with multiple CTEs
- Could benefit from query result caching with short TTL
- Consider materializing frequently-queried data

### 12. Copy Round Assignment Algorithm
- Sequential retry with queue push/pop creates contention
- Could use a "claim and validate" pattern with timeout
- Consider priority queue for prompts about to expire

### 13. Grace Period Checks
- Repeated grace period validation could be centralized
- Consider a Round method `is_within_grace_period()`

### Security & Data Integrity

### 14. Race Conditions
- Locking is much more consistent: `_lock_prompt_round_for_update()` and the
  abandonment/flagging paths now rely on `SELECT ... FOR UPDATE` to guard prompt
  rows before mutating them.
- Balance adjustments still mix explicit commits with implicit flushes; the
  transaction story would benefit from revisiting how `TransactionService` and
  round updates coordinate rollbacks.

### 15. Transaction Boundaries
- Some methods commit multiple times (e.g., lines 242, 508)
- Could lead to partial state if second commit fails
- Consider consolidating commits where possible

### Performance Optimizations

### 16. Cache Invalidation Pattern (Lines 185-187, 255-257, etc.)
- Good pattern, but could batch invalidations
- Consider cache warming after invalidation for hot paths

### 17. Prompt Usage Count Update (Lines 169-178)
- Raw SQL for a simple counter increment
- Could use ORM with optimistic locking or `update().values(usage_count=Prompt.usage_count + 1)`
- **Status: Fixed.** The counter now uses a SQLAlchemy `update` expression so increments occur atomically without bypassing ORM safety guarantees.

### 18. Activity Service Calls
- Multiple individual activity records in `submit_copy_phrase`
- Could batch activity logging

### Testing & Observability

### 19. Logging Verbosity
- Excellent detailed logging throughout
- Consider structured logging (JSON) for production observability
- Some debug logs could be conditional on log level

### 20. Metrics
- No timing metrics for critical paths (e.g., round assignment latency)
- Should instrument queue wait times, retry counts

---

## phraseset_service.py Issues

### Critical Issues

#### 21. ~~N+1 Query Problem in `_build_contributions`~~ ✅ **FIXED**
**Severity: High**
- ~~Loads all prompt rounds for a player (line 362-368)~~
- ~~Loads all copy rounds for a player (line 371-377)~~
- ~~Then iterates through each phraseset calling `calculate_payouts` individually (lines 424, 465)~~
- ~~For a player with 50 phrasesets, this triggers 50+ separate payout calculations~~
- ~~Each payout calculation may trigger additional queries via `scoring_service`~~
- **Resolution**: Implemented `scoring_service.calculate_payouts_bulk()` that batches all phraseset payout calculations. Pre-loads all votes and rounds with 2 queries, then calculates payouts in memory. Eliminates N+1 pattern completely.

#### 22. ~~Missing Line Between Method~~ ✅ **FIXED**
**Severity: Low - Code Style**
- ~~Missing blank line before `_extract_player_payout` method definition~~
- ~~Violates PEP 8 style guidelines~~
- **Resolution**: Added missing blank line for consistency with project style.

#### 23. ~~Inefficient Multiple Database Round Loads~~ ✅ **FIXED**
**Severity: Medium**
- ~~`_load_contributor_rounds` makes 3 separate `db.get()` calls~~
- ~~Should use a single query with `select().where(Round.round_id.in_([...]))`~~
- ~~Called multiple times per request in detail views~~
- **Resolution**: Refactored `_load_contributor_rounds()` to use single query with `Round.round_id.in_()`, reducing 3 queries to 1. Returns dictionary mapping for efficient lookups.

### Efficiency Improvements

#### 24. Request-Scoped Cache is Good But Limited (Lines 27-33)
**Strengths:**
- Smart use of request-scoped cache for `_build_contributions`
- Prevents redundant queries within a single request
- Good invalidation pattern

**Limitations:**
- Cache is service-instance scoped, not shared across requests
- No TTL or size limits (could grow unbounded in long-lived instances)
- Payout cache is per-method, not shared across service

#### 25. Redundant Phraseset Status Queries
- Multiple calls to `phraseset.status == "finalized"` checks (lines 201, 247, 423, 464)
- Status is immutable once set; could cache in request context

#### 26. Repeated Player Loading Pattern (Lines 539-555)
**Good:** Merges into existing mapping to avoid duplicates
**Opportunity:** Could use a service-level LRU cache for player metadata since usernames/pseudonyms rarely change

#### 27. Duplicate Payout Calculation Logic (Lines 424-427, 464-468)
- Identical code block repeated for prompt and copy rounds
- Should extract to helper method `_get_player_payout_with_fallback`

### Code Quality & Maintainability

#### 28. ~~Method Complexity: `_build_contributions` (148 lines)~~ ✅ **FIXED**
- ~~Does too much: loads rounds, loads phrasesets, loads result views, calculates payouts, builds output~~
- ~~Difficult to test individual pieces~~
- ~~Hard to optimize specific parts~~
- **Resolution**: `_build_contributions` now delegates to `_load_prompt_rounds_for_player`, `_load_copy_rounds_for_player`, `_load_phrasesets_for_prompts`, and targeted builders for prompt/copy entries. The orchestration function shrank by ~40 lines and each helper is testable in isolation.

#### 29. Method Complexity: `get_phraseset_details` (144 lines)
**Similar issues:**
- Too many responsibilities: validation, loading, transforming, serializing
- Should extract sub-methods for each logical section

#### 30. Inconsistent Error Handling
- Generic `ValueError` used throughout (lines 150, 160, 295, 297, 306, 507)
- Should use custom exceptions: `PhrasesetNotFoundError`, `NotContributorError`, `PhrasesetNotFinalizedError`
- Better for API error response handling

#### 31. Status String Mapping Duplication (Lines 51-56, 593-607)
- `STATUS_BUCKETS` defined inline in `get_player_phrasesets`
- Similar mappings in `_derive_status`
- Should centralize status logic in a StatusMapper class or constants file

#### 32. Magic Numbers and Strings
- Line 40: `limit: int = 50` - default pagination size should be in config
- Line 68: Slice syntax `[offset: offset + limit]` - could use itertools.islice for consistency
- Status strings scattered throughout ("finalized", "open", "closing", etc.) - should be Enum

### Algorithmic Improvements

#### 33. ~~O(n²) Filter Complexity (Lines 46-66)~~ ✅ **FIXED**
- `get_player_phrasesets` now performs role/status filtering in a single
  list comprehension, keeping the operation O(n) while preserving readability.

#### 34. Sort After Filter (Line 494)
- Sorts all contributions, then filters/paginates in calling method
- More efficient: filter first, then sort only the subset needed
- For large result sets, wastes sorting on data that gets filtered out

#### 35. Payout Cache Pattern Could Be Service-Wide (Lines 557-565)
- Each method creates its own payout cache dictionary
- Could maintain a service-level LRU cache keyed by phraseset_id
- Would benefit repeated calls across different methods

#### 36. Vote Counting Logic (Lines 628-638)
- Iterates through all votes to count by phrase
- Could use `collections.Counter` for cleaner, more efficient code
- Or better: store counts in database when vote is recorded

### Security & Data Integrity

#### 37. No Transaction Management in `claim_prize` (Lines 287-333)
- Multiple database operations without explicit transaction boundaries
- Lines 317, 319: Two separate commits
- If second commit fails, could have inconsistent state

#### 38. ~~Race Condition in Result View Creation (Lines 524-536)~~ ✅ **FIXED**
- ~~Check-then-create pattern without locking~~
- ~~Two concurrent requests could both see missing result_view~~
- **Resolution**: Result view creation now performs an idempotent upsert (`ON CONFLICT DO NOTHING` / `INSERT OR IGNORE`) and reloads the persisted row inside the same transaction, preventing duplicate inserts while keeping payout amounts current.

#### 39. Missing Validation in `is_contributor` (Lines 335-345)
- Returns False for invalid phraseset_id
- Should distinguish between "not found" and "not a contributor"
- Silent failures make debugging harder

### Performance Optimizations

#### 40. ~~Missing Database Indexes~~ ✅ **FIXED**
- ~~Queries filter by `Round.player_id` + `Round.round_type` (line 364, 374)~~
- ~~Should have composite index: `(player_id, round_type, status)`~~
- **Resolution**: Added composite index `ix_rounds_player_type_status` via migration `e6b0d1f2c3a4` to cover the phraseset summary filter patterns.

#### 41. Unnecessary `db.refresh()` Call (Lines 322-323)
- After committing, refreshes player object
- Not clear why refresh is needed here
- If balance needs updating, should be explicit

#### 42. Defensive Datetime Conversion Overhead (Lines 640-646)
- `_ensure_utc` called on every datetime field in every result
- If database properly stores timezone-aware datetimes, this is redundant
- Should fix at ORM configuration level instead

#### 43. Activity Loading Not Optimized (Line 231)
- Delegates to activity_service without pagination
- For old phrasesets with many activities, could be slow
- Should add optional limit parameter

### Testing & Observability

#### 44. No Logging
- Zero logging statements in entire file
- Makes debugging production issues difficult
- Should log at minimum:
  - Cache hits/misses
  - Query performance (slow queries)
  - Errors and exceptions
  - Prize claims and result views

#### 45. No Metrics/Instrumentation
- No timing for expensive operations (`_build_contributions`)
- No counters for cache effectiveness
- No alerts for N+1 query patterns
- Should add OpenTelemetry or similar

#### 46. Complex Business Logic Without Tests
- Status derivation logic (lines 590-607)
- Payout extraction logic (lines 566-571)
- Filter combinations (lines 46-66)
- These are pure functions that should have comprehensive unit tests

### Data Modeling Issues

#### 47. Denormalized Data Without Validation
- Phraseset stores denormalized copies of prompt_text, phrases
- No validation that denormalized data matches source
- If source Round is updated, Phraseset is stale
- Should either: (1) make source immutable, or (2) add consistency checks

#### 48. Result View Payout Discrepancy Logic (Lines 204-205, 426-427, 467-468)
- Trusts `result_view.payout_amount` over calculated payouts if present
- Why would these differ? Indicates data integrity issue
- Should investigate root cause and fix, not work around

#### 49. Implicit vs Explicit Status (Lines 590-607)
- Complex logic to derive status from multiple sources
- Should have single source of truth for phraseset status
- Current approach causes confusion and bugs

---

## vote_service.py Issues

### Critical Issues

#### 50. ~~N+1 Query in Contributor Validation~~ ✅ **FIXED**
**Severity: High**
- ~~`submit_system_vote` loads 3 rounds individually: `await self.db.get(Round, round_id)` in loop (lines 315)~~
- ~~`submit_vote` reloads entire phraseset with relationships despite already having it (lines 454-464)~~
- ~~Should batch-load all contributor rounds in a single query~~
- ~~This pattern is repeated twice in the same file~~
- **Resolution**: Contributor IDs are now fetched by `_get_contributor_ids()` using a single batched query reused by `submit_system_vote` and `submit_vote`.

#### 51. ~~Duplicate Contributor Validation Logic~~ ✅ **FIXED**
**Severity: Medium**
- ~~Nearly identical contributor checking code in `submit_system_vote` and `submit_vote`~~
- ~~Lines 306-318 use lazy loading with `db.get()`~~
- ~~Lines 449-476 use eager loading with `selectinload()`~~
- ~~Should extract to helper method: `_get_contributor_ids(phraseset_id) -> set[UUID]`~~
- **Resolution**: Both `submit_system_vote` and `submit_vote` delegate to `_get_contributor_ids()` so the validation logic is shared.

#### 52. ~~Phraseset Finalization Check Runs on Every Count~~ ✅ **FIXED**
**Severity: High - Performance**
- ~~`count_available_phrasesets_for_player` calls `_check_and_finalize_active_phrasesets()`~~
- ~~This method loads ALL active phrasesets and checks finalization criteria for each~~
- ~~Called frequently (dashboard loads, API polling)~~
- ~~Can trigger 10+ database queries per count request~~
- **Resolution**: Finalization checks are throttled behind a shared async lock and configurable interval (`vote_finalization_refresh_interval_seconds`). Requests reuse cached results and only trigger a new scan once per interval, removing the expensive per-request work.

#### 53. ~~Orphaned Phraseset Error Handling~~ ✅ **FIXED**
**Severity: Medium - Data Integrity**
- ~~Catches "missing round references" errors and logs warning~~
- ~~Leaves orphaned phrasesets in limbo (never finalized, never cleaned up)~~
- ~~Comment says "let manual cleanup handle it" but provides no cleanup mechanism~~
- ~~Should mark as failed/abandoned or have automated cleanup~~
- **Resolution**: Orphaned phrasesets are now marked `closed`, annotated with a `finalization_error` activity entry, and committed immediately so they are excluded from future processing.

### Efficiency Improvements

#### 54. ~~Double Phraseset Loading~~ ✅ **FIXED**
- `_load_available_phrasesets_for_player()` now applies all contributor and
  relationship filters in SQL using correlated EXISTS subqueries before the
  rows ever reach Python.
- The method still logs missing relationships up front so we can track data
  integrity problems without losing visibility.

#### 55. ~~Redundant Already-Voted Query~~ ✅ **FIXED**
- The correlated EXISTS that filters out players who already voted now lives in
  the main availability query, so we avoid the follow-up round trip entirely.
- Early exits still happen when the SQL query returns no candidates, keeping the
  hot path lean.

#### 56. Vote Counting in Python (Lines 892-906)
**Inefficiency:**
- Loads all votes with player relationships (line 885-890)
- Counts votes per phrase in Python loop (lines 903-906)
- Should use SQL aggregate query: `SELECT voted_phrase, COUNT(*) ... GROUP BY voted_phrase`

#### 57. Unnecessary Refresh After Commit (Lines 268, 414, 583, 868, 882)
**Pattern:**
- Multiple `await self.db.refresh()` calls after commit
- Lines 268, 414, 583: Refresh object that won't be used again
- Adds extra database query for no benefit
- Only refresh if subsequent code needs updated data

### Code Quality & Maintainability

#### 58. Method Complexity: `submit_vote` (184 lines)
**Issues:**
- Too many responsibilities: validation, contributor check, vote creation, payout, timeline update, finalization check, quest tracking
- Lines 422-606 do 8+ different things
- Difficult to test individual pieces

**Suggested breakdown:**
- `_validate_vote_timing(round)` - grace period check
- `_validate_phrase_choice(phrase, phraseset)` - valid phrase check
- `_process_vote_submission(...)` - core vote logic
- `_update_guest_vote_tracking(...)` - guest lockout logic

#### 59. Method Complexity: `get_phraseset_results` (168 lines)
**Issues:**
- Lines 795-963: loads phraseset, validates contributor, creates/updates result view, calculates points, builds response
- Should extract sub-methods for each logical section

#### 60. Method Complexity: `_check_and_finalize_active_phrasesets` (66 lines)
**Issues:**
- Lines 145-210: loads phrasesets, checks each one, handles errors, logs results
- Mixed abstraction levels (high-level orchestration + detailed error handling)
- Should extract error handling to separate method

#### 61. Inconsistent Error Types
- Lines 476, 488, 808, 811, 820, 822, 824, 833: Generic `ValueError`
- Lines 230, 346, 447, 497: Custom exceptions (NoPhrasesetsAvailableError, AlreadyVotedError, etc.)
- Should consistently use custom exceptions for domain errors

#### 62. Magic Numbers
- Line 235: `timeout=10` - lock timeout should be in config
- Lines 778, 783: Hardcoded `20` votes for quest (should use `settings.vote_max_votes`)
- Line 156: `order_by(Phraseset.created_at.asc())` - processing order should be configurable

#### 63. Duplicate Prize Pool Update Logic (Lines 383-391, 553-561)
**Duplication:**
- Identical prize pool calculation in `submit_system_vote` and `submit_vote`
- 9 lines of code repeated verbatim
- Should extract to: `_update_phraseset_prize_pool(phraseset, correct, payout)`

### Algorithmic Improvements

#### 64. Priority-Based Selection Algorithm (Lines 99-129)
**Good design but inefficient:**
- Loads ALL available phrasesets (could be 100+)
- Filters and sorts in Python three times (priority1, priority2, priority3)
- Better: single query with priority-based ORDER BY:
```sql
ORDER BY
  CASE
    WHEN vote_count >= 5 THEN 1
    WHEN vote_count >= 3 THEN 2
    ELSE 3
  END,
  CASE
    WHEN vote_count >= 5 THEN fifth_vote_at
    WHEN vote_count >= 3 THEN third_vote_at
    ELSE RANDOM()
  END
LIMIT 1
```

#### 65. Finalization Check Algorithm (Lines 655-703)
**Inefficiency:**
- Three separate condition checks with datetime arithmetic
- Could optimize with single calculation:
```python
windows = {
    'max_votes': (vote_count >= max, 0),
    'closing': (vote_count >= closing_threshold, closing_window_elapsed),
    'minimum': (vote_count >= min_threshold, min_window_elapsed)
}
should_finalize = any(count_met and time_met for count_met, time_met in windows.values())
```

#### 66. Contributor Map Building (Lines 826-835)
**Good:** Clean logic
**Opportunity:** Could be cached per phraseset (contributor IDs don't change)
- Same contributor map rebuilt multiple times across service methods

### Security & Data Integrity

#### 67. Missing Phraseset Relationship Validation (Lines 58-66)
**Good:** Defensive check for missing relationships
**Issue:** Logs warning but doesn't prevent future issues
- Should either: (1) add DB foreign key constraints, or (2) mark phraseset as invalid
- Currently silently skips broken data which hides underlying bug

#### 68. ~~Race Condition in Result View (Lines 837-868)~~ ✅ **FIXED**
- ~~Check-then-create pattern without locking (line 843-846)~~
- ~~Two concurrent calls could create duplicate result views~~
- **Resolution**: Result view creation now reuses the idempotent upsert helper so concurrent requests share the same row while refreshing payout/timestamp fields without integrity errors.

#### 69. Guest Vote Lockout Not Atomic (Lines 527-544)
**Issue:**
- Updates `consecutive_incorrect_votes` and `vote_lockout_until` without transaction isolation
- If commit fails after incrementing counter, player loses correct vote count
- Could lead to premature lockout

#### 70. Transaction Boundaries Unclear (Lines 405-413, 574-582)
**Pattern:**
- Calls multiple service methods with `auto_commit=False`
- Then single commit at end
- Good: atomic transactions
- Risk: If any intermediate step fails, rollback leaves partial state
- Should wrap entire block in try-except with explicit rollback

### Performance Optimizations

#### 71. Redundant Prompt Round Loading (Lines 615, 637, 752)
**Pattern:**
- `_update_vote_timeline` loads prompt round (line 615)
- Then `check_and_finalize` → `_finalize_phraseset` loads it again (line 752)
- Should pass prompt round as parameter or cache in request context

#### 72. Missing Database Indexes
**Needed indexes:**
- `Vote.phraseset_id` + `Vote.player_id` (for already-voted check, line 89-93)
- `Phraseset.status` + `Phraseset.fifth_vote_at` (for priority selection, line 112-115)
- `Phraseset.status` + `Phraseset.third_vote_at` (for priority selection, line 118-121)
- `Phraseset.status` + `Phraseset.created_at` (for finalization check, line 153-157)

#### 73. Over-fetching with selectinload (Lines 45-49, 888)
**Issue:**
- Loads full Round objects with all fields when only need player_id
- Lines 45-49: Load 3 full rounds per phraseset when only need player_ids
- Line 888: Load full Player objects when only need username
- Should use `load_only()` or raw SQL with specific columns

#### 74. Quest Service Called Sequentially (Lines 586-596, 768-786)
**Inefficiency:**
- Multiple quest checks called one after another
- Lines 589-594: 3 sequential quest checks
- Could be called in parallel with asyncio.gather()
- Or better: batch into single quest check method

### Testing & Observability

#### 75. Good Logging But Could Be Better
**Strengths:**
- Comprehensive logging at key points (lines 274, 416, 602, etc.)
- Includes context (IDs, values, outcomes)

**Improvements:**
- Missing query performance metrics
- No logging of slow finalization checks
- Quest errors logged but no alerting
- Should add structured logging with correlation IDs

#### 76. Error Handling Swallows Quest Failures (Lines 595-596, 785-786)
**Issue:**
- Quest failures caught and logged but don't affect main flow
- Lines 595-596: "Failed to update quest progress for vote"
- This is good for availability but bad for data consistency
- Should have monitoring alerts for repeated quest failures

#### 77. Defensive Logging for Data Issues (Lines 60-65, 734-738)
**Good pattern:**
- Logs data integrity issues (missing relationships, missing players)
- Helps identify bugs in production

**Missing:**
- No metrics/counters for these warnings
- Should track frequency of data integrity issues
- Should alert if frequency exceeds threshold

### Data Modeling Issues

#### 78. Phraseset Missing Helper Properties
**Observation:**
- Lines 780: `phraseset.original_player_id` - this field doesn't exist in model
- Should be extracted from `prompt_round.player_id`
- Suggests need for computed properties or helper methods on Phraseset model

#### 79. Vote Timeline Coupling (Lines 608-653)
**Issue:**
- Vote timeline updates coupled to prompt_round.phraseset_status
- Lines 616-617, 638: Updates prompt_round status as side effect
- This creates hidden dependencies between models
- Should use event system or separate status sync method

#### 80. Already Collected Flag Confusion (Line 948)
**Issue:**
- Returns `already_collected: result_view.result_viewed`
- But payouts are auto-distributed at finalization (line 870 comment)
- Name "already_collected" implies manual collection but it's automatic
- Misleading field name causes confusion

## Recommendations Summary

### High Priority (Immediate Impact)

**round_service.py:**
- ~~Extract timezone normalization to utility function (#3)~~ ✅
- ~~Fix UUID string handling at data layer (migration or seed script) (#1)~~ ✅
- ~~Optimize queue batch processing to eliminate N+1 queries (#2)~~ ✅
- ~~Improve queue rehydration locking with timeout and double-check (#4)~~ ✅
- ~~Refactor `start_copy_round` and `start_prompt_round` into smaller methods (#7)~~ ✅ (orchestration now pushes queue prefetching, locking, and DB writes into helpers)
- ~~Add pessimistic locking to more critical sections (#14)~~ ✅ (prompt/copy submissions now lock rows with `SELECT ... FOR UPDATE` before mutating state)
- ~~Move magic numbers to config (#8)~~ ✅ (retry counts/lock timeouts sourced from `Settings`)

**phraseset_service.py:**
- ~~Fix N+1 query in `_build_contributions` - batch payout calculations (#21)~~ ✅
- ~~Optimize `_load_contributor_rounds` to single query (#23)~~ ✅
- ~~Fix race condition in result view creation (#38)~~ ✅
- ~~Add composite database index on (player_id, round_type, status) (#40)~~ ✅
- ~~Break down `_build_contributions` into smaller methods (#28)~~ ✅

**vote_service.py:**
- ~~Fix N+1 query in contributor validation - batch load rounds (#50)~~ ✅
- ~~Extract duplicate contributor validation logic (#51)~~ ✅
- ~~Handle orphaned phrasesets properly (#53)~~ ✅
- ~~Throttle phraseset finalization sweeps so they stay off the request path (#52)~~ ✅ (interval-gated async lock keeps heavy work off the hot path)
- ~~Add SQL-level filtering for available phrasesets (#54)~~ ✅ (EXISTS-based filtering in `_load_available_phrasesets_for_player`)
- ~~Fix race condition in result view creation (#68)~~ ✅
- ~~Add missing database indexes for vote queries (#72)~~ ✅ (covered by migrations `1c2b3a4d5e67` and `e6b0d1f2c3a4`)

### Medium Priority (Significant Improvement)

**round_service.py:**
- Optimize copy round retry algorithm (claim-and-validate pattern) (#12)
- Cache frequently-queried player eligibility data (#11)
- Consolidate transaction commits (#15)
- Add query performance metrics (#20)

**phraseset_service.py:**
- Implement service-level LRU cache for player metadata (#26)
- Implement service-level LRU cache for payouts (#35)
- Add custom exception classes for better error handling (#30)
- Fix transaction boundaries in `claim_prize` (#37)
- Add comprehensive logging throughout (#44)
- Centralize status mapping logic (#31)

**vote_service.py:**
- Break down `submit_vote` into smaller methods (#58)
- Optimize priority-based phraseset selection with SQL (#64)
- Extract duplicate prize pool update logic (#63)
- Use SQL for vote counting instead of Python loops (#56)
- Reduce unnecessary db.refresh() calls (#57)
- Parallelize quest service calls with asyncio.gather() (#74)

### Low Priority (Polish & Technical Debt)

**round_service.py:**
- Batch activity logging (#18)
- Implement structured logging (#19)
- Extract common grace period validation (#13)
- Consider query result caching for `get_available_prompts_count` (#11)

**phraseset_service.py:**
- Extract duplicate payout logic to helper (#27)
- Combine filter functions for efficiency (#33)
- Use collections.Counter for vote counting (#36)
- Add instrumentation/metrics (#45)
- Fix datetime conversion overhead at ORM level (#42)
- Investigate payout amount discrepancies (#48)
- Convert status strings to Enum (#32)
- Add pagination to activity loading (#43)

**vote_service.py:**
- Optimize over-fetching with load_only() (#73)
- Cache contributor map per phraseset (#66)
- Eliminate redundant prompt round loading (#71)
- Add explicit rollback handling in transactions (#70)
- Fix "already_collected" naming confusion (#80)
- Decouple vote timeline from prompt_round status (#79)
- Add monitoring for quest failures (#76)
- Add metrics for data integrity warnings (#77)

### Code Quality Improvements (All Services)

1. **Custom Exception Hierarchy**: Create domain-specific exceptions (vote_service.py #61)
2. **Status Enums**: Replace magic strings with typed enums (#32)
3. **Configuration Centralization**: Move all magic numbers to config (#32, #62)
4. **Logging Standards**: Implement structured logging with correlation IDs (#19, #75)
5. **Metrics**: Add OpenTelemetry instrumentation (#20, #45)
6. **Unit Tests**: Add tests for pure business logic functions (#46)
7. **Documentation**: Add docstring examples and complexity notes
8. **Extract Common Patterns**: Contributor validation, prize pool updates, payout logic (#51, #63)
9. **Database Constraints**: Add foreign keys and unique constraints to prevent data integrity issues (#67)
10. **Background Jobs**: Move expensive checks out of request path (cleanup) (#53)

## Summary Statistics

**Total Issues Identified: 80**
- **Fixed: 20 issues (25%)** ✅
- **Remaining: 60 issues (75%)**

**Critical coverage:** All critical blockers called out in the original review
(#1-#3, #21-#23, #50-#53) now have merged fixes. Follow-up work is concentrated on
performance optimizations, transaction hygiene, and observability gaps.

**Outstanding focus areas:**
- **Maintainability Debt**: #28, #29, #58, #59 (large orchestration methods still
  mix validation, transformation, and side effects).
- **Operational Risk**: #44, #75, #76, #77 (lack of structured logging and
  metrics makes it hard to spot regressions in production).
- **Data Integrity**: #67 and #69 (deeper enforcement of phraseset
  relationships and guest vote lockouts remains to be tackled).
- **Performance**: #11, #12, #34, #56, #64 (further SQL tuning and caching
  opportunities are on deck).

## Recent Improvements (Merged)

### Round service updates
- `ensure_utc()` centralizes timezone normalization before timestamps leave the
  service layer (#3).
- Copy-round orchestration delegates queue pops to
  `QueueService.get_next_prompt_round_batch()` and prefetches prompt metadata in
  bulk (#2).
- `_lock_prompt_round_for_update()` applies consistent pessimistic locking
  before mutating prompt rounds, preventing mid-flight races (#14).

### Phraseset service updates
- `_build_contributions()` now composes results from targeted loaders (prompt
  rounds, copy rounds, payouts, and result views) and caches the assembled list
  per request to avoid redundant queries (#21, #23, #28).
- `ScoringService.calculate_payouts_bulk()` replaces per-phraseset payout calls,
  removing the worst of the N+1 patterns (#21).
- Result-view creation funnels through a shared `upsert_result_view()` helper so
  duplicate inserts are ignored safely (#38).

### Vote service updates
- Contributor validation reuses `_get_contributor_ids()` so both
  `submit_vote()` and `submit_system_vote()` share a single batched query (#50,
  #51).
- `_ensure_recent_finalization()` throttles heavy finalization sweeps behind an
  async lock while `_handle_orphaned_phraseset()` retires broken records and
  logs an explicit activity entry (#52, #53).
- Result-view creation and guest vote handling reuse the same upsert helper used
  by the phraseset service, eliminating check-then-insert races (#68).

### Queue and helper utilities
- `QueueService.get_next_prompt_round_batch()` and `queue_client.pop_many()`
  allow efficient FIFO batch pops used by the round service (#2).
- Queue logging now records queue length before/after pops, giving better
  visibility during load testing.
