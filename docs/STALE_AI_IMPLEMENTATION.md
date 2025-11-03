# Stale AI Handler Implementation Plan

## Implementation Status

**STATUS: ✅ PRODUCTION READY**

All "Must Have" items for production deployment have been completed:
- ✅ Core infrastructure (Phase 1)
- ✅ Metrics tracking for copy and vote operations
- ✅ Queue re-enqueue on copy failure
- ✅ Comprehensive test suite (16 tests, all passing)
- ✅ Race condition protection for voting
- ✅ Documentation updates (GAME_RULES.md, AI_SERVICE.md)

See [Implementation Checklist](#implementation-checklist) for detailed status.

## Overview

This document outlines the implementation plan for a new AI system that handles stale content - prompts waiting for copies and phrasesets waiting for votes that are more than X days old (configurable, minimum 3 days).

### Key Characteristics
- **Separate AI Players**: Uses `ai_stale_handler@quipflip.internal` for copies and `ai_stale_voter@quipflip.internal` for votes
- **No Human Requirement**: Can submit copies/votes even when only AI players have participated
- **Comprehensive Processing**: Handles ALL stale content in each cycle (no batch size limit)
- **Scheduled Execution**: Runs every 12 hours (configurable)
- **Complementary System**: Supplements the existing backup AI (which handles recent 60min+ content)

## Business Requirements

### Primary Goal
Ensure that no prompts or phrasesets are permanently abandoned by providing AI participation for content that has been stale for an extended period.

### Key Differences from Backup AI

| Feature | Backup AI | Stale AI |
|---------|-----------|----------|
| **Email** | `ai_copy_backup@quipflip.internal` | `ai_stale_handler@quipflip.internal` (copies)<br>`ai_stale_voter@quipflip.internal` (votes) |
| **Trigger Time** | 60 minutes (configurable) | 3+ days (configurable) |
| **Human Activity Required** | Yes - requires human vote before voting | No - can act independently |
| **Batch Size** | Limited to 2 items per cycle | Processes ALL stale content |
| **Frequency** | Every 2 hours | Every 12 hours |
| **Purpose** | Handle temporary gaps | Handle abandoned content |

## Technical Design

### 1. Configuration Changes

**File**: `backend/config.py`

Add the following settings to the `Settings` class (in the AI Service section):

```python
# Stale AI Handler (for content 3+ days old)
ai_stale_handler_enabled: bool = True  # Feature flag
ai_stale_threshold_days: int = 3  # Days before content is stale (minimum 3)
ai_stale_check_interval_hours: int = 12  # How often to check for stale content
```

**Validation Logic** (add to `validate_all_config` method):

```python
# Validate stale AI configuration
if self.ai_stale_threshold_days < 3:
    raise ValueError("ai_stale_threshold_days must be at least 3 days")

if self.ai_stale_check_interval_hours < 1:
    raise ValueError("ai_stale_check_interval_hours must be at least 1 hour")
```

### 2. New Service Implementation

**File**: `backend/services/ai/stale_ai_service.py`

Create a new service class that handles stale content processing.

#### Class Structure

```python
"""
Stale AI Service for handling abandoned content.

This service provides AI-generated copies and votes for content that has been
waiting for 3+ days (configurable), ensuring no prompts or phrasesets are
permanently abandoned.
"""

import logging
from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.config import get_settings
from backend.models.player import Player
from backend.models.round import Round
from backend.models.phraseset import Phraseset
from backend.models.vote import Vote
from backend.services.ai.ai_service import AIService

logger = logging.getLogger(__name__)

AI_STALE_HANDLER_EMAIL = "ai_stale_handler@quipflip.internal"


class StaleAIService:
    """
    Service for generating AI copies and votes for stale content.

    Handles content that has been waiting for 3+ days (configurable).
    Unlike the backup AI, this service can act even when only AI players
    have participated, ensuring no content is permanently abandoned.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.ai_service = AIService(db)  # Reuse generation methods

    async def run_stale_cycle(self) -> None:
        """
        Run a cycle to handle stale prompts and phrasesets.

        This method:
        1. Finds prompts waiting for copies that are 3+ days old
        2. Generates AI copies for ALL such prompts
        3. Finds phrasesets waiting for votes that are 3+ days old
        4. Generates AI votes for ALL such phrasesets
        5. Logs comprehensive statistics

        Note:
            Unlike backup AI, this processes ALL stale content in each cycle
            and can act even when only AI players have participated.
        """
        pass  # Implementation details below
```

#### Key Methods

**1. Get or Create Stale AI Player**

```python
async def _get_or_create_stale_handler(self) -> Player:
    """Get or create the dedicated stale handler AI player."""
    from backend.services.player_service import PlayerService

    # Check if player exists
    result = await self.db.execute(
        select(Player).where(Player.email == AI_STALE_HANDLER_EMAIL)
    )
    player = result.scalar_one_or_none()

    if player:
        return player

    # Create new stale handler player
    player_service = PlayerService(self.db)
    player = await player_service.create_player(
        email=AI_STALE_HANDLER_EMAIL,
        username="Stale AI Handler",
        password="not-used-for-ai",
        is_guest=False
    )

    await self.db.commit()
    logger.info(f"Created stale AI handler player: {player.player_id}")

    return player
```

**2. Find Stale Prompts**

```python
async def _find_stale_prompts(self, stale_handler_id: UUID) -> list[Round]:
    """
    Find prompts that have been waiting for copies for 3+ days.

    Criteria:
    - Status = 'submitted'
    - No phraseset created yet
    - Created 3+ days ago (configurable)
    - Not owned by stale AI itself
    - Not already copied by stale AI
    """
    cutoff_time = datetime.now(UTC) - timedelta(days=self.settings.ai_stale_threshold_days)

    result = await self.db.execute(
        select(Round)
        .where(Round.round_type == 'prompt')
        .where(Round.status == 'submitted')
        .where(Round.created_at <= cutoff_time)
        .where(Round.player_id != stale_handler_id)
        .outerjoin(Phraseset, Phraseset.prompt_round_id == Round.round_id)
        .where(Phraseset.phraseset_id.is_(None))  # No phraseset yet
        .order_by(Round.created_at.asc())  # Process oldest first
    )

    return list(result.scalars().all())
```

**3. Find Stale Phrasesets**

```python
async def _find_stale_phrasesets(self, stale_handler_id: UUID) -> list[Phraseset]:
    """
    Find phrasesets that have been waiting for votes for 3+ days.

    Criteria:
    - Status in ['open', 'closing']
    - Created 3+ days ago (configurable)
    - Not already voted on by stale AI
    - NO restriction on AI vs human contributors (key difference!)
    """
    cutoff_time = datetime.now(UTC) - timedelta(days=self.settings.ai_stale_threshold_days)

    # Subquery to find phrasesets already voted by this stale handler
    already_voted_subquery = (
        select(Vote.phraseset_id)
        .where(Vote.player_id == stale_handler_id)
    )

    result = await self.db.execute(
        select(Phraseset)
        .where(Phraseset.status.in_(["open", "closing"]))
        .where(Phraseset.created_at <= cutoff_time)
        .where(Phraseset.phraseset_id.not_in(already_voted_subquery))
        .options(
            selectinload(Phraseset.prompt_round),
            selectinload(Phraseset.copy_round_1),
            selectinload(Phraseset.copy_round_2),
        )
        .order_by(Phraseset.created_at.asc())  # Process oldest first
    )

    return list(result.scalars().all())
```

**4. Main Cycle Implementation**

```python
async def run_stale_cycle(self) -> None:
    """Run the stale content handling cycle."""

    stats = {
        "stale_prompts_found": 0,
        "stale_prompts_processed": 0,
        "stale_copies_generated": 0,
        "stale_phrasesets_found": 0,
        "stale_phrasesets_processed": 0,
        "stale_votes_generated": 0,
        "errors": 0,
    }

    try:
        # Get or create stale handler player
        stale_handler = await self._get_or_create_stale_handler()

        # Process stale prompts (waiting for copies)
        stale_prompts = await self._find_stale_prompts(stale_handler.player_id)
        stats["stale_prompts_found"] = len(stale_prompts)

        logger.info(f"Found {len(stale_prompts)} stale prompts to process")

        for prompt_round in stale_prompts:
            try:
                # Use AIService to generate copy (reuses all validation logic)
                copy_phrase = await self.ai_service.generate_copy_phrase(
                    prompt_round.submitted_phrase,
                    prompt_round
                )

                # Submit copy as stale handler
                # (Implementation similar to backup AI but with stale handler player)
                # ... copy submission logic ...

                stats["stale_copies_generated"] += 1
                stats["stale_prompts_processed"] += 1

            except Exception as e:
                logger.error(f"Failed to process stale prompt {prompt_round.round_id}: {e}")
                stats["errors"] += 1

        # Process stale phrasesets (waiting for votes)
        stale_phrasesets = await self._find_stale_phrasesets(stale_handler.player_id)
        stats["stale_phrasesets_found"] = len(stale_phrasesets)

        logger.info(f"Found {len(stale_phrasesets)} stale phrasesets to process")

        for phraseset in stale_phrasesets:
            try:
                # Use AIService to generate vote
                vote_choice = await self.ai_service.generate_vote_choice(phraseset)

                # Submit vote as stale handler
                # (Implementation similar to backup AI but with stale handler player)
                # ... vote submission logic ...

                stats["stale_votes_generated"] += 1
                stats["stale_phrasesets_processed"] += 1

            except Exception as e:
                logger.error(f"Failed to process stale phraseset {phraseset.phraseset_id}: {e}")
                stats["errors"] += 1

        await self.db.commit()

        logger.info(
            f"Stale AI cycle completed: "
            f"{stats['stale_prompts_processed']}/{stats['stale_prompts_found']} prompts, "
            f"{stats['stale_phrasesets_processed']}/{stats['stale_phrasesets_found']} phrasesets, "
            f"{stats['errors']} errors"
        )

    except Exception as e:
        logger.error(f"Stale AI cycle failed: {e}")
        await self.db.rollback()
        raise
```

### 3. Background Task

**File**: `backend/main.py`

Add a new background task that runs the stale AI cycle.

#### Implementation

```python
async def ai_stale_handler_cycle():
    """
    Background task to run stale AI handler cycles.

    Processes prompts and phrasesets that have been waiting for 3+ days.
    Unlike backup AI, this can act even when only AI players have participated.
    """
    from backend.database import AsyncSessionLocal
    from backend.services.ai.stale_ai_service import StaleAIService

    settings = get_settings()

    # Check if stale handler is enabled
    if not settings.ai_stale_handler_enabled:
        logger.info("Stale AI handler is disabled, not starting cycle")
        return

    # Verify phrase validator is ready (same as backup AI)
    try:
        if settings.use_phrase_validator_api:
            from backend.services.phrase_validation_client import get_phrase_validation_client
            client = get_phrase_validation_client()
            if not await client.health_check():
                logger.warning("Phrase validator API not healthy yet, stale AI may experience issues")
        else:
            from backend.services.phrase_validator import get_phrase_validator
            validator = get_phrase_validator()
            if not validator.dictionary:
                logger.warning("Local phrase validator dictionary not loaded, stale AI may experience issues")
    except Exception as e:
        logger.warning(f"Could not verify phrase validator health: {e}")

    # Initial startup delay
    startup_delay = 180
    logger.info(f"Stale AI handler cycle starting in {startup_delay}s")
    await asyncio.sleep(startup_delay)

    logger.info("Stale AI handler cycle starting main loop")

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await StaleAIService(db).run_stale_cycle()

        except Exception as e:
            logger.error(f"Stale AI handler cycle error: {e}")

        # Wait before next cycle (default: 12 hours)
        sleep_seconds = settings.ai_stale_check_interval_hours * 3600
        logger.info(f"Stale AI handler sleeping for {settings.ai_stale_check_interval_hours} hours")
        await asyncio.sleep(sleep_seconds)
```

#### Register Background Task

In the `lifespan` function, add the stale handler task:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # ... existing setup ...

    # Start background tasks
    ai_backup_task = asyncio.create_task(ai_backup_cycle())
    stale_handler_task = asyncio.create_task(ai_stale_handler_cycle())  # NEW
    cleanup_task = asyncio.create_task(cleanup_cycle())
    finalization_task = asyncio.create_task(finalization_cycle())

    # ... rest of lifespan ...
```

### 4. Admin Configuration Support

#### Update Admin Router

**File**: `backend/routers/admin.py`

Add new fields to the `GameConfigResponse` model:

```python
class GameConfigResponse(BaseModel):
    # ... existing fields ...

    # Stale AI Handler (NEW)
    ai_stale_handler_enabled: bool
    ai_stale_threshold_days: int
    ai_stale_check_interval_hours: int
```

Update the GET `/admin/config` endpoint to include stale AI settings:

```python
@router.get("/config", response_model=GameConfigResponse)
async def get_game_config(...):
    # ... existing code ...

    return GameConfigResponse(
        # ... existing fields ...

        # Stale AI Handler
        ai_stale_handler_enabled=config.get("ai_stale_handler_enabled", True),
        ai_stale_threshold_days=config.get("ai_stale_threshold_days", 3),
        ai_stale_check_interval_hours=config.get("ai_stale_check_interval_hours", 12),
    )
```

#### Update System Config Service

**File**: `backend/services/system_config_service.py`

Add stale AI settings to the configurable fields:

```python
# In CONFIGURABLE_FIELDS dictionary:
"ai_stale_handler_enabled": {
    "type": "bool",
    "description": "Enable stale AI handler for 3+ day old content",
},
"ai_stale_threshold_days": {
    "type": "int",
    "description": "Days before content is considered stale (minimum 3)",
    "min": 3,
},
"ai_stale_check_interval_hours": {
    "type": "int",
    "description": "Hours between stale AI handler cycles",
    "min": 1,
},
```

### 5. Metrics and Logging

#### Metrics Integration

Reuse the existing `AIMetricsService` but add new operation types:

- `operation_type = "stale_copy"` - Copy generated by stale handler
- `operation_type = "stale_vote"` - Vote generated by stale handler

In `StaleAIService`, track metrics similar to backup AI:

```python
# When generating a copy:
await self.ai_service.metrics_service.record_copy_attempt(
    prompt_round_id=prompt_round.round_id,
    ai_model=self.ai_service.ai_model,
    provider=self.ai_service.provider,
    success=True,
    generated_phrase=copy_phrase,
    error_message=None,
    operation_type="stale_copy"  # NEW
)

# When generating a vote:
await self.ai_service.metrics_service.record_vote_attempt(
    phraseset_id=phraseset.phraseset_id,
    ai_model=self.ai_service.ai_model,
    provider=self.ai_service.provider,
    success=True,
    selected_phrase=vote_choice,
    error_message=None,
    operation_type="stale_vote"  # NEW
)
```

#### Logging Strategy

Log at these key points:

1. **Cycle Start**: "Stale AI handler cycle starting main loop"
2. **Content Found**: "Found X stale prompts to process", "Found Y stale phrasesets to process"
3. **Individual Success**: Debug level for each successful copy/vote
4. **Individual Error**: Error level for each failed attempt
5. **Cycle Complete**: "Stale AI cycle completed: X/Y prompts, A/B phrasesets, C errors"
6. **Sleep**: "Stale AI handler sleeping for X hours"

### 6. Documentation Updates

#### Update Game Rules

**File**: `docs/GAME_RULES.md`

Add a new section under "AI Assistance and Automation":

```markdown
### Stale Content Handler

The stale AI handler (`ai_stale_handler@quipflip.internal`) provides a safety net for content that has been waiting for an extended period:

- **Activation Threshold**: Content must be at least `ai_stale_threshold_days` old (default: 3 days)
- **Scope**: Handles both prompts waiting for copies AND phrasesets waiting for votes
- **Independence**: Unlike the backup AI, the stale handler can act even when only AI players have participated
- **Processing**: Handles ALL stale content in each cycle (no batch size limit)
- **Frequency**: Runs every `ai_stale_check_interval_hours` (default: 12 hours)

The stale handler ensures that no content is permanently abandoned while allowing ample time for human participation. It complements the backup AI system, which handles more recent content (60+ minutes old) but requires human activity.
```

Update the configuration reference section:

```markdown
## Configuration Reference by Purpose

- **AI providers**: `ai_provider`, `ai_openai_model`, `ai_gemini_model`, `openai_api_key`, `gemini_api_key`, `ai_timeout_seconds`, `ai_backup_delay_minutes`, `ai_backup_batch_size`, `ai_backup_sleep_minutes`, `ai_stale_handler_enabled`, `ai_stale_threshold_days`, `ai_stale_check_interval_hours` (environment-driven).
```

## Implementation Checklist

### Phase 1: Core Implementation ✅ COMPLETE
- [x] Add configuration settings to `backend/config.py` with validation
- [x] Create `backend/services/ai/stale_ai_service.py` with all methods
- [x] Add background task to `backend/main.py`
- [x] Update admin router with new config fields
- [x] Update system config service with new settings

### Phase 2: Integration ✅ COMPLETE
- [x] Add metrics tracking for stale operations (using `record_operation`)
- [x] Implement comprehensive logging
- [x] Update `docs/GAME_RULES.md` with stale AI documentation
- [x] Update `docs/AI_SERVICE.md` with stale AI documentation
- [x] Add inline code comments and docstrings

### Phase 3: Testing ✅ COMPLETE
- [x] Test query logic finds correct stale content (8 tests)
- [x] Verify stale AI can act without human participants (player creation tests)
- [x] Test deduplication (no double-processing) - covered in `test_exclude_*` tests
- [x] Validate configuration constraints (validation in config.py)
- [x] Test background task lifecycle (integration tests)
- [x] Test error handling and recovery (metrics + queue re-enqueue tests)
- [x] Test race condition protection (copy slot checking, phraseset status refresh)
- [x] **Total: 16 tests, all passing** (`tests/test_stale_ai_service.py`)

### Phase 4: Deployment 🔄 READY
- [x] Environment variables defined in config.py
- [x] Admin panel backend updated (GET /admin/config includes stale AI settings)
- [ ] Admin panel frontend UI update (optional - can configure via database)
- [x] Logging implemented ("Stale AI cycle completed" messages)
- [x] Metrics recording verified (operation_type="stale_copy" and "stale_vote")
- [ ] Deploy to production and monitor first cycles

### Production Readiness ✅
All critical items complete:
- [x] Core infrastructure
- [x] Metrics tracking
- [x] Queue re-enqueue on failure
- [x] Race condition protection
- [x] Comprehensive tests
- [x] Documentation

## Testing Scenarios

### 1. Stale Prompt Processing
```python
# Create a prompt 4 days ago
# Ensure no copies exist
# Run stale cycle
# Verify AI copy is submitted
# Verify metrics are recorded
```

### 2. Stale Phraseset Processing
```python
# Create a phraseset 4 days ago with only AI contributors
# Run stale cycle
# Verify stale AI can vote (no human requirement)
# Verify metrics are recorded
```

### 3. Deduplication
```python
# Create stale content
# Run stale cycle once
# Run stale cycle again
# Verify content is not processed twice
```

### 4. Configuration Validation
```python
# Test ai_stale_threshold_days < 3 raises error
# Test ai_stale_check_interval_hours < 1 raises error
# Test valid configurations work
```

### 5. Complementary Operation
```python
# Create content 30 minutes old
# Run backup AI cycle - should process
# Run stale AI cycle - should NOT process (not old enough)
#
# Create content 4 days old
# Run backup AI cycle - should NOT process (too old/different purpose)
# Run stale AI cycle - should process
```

## Environment Variables

For production deployment, add:

```bash
AI_STALE_HANDLER_ENABLED=true
AI_STALE_THRESHOLD_DAYS=3
AI_STALE_CHECK_INTERVAL_HOURS=12
```

## Monitoring and Alerts

Monitor these metrics:

1. **Stale Content Volume**: How many prompts/phrasesets become stale per cycle?
2. **Success Rate**: Percentage of stale content successfully processed
3. **Error Rate**: Failures during stale processing
4. **Cycle Duration**: How long does each cycle take?

Set alerts for:
- Error rate > 10%
- Stale content volume increasing over time (may indicate human participation dropping)
- Cycle failures

## Future Enhancements

Potential improvements for future iterations:

1. **Configurable Batch Sizes**: Add option to limit processing per cycle if performance is a concern
2. **Priority Scoring**: Process older content first, or content with more activity
3. **Notification System**: Alert moderators when stale content volume is high
4. **Gradual Activation**: Start with higher threshold (e.g., 7 days) and adjust based on activity patterns
5. **Analytics Dashboard**: Visualize stale content trends over time

## Questions and Decisions

### Q: Why 3 days minimum?
**A**: Provides ample time for human participation while ensuring content isn't abandoned indefinitely. Can be configured higher if needed.

### Q: Why no batch size limit?
**A**: Stale content represents a backlog that should be cleared. Running infrequently (12 hours) means processing all stale content won't overload the system.

### Q: Why separate from backup AI?
**A**: Backup AI handles recent gaps in activity (temporary), while stale AI handles abandoned content (permanent). Different purposes require different logic and constraints.

### Q: Should stale AI count toward rate limits?
**A**: No - stale AI player should be exempt from rate limiting like other AI players (check rate limiting middleware).

### Q: Can stale AI copy/vote on its own previous work?
**A**: Copies: No (filtered by player_id). Votes: Yes, potentially (if the phraseset is stale and the stale AI hasn't voted on it yet). This is acceptable since it provides value.

## Related Documentation

- [AI Service Guide](AI_SERVICE.md) - Details on existing backup AI system
- [Game Rules](GAME_RULES.md) - Complete game mechanics and rules
- [Architecture](ARCHITECTURE.md) - Overall system architecture

## Contact and Support

For questions about this implementation:
- Review existing `AIService` implementation in `backend/services/ai/ai_service.py`
- Check background task patterns in `backend/main.py`
- Refer to configuration patterns in `backend/config.py`
