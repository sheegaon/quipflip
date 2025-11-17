# Quipflip AI Service

## Overview

The AI service fills in for missing players by generating backup copy phrases and casting votes when human activity is low. It supports both OpenAI and Google Gemini models, records detailed telemetry for every AI operation, and integrates with the existing queue, phrase validation, and round management services so that AI decisions follow the same rules as real players.

## Module Layout

```
backend/services/ai/
├── ai_service.py       # High level coordinator for copy generation, voting, and backup cycles
├── stale_ai_service.py # Stale content handler for 3+ day old prompts/phrasesets
├── gemini_api.py       # Lightweight wrapper around the Google Gemini SDK
├── metrics_service.py  # Telemetry helpers (AIMetricsService + MetricsTracker)
├── openai_api.py       # Lightweight wrapper around the OpenAI SDK
├── prompt_builder.py   # Shared prompt templates for copy and vote prompts
└── vote_helper.py      # Provider-specific vote selection helpers
```

Related models and helpers live in other packages:

```
backend/models/ai_metric.py   # ORM model persisted by AIMetricsService
backend/models/ai_phrase_cache.py  # ORM model storing pre-validated phrases for reuse
backend/services/queue_service.py  # Used to claim work during backup cycles
backend/services/round_service.py  # Used to build phrasesets when AI copies arrive
backend/services/vote_service.py   # Used to submit AI votes with full transaction handling
backend/services/phrase_validator.py (or phrase_validation_client.py)  # Validation rules reused by AI copies
```

## Key Capabilities

### Provider selection

* `AIService` inspects `Settings.ai_provider` and the configured API keys.
* The requested provider is used when its API key is present.
* If the requested provider is unavailable the code falls back to the other provider when possible.
* If no provider is configured an `AIServiceError` is raised.

### Copy generation

* `AIService.generate_copy_phrase(original_phrase, prompt_round)` retrieves a validated phrase from the phrase cache, creating the cache if it doesn't exist.
* The underlying `generate_and_cache_phrases()` method generates 5 phrases via `prompt_builder.build_copy_prompt`, validates all of them, and stores 3-5 valid phrases in the `ai_phrase_cache` table.
* Phrases are validated with the same validator used for human submissions (local validator or remote Phrase Validation API depending on configuration).
* `generate_copy_phrase()` randomly selects one phrase from the cache and removes it from the list, ensuring different phrases for multiple AI backup copies.
* If the cache is depleted (all phrases consumed), it is automatically regenerated.
* Cache generation is wrapped in `MetricsTracker`, capturing latency, provider, model, success, and validation outcomes in `ai_metrics` with a reference to the `cache_id`.

### Vote generation

* `AIService.generate_vote_choice(phraseset)` assembles the original phrase and two copies, shuffles them, and calls `vote_helper.generate_vote_choice`.
* `vote_helper` contains provider-specific implementations for OpenAI and Gemini. They both rely on `prompt_builder.build_vote_prompt` to produce the voting instructions.
* The tracker logs whether the AI selected the original phrase so that accuracy can be measured later.

### Hint generation

* `AIService.get_hints_from_cache(prompt_round, count=3)` provides AI-powered copy phrase suggestions by reusing the phrase cache created during copy generation.
* Hints are drawn from the same validated phrase set used for AI backup copies, ensuring consistency and eliminating redundant AI API calls.
* The phrase cache (`ai_phrase_cache` table) stores 3-5 validated phrases per `prompt_round_id`, generated once and reused for both backup copies and hints.
* Unlike backup copies which consume phrases (removed from cache after use), hints do not consume phrases—all players requesting hints get the same set.
* When no cache exists, `get_hints_from_cache()` calls `generate_and_cache_phrases()` which generates and validates 5 phrases, keeping 3-5 valid ones.
* Hints are tracked with `operation_type="copy_generation"` in metrics (when cache is created), linking to the cache via `cache_id`.
* The hint cost is configurable via `Settings.hint_cost` (default: 10 Flipcoins).
* **Deprecated:** `generate_copy_hints()` is maintained for backward compatibility but delegates to `get_hints_from_cache()`.

### Backup cycle automation

* `AIService.run_backup_cycle()` creates or retrieves a dedicated AI player, then:
  1. Finds prompt rounds that have been waiting longer than `Settings.ai_backup_delay_minutes` and are still missing copies.
  2. Skips prompts the AI recently attempted (based on previous metrics entries).
  3. Generates copies, submits them as the AI player, and lets `RoundService` finalize phrasesets when both copies are present.
  4. Finds phrasesets that have been idle past the same delay but already have at least one human vote.
  5. Generates AI votes using `VoteService.submit_system_vote`, crediting payouts and recording metrics like any other vote.
* The method commits all successful work in one transaction and rolls back on failure. Statistics are logged for observability.

### Metrics and analytics

* `AIMetricsService.record_operation` stores a row in `ai_metrics` with provider, model, latency, validation or vote correctness, and an estimated cost based on prompt/response lengths.
* `AIMetricsService.get_stats` returns aggregate counts, success rates, cost totals, average latency, and breakdowns per provider/type for a time window (default: 24 hours).
* `AIMetricsService.get_vote_accuracy` reports how often AI votes matched the original phrase.
* `MetricsTracker` is an async context manager that simplifies latency measurement and automatic failure logging.

## Configuration

The AI service reads its configuration from `backend.config.Settings` (environment variables of the same name override defaults):

| Setting | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | Enables OpenAI copy/vote generation | unset |
| `GEMINI_API_KEY` | Enables Gemini copy/vote generation | unset |
| `AI_PROVIDER` | Preferred provider (`"openai"`, `"gemini"`, or `"none"`) | `openai` |
| `AI_OPENAI_MODEL` | OpenAI model name passed to the API | `gpt-5-nano` |
| `AI_GEMINI_MODEL` | Gemini model name passed to the API | `gemini-2.5-flash-lite` |
| `AI_TIMEOUT_SECONDS` | Request timeout for provider calls | `60` |
| `AI_BACKUP_DELAY_MINUTES` | Age threshold before AI copies/votes run | `15` |
| `AI_BACKUP_BATCH_SIZE` | Max prompts/phrasesets processed per cycle | `3` |
| `AI_BACKUP_SLEEP_MINUTES` | Recommended sleep between scheduled cycles | `60` |
| `HINT_COST` | Cost in Flipcoins to generate new AI hints | `10` |

When `Settings.use_phrase_validator_api` is `True`, the service uses the remote validator via `phrase_validation_client`; otherwise it falls back to the local validator.

## API Reference

### Creating an `AIService`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services import AIService

ai_service = AIService(db_session)  # db_session: AsyncSession
```

`AIService` pulls configuration during construction and lazily loads the phrase validator.

### `generate_copy_phrase`

```python
copy = await ai_service.generate_copy_phrase(
    original_phrase="HAPPY BIRTHDAY",
    prompt_round=prompt_round,  # backend.models.qf.round.Round instance
)
```

* Returns an uppercase phrase ready to store on a copy round.
* Raises `AICopyError` when generation fails or validation rejects the result.
* Metrics are queued on the current SQLAlchemy session; the caller is responsible for committing.

### `generate_vote_choice`

```python
choice = await ai_service.generate_vote_choice(phraseset)  # returns the chosen phrase string
```

* Accepts a fully populated `backend.models.qf.phraseset.Phraseset` (prompt text and phrase fields are used).
* Returns the phrase text selected by the AI.
* Raises `AIVoteError` if the provider cannot return a valid choice.

### `run_backup_cycle`

```python
await ai_service.run_backup_cycle()
```

* Orchestrates both copy and vote catch-up tasks as described above.
* Does not return a value; success and error counts are logged.
* Commits at the end of a successful cycle. On failure it rolls back and logs the error.

### Metrics helpers

```python
from backend.services import AIMetricsService, MetricsTracker

metrics = AIMetricsService(db_session)
stats = await metrics.get_stats()
accuracy = await metrics.get_vote_accuracy()

async with MetricsTracker(metrics,
                          operation_type="copy_generation",
                          provider="openai",
                          model="gpt-5-nano") as tracker:
    # ... call provider ...
    tracker.set_result(result_text,
                       success=True,
                       response_length=len(result_text),
                       validation_passed=True)
```

## Data Model

### AIPhraseCache Table

`backend/models/ai_phrase_cache.py` defines the `ai_phrase_cache` table for storing pre-validated copy phrases:

* Primary key `cache_id` uses UUIDs generated by `uuid.uuid4`.
* `prompt_round_id` is a unique foreign key to `rounds.round_id` (cascade delete) - one cache per prompt round.
* `original_phrase` and `prompt_text` are denormalized from the prompt round for context.
* `validated_phrases` is a JSON array containing 3-5 validated copy phrase strings.
* `generation_provider` and `generation_model` capture which AI backend generated the phrases (e.g., `"openai"` / `"gpt-5-nano"`).
* `used_for_backup_copy` boolean flag indicates if the cache has been used for AI backup copies.
* `used_for_hints` boolean flag indicates if the cache has been used for player hints.
* `created_at` timestamp for tracking cache age.

The cache eliminates redundant AI API calls by generating phrases once and reusing them for both backup copies and hints. Backup copies consume phrases (removed from the array), while hints do not consume phrases (all players get the same hints).

### AIMetric Table

`backend/models/ai_metric.py` defines the `ai_metrics` table with the following notable columns and behaviour:

* Primary key `metric_id` uses UUIDs generated by `uuid.uuid4`.
* `operation_type` distinguishes copy and vote flows (`"copy_generation"` or `"vote_generation"`).
* `provider` and `model` capture the configured backend (for example `"openai"` / `"gpt-5-nano"`).
* `success`, `latency_ms`, and `error_message` describe the outcome of the provider call. Latency is stored in milliseconds and can be `NULL` on hard failures where no timing is captured.
* `estimated_cost_usd` is a nullable float populated when the provider cost helper can estimate token usage.
* `prompt_length` and `response_length` store character lengths for prompts and responses when available. These fields are optional so that the service can log operations even if a provider omits size metadata.
* `validation_passed` is set for copy-generation attempts. It is `NULL` on vote operations.
* `vote_correct` is set for vote-generation attempts and is `NULL` for copy operations.
* `cache_id` is a nullable foreign key to `ai_phrase_cache.cache_id` (set null on delete) linking metrics to the phrase cache used/generated.
* `created_at` defaults to `datetime.now(UTC)` and is indexed for efficient time-window analytics.

Additional composite indexes support common dashboards and alerts:

* `ix_ai_metrics_created_at_success` accelerates time-bounded success-rate checks.
* `ix_ai_metrics_operation_provider` groups operations by type and provider for breakdowns.
* `ix_ai_metrics_op_created` is used by the metrics service to retrieve the most recent operations of each type.
* `ix_ai_metrics_cache_id` enables efficient queries linking metrics to phrase caches.

## External Dependencies

* `openai` – optional dependency used when OpenAI is the provider.
* `google-genai` – optional dependency used when Gemini is the provider.
* The phrase validation service (remote API or local validator) must be available so that AI copies follow the same rules as player submissions.

## Testing

Automated coverage lives in `tests/test_ai_service.py` and focuses on the following scenarios:

* Provider selection fallbacks (`AIService` initialization) across all combinations of configured API keys.
* Copy generation success paths, validation failures, and provider exceptions. External SDK calls are mocked so no real OpenAI or Gemini requests are issued.
* Vote generation, including correctness tracking, shuffled phrase ordering, and error-handling around `vote_helper` responses.
* Metrics recording for copy and vote operations, plus aggregation via `AIMetricsService.get_stats` and `get_vote_accuracy`.
* AI player management helpers that create the backup player when missing and reuse the persisted record when present.
* Backup cycle behaviour that filters phrasesets, requires existing human votes before adding AI votes, and submits system votes via the vote service.

Current gaps include:

* No coverage for running `run_backup_cycle` end-to-end with real provider integrations or phrase validation API calls.
* No assertions around the token-cost estimation logic beyond verifying that `estimated_cost_usd` is populated when supplied.
* Gemini-specific voting pathways rely on shared mocks and are not exercised with provider-specific prompts.

Run the suite with:

```bash
pytest tests/test_ai_service.py -v
```

## Stale Content Handler

The stale AI handler (`StaleAIService`) provides a complementary safety net for content that has been waiting for 3+ days. Unlike the backup AI which handles recent stalled content, the stale handler ensures nothing is permanently abandoned.

### Key Differences from Backup AI

| Feature | Backup AI | Stale AI |
|---------|-----------|----------|
| **Email** | `ai_copy_backup@quipflip.internal` | `ai_stale_handler@quipflip.internal` (copies)<br>`ai_stale_voter@quipflip.internal` (votes) |
| **Trigger Time** | `ai_backup_delay_minutes` (default: 60 min) | `ai_stale_threshold_days` (default: 3 days) |
| **Human Activity Required** | Yes - requires human vote before voting | No - can act independently |
| **Batch Size** | Limited to `ai_backup_batch_size` (default: 2) | Processes ALL stale content |
| **Frequency** | Every `ai_backup_sleep_minutes` (default: 120 min) | Every `ai_stale_check_interval_hours` (default: 12 hours) |
| **Purpose** | Handle temporary gaps in activity | Handle permanently abandoned content |
| **Operation Types** | `"backup_copy"`, `"backup_vote"` | `"stale_copy"`, `"stale_vote"` |

### Architecture

```
backend/services/ai/
├── stale_ai_service.py    # StaleAIService - handles abandoned content
└── ai_service.py           # AIService - reused for generation logic
```

### Key Methods

* **`StaleAIService.run_stale_cycle()`** - Main entry point, processes all stale prompts and phrasesets
* **`_find_stale_prompts()`** - Queries for prompts older than threshold without phrasesets (single query, no N+1)
* **`_find_stale_phrasesets()`** - Queries for phrasesets older than threshold still accepting votes
* **`_get_or_create_stale_handler()`** - Manages `ai_stale_handler@quipflip.internal` player for copies
* **`_get_or_create_stale_voter()`** - Manages `ai_stale_voter@quipflip.internal` player for votes

### Workflow

1. **Startup**: Background task starts after 240s delay
2. **Query Phase**: Find all prompts/phrasesets older than `ai_stale_threshold_days`
3. **Copy Phase**:
   - For each stale prompt, generate copy using `AIService.generate_copy_phrase`
   - Race condition protection: check slot availability before AND after generation
   - Record metrics with `operation_type="stale_copy"`
   - On failure: re-enqueue prompt and record error metrics
4. **Vote Phase**:
   - For each stale phraseset, generate vote using `AIService.generate_vote_choice`
   - Race condition protection: refresh phraseset status before voting
   - Record metrics with `operation_type="stale_vote"`
   - On failure: record error metrics (no re-enqueue for votes)
5. **Sleep**: Wait `ai_stale_check_interval_hours` before next cycle

### Error Recovery

* **Failed Copy Generation**: Prompt is re-enqueued via `QueueService.add_prompt_round_to_queue()` for retry
* **Race Conditions**: Double-check pattern prevents conflicts when slots fill during generation
* **Closed Phrasesets**: Status check before voting prevents voting on finalized sets
* **Metrics Failures**: Wrapped in try/except to prevent blocking the cycle

### Configuration

```python
# In backend/config.py
ai_stale_handler_enabled: bool = True  # Feature flag
ai_stale_threshold_days: int = 2  # Minimum 1 day
ai_stale_check_interval_hours: int = 6  # Check frequency
```

### Testing

Comprehensive test coverage in `tests/test_stale_ai_service.py`:

* Player creation and management (handler vs voter separation)
* Query logic validation (age filtering, deduplication, N+1 prevention)
* Race condition handling for both copies and votes
* Metrics recording for success and failure cases
* Full cycle integration tests

Run tests with:

```bash
pytest tests/test_stale_ai_service.py -v
```

## Troubleshooting tips

* Verify that at least one API key is configured; missing keys raise `AIServiceError` during initialization.
* When `MetricsTracker` records repeated failures, inspect `ai_metrics.error_message` for provider error details.
* Queue contention can prevent the AI from claiming prompts. Check `QueueService.remove_prompt_round_from_queue` logs if copies are skipped.
* For stale AI issues, check logs for "Stale AI cycle completed" messages and compare processed vs found counts.
* Monitor `ai_metrics` table filtered by `operation_type IN ('stale_copy', 'stale_vote')` for stale AI performance.
