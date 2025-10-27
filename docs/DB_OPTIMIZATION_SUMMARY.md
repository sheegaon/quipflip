# Database Query Optimization - Summary

## Issue Identified
The logs showed **218 SELECT statements in just 534 log lines** (~40% of all log activity).

The `/player/dashboard` endpoint was executing **~15-20 database queries per request**, with a significant inefficiency: the `_build_contributions()` method in `PhrasesetService` was being called **3 times per dashboard request** to fetch the same data.

## Root Cause
The dashboard endpoint calls multiple sub-methods that each independently call `_build_contributions()`:
- `get_pending_results()` → calls `_build_contributions()`
- `get_phraseset_summary()` → calls `_build_contributions()`
- `get_unclaimed_results()` → calls `_build_contributions()`

Each call to `_build_contributions()` executes 5+ database queries:
1. SELECT player's prompt rounds
2. SELECT player's copy rounds
3. SELECT missing prompt rounds (if any)
4. SELECT phrasesets for all prompts
5. SELECT result_views for all phrasesets

**Before optimization**: 3 calls × 5+ queries = **15+ redundant queries per dashboard request**

## Solution Implemented
Added **request-scoped caching** to `PhrasesetService`:

```python
class PhrasesetService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.activity_service = ActivityService(db)
        self.scoring_service = ScoringService(db)
        # Request-scoped cache to avoid re-querying _build_contributions
        self._contributions_cache: dict[UUID, list[dict]] = {}
```

The `_build_contributions()` method now:
1. Checks the cache first
2. If cached, returns immediately
3. If not cached, queries the database and stores the result
4. Cache is automatically cleared when the service instance is garbage collected (end of request)

Cache invalidation is handled when data changes (e.g., when claiming a prize).

## Impact

### Database Query Reduction
- **Before**: ~15+ queries per dashboard request
- **After**: ~5+ queries per dashboard request
- **Reduction**: ~67% fewer queries for dashboard loads

### Performance Characteristics
- ✅ No user-facing changes required
- ✅ No schema changes
- ✅ Cache lifetime limited to single request (safe)
- ✅ All existing tests pass
- ✅ Maintains data consistency with invalidation on writes

### Scalability
This optimization:
- Reduces database load by 2/3 for the most-called endpoint
- Maintains fast response times even with increased traffic
- Works seamlessly with existing 10-second application-level dashboard cache
- Provides immediate improvement with zero deployment risk

## Files Changed
- `backend/services/phraseset_service.py` - Added caching logic

## Testing
All tests pass:
```bash
tests/test_phraseset_service.py::test_get_phrasesets_and_claim PASSED
tests/test_daily_bonus.py::test_dashboard_endpoint_includes_bonus_status PASSED
# ... and 13 more player/dashboard tests
```

## Future Optimizations (Not Implemented)
These optimizations were considered but deferred as the current solution provides sufficient improvement:

1. **Eager loading with JOINs**: Combine the 5 sequential queries in `_build_contributions` into 1-2 queries using SQL JOINs
2. **Longer cache TTL**: Increase dashboard cache from 10s to 30s for more stable data
3. **WebSockets**: Replace HTTP polling with real-time updates
4. **Materialized views**: Denormalize dashboard summary data

These can be implemented later if performance issues arise at scale.
