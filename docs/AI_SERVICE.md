# Crowdcraft AI Service

## Overview

The AI service fills in for missing players by generating backup copy phrases and casting votes when human activity is low. It supports both OpenAI and Google Gemini models, records detailed telemetry for every AI operation, and integrates with the existing queue, phrase validation, and round management services so that AI decisions follow the same rules as real players. The same service also powers Initial Reaction (IR) by generating backronym entries and votes when IR sets stall.

## Module Layout

```
backend/services/ai/
├── ai_service.py       # High level coordinator for copy generation, voting, and backup cycles
├── stale_ai_service.py # Stale content handler for 3+ day old prompts/phrasesets
├── qf_backup_orchestrator.py # QuipFlip-specific backup cycle orchestration
├── ir_backup_orchestrator.py # Initial Reaction-specific backup cycle orchestration
├── gemini_api.py       # Lightweight wrapper around the Google Gemini SDK
├── metrics_service.py  # Telemetry helpers (AIMetricsService + MetricsTracker)
├── openai_api.py       # Lightweight wrapper around the OpenAI SDK
├── prompt_builder.py   # Shared prompt templates for copy and vote prompts
└── vote_helper.py      # Provider-specific vote selection helpers
```

Related models and helpers live in other packages:

```
backend/models/qf/ai_metric.py   # ORM model persisted by AIMetricsService
backend/models/qf/ai_phrase_cache.py  # ORM model storing pre-validated phrases for reuse
backend/models/qf/ai_quip_cache.py    # ORM models storing validated quip responses and usage logs
backend/services/queue_service.py  # Used to claim work during backup cycles
backend/services/round_service.py  # Used to build phrasesets when AI copies arrive
backend/services/vote_service.py   # Used to submit AI votes with full transaction handling
backend/services/phrase_validator.py (or phrase_validation_client.py)  # Validation rules reused by AI copies
backend/services/ir/backronym_set_service.py  # IR set management for backronym generation/voting
backend/services/ir/player_service.py  # IR AI player management
```

## Key Capabilities

### Provider selection

* `AIService` inspects `Settings.ai_provider` and the configured API keys.
* The requested provider is used when its API key is present.
* If the requested provider is unavailable the code falls back to the other provider when possible.
* If no provider is configured an `AIServiceError` is raised.

### Copy generation (Impostor phrases)

* `AIService.get_impostor_phrase(prompt_round)` retrieves a validated phrase from the phrase cache, creating the cache if it doesn't exist.
* The underlying `generate_and_cache_impostor_phrases()` method generates 5 phrases via `prompt_builder.build_impostor_prompt`, validates all of them, and stores 3-5 valid phrases in the `ai_phrase_cache` table.
* Phrases are validated with the same validator used for human submissions (local validator or remote Phrase Validation API depending on configuration).
* `get_impostor_phrase()` randomly selects one phrase from the cache and removes it from the list, ensuring different phrases for multiple AI backup copies.
* If the cache is depleted (all phrases consumed), it is automatically regenerated.
* Cache generation is wrapped in `MetricsTracker`, capturing latency, provider, model, success, and validation outcomes in `ai_metrics` with a reference to the `cache_id`.

### Quip generation (prompt responses)

* `AIService.generate_quip_response(prompt_text, prompt_round_id)` reuses a cached pool of validated quip responses before calling the provider.
* The cache lives in `qf_ai_quip_cache` and stores one row per prompt text plus the provider/model used to validate it.
* Individual quips are stored in `qf_ai_quip_phrase`; when one is returned, a usage row is added to `qf_ai_quip_phrase_usage` linking the quip phrase to the consuming quip round ID.
* Selection prioritizes quips that have never been used, but allows reuse by ordering by usage count and creation time.
* Cache generation validates every provider response with the prompt validator to ensure quips meet the same rules as human submissions.

### Vote generation

* `AIService.generate_vote_choice(phraseset, seed)` assembles the original phrase and two copies, shuffles them, and calls `vote_helper.generate_vote_choice`.
* `vote_helper` contains provider-specific implementations for OpenAI and Gemini. They both rely on `prompt_builder.build_vote_prompt` to produce the voting instructions.
* The tracker logs whether the AI selected the original phrase so that accuracy can be measured later.

### Hint generation

* `AIService.get_hints(prompt_round, count=3)` provides AI-powered copy phrase suggestions by reusing the phrase cache created during copy generation.
* Hints are drawn from the same validated phrase set used for AI backup copies, ensuring consistency and eliminating redundant AI API calls.
* The phrase cache (`ai_phrase_cache` table) stores 3-5 validated phrases per `prompt_round_id`, generated once and reused for both backup copies and hints.
* Unlike backup copies which consume phrases (removed from cache after use), hints do not consume phrases—all players requesting hints get the same set.
* When no cache exists, `get_hints()` calls `generate_and_cache_impostor_phrases()` which generates and validates 5 phrases, keeping 3-5 valid ones.
* Hints are tracked with `operation_type="copy_generation"` in metrics (when cache is created), linking to the cache via `cache_id`.
* The hint cost is configurable via `Settings.hint_cost` (default: 10 Flipcoins).

### Backup cycle automation

* `AIService.run_backup_cycle()` delegates to `QFBackupOrchestrator` for QuipFlip-specific backup logic or `IRBackupOrchestrator` for Initial Reaction backup logic.
* The orchestrators create or retrieve dedicated AI players, then:
  1. Find prompt rounds that have been waiting longer than `Settings.ai_backup_delay_minutes` and are still missing copies.
  2. Generate AI copies using the phrase cache system.
  3. Find phrasesets that have been waiting for votes and have at least one human vote.
  4. Generate AI votes using `VoteService.submit_system_vote`, crediting payouts and recording metrics like any other vote.
* The methods commit all successful work in one transaction and roll back on failure. Statistics are logged for observability and batch sizes are capped by `Settings.ai_backup_batch_size`.

### Metrics and analytics

* `AIMetricsService.record_operation` stores a row in `ai_metrics` with provider, model, latency, validation or vote correctness, and an estimated cost based on prompt/response lengths.
* `AIMetricsService.get_stats` returns aggregate counts, success rates, cost totals, average latency, and breakdowns per provider/type for a time window (default: 24 hours). Operation types include `copy_generation`, `vote_generation`, `hint_generation`, and stale/IR variants where applicable.
* `AIMetricsService.get_vote_accuracy` reports how often AI votes matched the original phrase.
* `MetricsTracker` is an async context manager that simplifies latency measurement and automatic failure logging.

### Initial Reaction (IR) support

* `AIService.generate_backronym(word)` creates a list of uppercased words for each letter in the target word, sanitizing punctuation and invalid entries.
* `AIService.generate_backronym_vote(word, backronyms)` ranks backronym submissions and returns the selected index.
* `AIService.run_ir_backup_cycle()` delegates to `IRBackupOrchestrator` which fills stalled IR sets by generating backronym entries until each set has five entries and then casting votes until five votes exist, using the IR-specific AI player.

### AI Players vs. Guest Players

It is important to distinguish between two types of non-registered player accounts in the system: AI players and guest players.

*   **AI Players**: These are system-controlled accounts created and managed by the `AIService` via the `get_or_create_ai_player` method. Their purpose is to fill in for missing human activity, such as generating backup copy phrases or casting votes in stalled games. They are not intended for human use and have distinct roles and behaviors defined within the AI service.

*   **Guest Players**: These are temporary accounts for human users who want to play the game without completing a full registration. They are created through the standard player registration flow (e.g., via `/api/v1/players/guest`) and are marked with an `is_guest` flag in the database. Guest players have limitations, such as stricter rate limits and restrictions on certain game features. They can be upgraded to full accounts.

These two player types are technically separate and managed by different parts of the application. The AI service exclusively uses its own pool of AI players and does not interact with guest player accounts.

## Configuration

The AI service reads its configuration from `backend.config.Settings` (environment variables of the same name override defaults):

| Setting | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | Enables OpenAI copy/vote generation | unset |
| `GEMINI_API_KEY` | Enables Gemini copy/vote generation | unset |
| `AI_PROVIDER` | Preferred provider (`"openai"`, `"gemini"`, or `"none"`) | `openai` |
| `AI_OPENAI_MODEL` | OpenAI model name passed to the API | `gpt-5-nano` |
| `AI_GEMINI_MODEL` | Gemini model name passed to the API | `gemini-2.5-flash-lite` |
| `AI_TIMEOUT_SECONDS` | Request timeout for provider calls | `90` |
| `AI_BACKUP_DELAY_MINUTES` | Age threshold before AI copies/votes run | `30` |
| `AI_BACKUP_BATCH_SIZE` | Max prompts/phrasesets processed per cycle | `10` |
| `AI_BACKUP_SLEEP_MINUTES` | Recommended sleep between scheduled cycles | `30` |
| `HINT_COST` | Cost in Flipcoins to generate new AI hints | `10` |
| `IR_AI_BACKUP_DELAY_MINUTES` | Idle time before IR backronym sets receive AI help | `2` |
| `AI_STALE_THRESHOLD_DAYS` | Age threshold for stale content handler | `2` |
| `AI_STALE_CHECK_INTERVAL_HOURS` | Frequency of stale content checks | `6` |
| `AI_STALE_HANDLER_ENABLED` | Feature flag for stale handler | `True` |

When `Settings.use_phrase_validator_api` is `True`, the service uses the remote validator via `phrase_validation_client`; otherwise it falls back to the local validator.

## API Reference

### Creating an `AIService`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from backend.services.ai import AIService

ai_service = AIService(db_session)  # db_session: AsyncSession
```

`AIService` pulls configuration during construction and lazily loads the phrase validator.

### Core Methods

#### `get_or_create_ai_player`

```python
ai_player = await ai_service.get_or_create_ai_player(
    ai_player_type=AIPlayerType.QF_IMPOSTOR,  # AIPlayerType enum value
    excluded=[player_id1, player_id2]  # Optional list of player IDs to exclude
)
```

* Creates or retrieves an AI player account for the specified game type and role.
* Supports QF (QuipFlip) and IR (Initial Reaction) game types with different player roles.
* Returns a `PlayerBase` instance (QFPlayer or IRPlayer depending on type).
* Excludes specified player IDs to ensure different AI players for multiple operations.
* Validates AI player state (e.g., sufficient wallet funds for QF players).
* Raises `AIServiceError` if AI player cannot be created or is in invalid state.

#### `get_impostor_phrase`

```python
copy = await ai_service.get_impostor_phrase(
    prompt_round=prompt_round,  # backend.models.qf.round.Round instance
)
```

* Returns an uppercase phrase ready to store on a copy round.
* Uses cached validated phrases from `generate_and_cache_impostor_phrases()`.
* Selects a random phrase from the cache and removes it from the list.
* Automatically regenerates cache if depleted.
* Raises `AICopyError` when generation fails or validation rejects the result.
* Metrics are queued on the current SQLAlchemy session; the caller is responsible for committing.

#### `generate_quip_response`

```python
quip = await ai_service.generate_quip_response(
    prompt_text="Complete this thought:",  # The prompt to respond to
    prompt_round_id=prompt_round_id,  # UUID of the quip round consuming the cached phrase
)
```

* Generates or reuses a creative quip for a quip round, with caching.
* Uses `qf_ai_quip_cache` to store validated responses per prompt text.
* Prioritizes unused phrases but allows reuse when necessary.
* Validates responses with the same prompt validator used for human submissions.
* Records usage in `qf_ai_quip_phrase_usage` for tracking.
* Returns the selected phrase text.
* Raises `AICopyError` if generation fails.

#### `generate_and_cache_impostor_phrases`

```python
cache = await ai_service.generate_and_cache_impostor_phrases(
    prompt_round=prompt_round  # Round object with original phrase and context
)
```

* Generates and caches multiple validated copy phrases for a prompt round.
* Attempts to use pre-validated phrases from CSV cache first before calling AI API.
* Generates 5 phrases and keeps 3-5 valid ones after validation.
* Uses distributed locking to prevent duplicate cache generation.
* Stores results in `QFAIPhraseCache` table with provider and model metadata.
* Returns the created cache object.
* Raises `AICopyError` if insufficient valid phrases are generated.

#### `revalidate_cached_phrases`

```python
cache = await ai_service.revalidate_cached_phrases(
    prompt_round=prompt_round  # Round object to revalidate cache for
)
```

* Re-runs phrase validation on cached phrases and refreshes the cache if needed.
* Used when validation rules change (e.g., after first copy submission).
* Removes invalid phrases from cache and regenerates if below threshold.
* Uses distributed locking to prevent race conditions.
* Returns updated cache or None if lock acquisition fails.

#### `get_hints`

```python
hints = await ai_service.get_hints(
    prompt_round=prompt_round,  # Round containing original phrase and context
    count=3  # Number of hints to return (default: 3)
)
```

* Gets hint phrases from the phrase cache, or generates and caches if not present.
* Reuses the same cache created by `generate_and_cache_impostor_phrases()`.
* Hints do not consume phrases (all players get the same hints).
* Marks cache as `used_for_hints = True` for tracking.
* Returns list of validated hint phrases ready for display.
* Raises `AICopyError` if hints cannot be generated or cache is unavailable.

#### `generate_vote_choice`

```python
choice = await ai_service.generate_vote_choice(
    phraseset=phraseset,  # Fully populated Phraseset with prompt and phrases
    seed=42  # Random seed for reproducibility
)
```

* Generates a vote choice using the configured AI provider with metrics tracking.
* Shuffles the 3 phrases (original + 2 copies) before presenting to AI.
* Uses `vote_helper.generate_vote_choice` with provider-specific implementations.
* Tracks vote correctness in metrics for accuracy measurement.
* Returns the chosen phrase text (one of the 3 phrases in the phraseset).
* Raises `AIVoteError` if vote generation fails.

#### `get_common_words`

```python
words = await ai_service.get_common_words()
```

* Gets the list of common words allowed in AI-generated phrases.
* Calls `phrase_validator.common_words()` and handles different return types.
* Results are cached to avoid repeated validator calls.
* Handles conversion from sets to lists for compatibility.
* Returns empty list on validator failures with error logging.

### Backup Cycle Methods

#### `run_backup_cycle`

```python
await ai_service.run_backup_cycle()
```

* Orchestrates both copy and vote catch-up tasks for QuipFlip game.
* Delegates to `QFBackupOrchestrator` for actual backup logic.
* Does not return a value; success and error counts are logged.
* Commits at the end of a successful cycle. On failure it rolls back and logs the error.

#### `run_ir_backup_cycle`

```python
await ai_service.run_ir_backup_cycle()
```

* Orchestrates backup cycle for Initial Reaction game.
* Delegates to `IRBackupOrchestrator` for actual backup logic.
* Fills stalled backronym sets with AI entries and votes.
* Commits successful operations and rolls back on failure.

### Initial Reaction Methods

#### `generate_backronym`

```python
backronym = await ai_service.generate_backronym(
    word="FROG"  # Target word for backronym generation
)
```

* Generates a clever backronym for a word using AI.
* Returns array of words forming the backronym (e.g., ["FUNNY", "RODENT", "ON", "GRASS"]).
* Validates each word is 2-15 characters and alphabetic.
* Pads with "WORD" if AI generates insufficient or invalid words.
* Raises `AICopyError` if backronym generation fails.

#### `generate_backronym_vote`

```python
choice_index = await ai_service.generate_backronym_vote(
    word="FROG",  # Target word
    backronyms=[["FUNNY", "RODENT"], ["FAST", "RUNNER"], ...]  # List of backronym word arrays
)
```

* Generates AI vote on backronym entries using configured provider.
* Returns 0-based index of chosen backronym.
* Handles invalid AI responses by defaulting to index 0.
* Raises `AIVoteError` if vote generation fails.

### CSV Cache Methods

The AI service includes methods for working with pre-cached phrases from CSV files:

#### `_load_prompt_completions`

* Lazy-loads pre-cached prompt completions from `backend/data/prompt_completions.csv`.
* Maps normalized prompt text to lists of completion phrases.
* Used by quip generation to avoid AI API calls when possible.

#### `_load_impostor_completions`

* Lazy-loads pre-cached impostor phrases from `backend/data/fakes.csv`.
* Creates bidirectional mapping where any phrase in a row can be the original.
* Used by impostor generation to provide high-quality cached phrases.

#### `_get_unused_csv_phrases` and `_get_unused_csv_impostor_phrases`

* Filter CSV phrases to exclude those already used in the database.
* Prevent duplicate phrase usage across different rounds.
* Enable consistent high-quality AI responses without redundant API calls.

### Internal Helper Methods

#### `_determine_provider`

* Determines which AI provider to use based on configuration and API keys.
* Implements fallback logic when preferred provider is unavailable.
* Raises `AIServiceError` if no providers are configured.

#### `_prompt_ai`

* Sends prompts to the configured AI provider and handles responses.
* Measures latency and logs request/response details.
* Raises `AICopyError` for empty or failed responses.

#### `_normalize_phrase_for_lookup`

* Normalizes phrases for cache lookup by removing stop words.
* Allows "a birthday cake" to match "birthday cake" in CSV lookups.
* Improves cache hit rates for semantically equivalent phrases.

### Metrics helpers

```python
from backend.services.ai import AIMetricsService, MetricsTracker

metrics = AIMetricsService(db_session)
stats = await metrics.get_stats()
accuracy = await metrics.get_vote_accuracy()

async with MetricsTracker(metrics,
                          operation_type="copy_generation",
                          provider="openai",
                          model="gpt-5-nano") as tracker:
    result = await ai_operation()
    tracker.set_result(result, success=True)
```

## Data Model

### AIPhraseCache Table

`backend/models/qf/ai_phrase_cache.py` defines the `ai_phrase_cache` table for storing pre-validated copy phrases:

* Primary key `cache_id` uses UUIDs generated by `uuid.uuid4`.
* `prompt_round_id` is a unique foreign key to `rounds.round_id` (cascade delete) - one cache per prompt round.
* `original_phrase` and `prompt_text` are denormalized from the prompt round for context.
* `validated_phrases` is a JSON array containing 3-5 validated copy phrase strings.
* `generation_provider` and `generation_model` capture which AI backend generated the phrases (e.g., `"openai"` / `"gpt-5-nano"`).
* `used_for_backup_copy` boolean flag indicates if the cache has been used for AI backup copies.
* `used_for_hints` boolean flag indicates if the cache has been used for player hints.
* `created_at` timestamp for tracking cache age.

The cache eliminates redundant AI API calls by generating phrases once and reusing them for both backup copies and hints. Backup copies consume phrases (removed from the array), while hints do not consume phrases (all players get the same hints).

### AIQuipCache Tables

`backend/models/qf/ai_quip_cache.py` defines tables for storing validated quip responses:

* `qf_ai_quip_cache` - One row per prompt text with provider/model metadata
* `qf_ai_quip_phrase` - Individual validated quip phrases linked to cache
* `qf_ai_quip_phrase_usage` - Usage tracking linking phrases to consuming rounds

### AIMetric Table

`backend/models/qf/ai_metric.py` defines the `ai_metrics` table with the following notable columns and behaviour:

* Primary key `metric_id` uses UUIDs generated by `uuid.uuid4`.
* `operation_type` distinguishes copy and vote flows (`"copy_generation"`, `"vote_generation"`, `"stale_copy"`, `"stale_vote"`).
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
| **Email** | `ai_*@quipflip.internal` (multiple types) | `ai_stale_handler@quipflip.internal` (copies)<br>`ai_stale_voter@quipflip.internal` (votes) |
| **Trigger Time** | `ai_backup_delay_minutes` (default: 30 min) | `ai_stale_threshold_days` (default: 2 days) |
| **Human Activity Required** | Yes - requires human vote before voting | No - can act independently |
| **Batch Size** | Limited to `ai_backup_batch_size` (default: 10) | Processes ALL stale content |
| **Frequency** | Every `ai_backup_sleep_minutes` (default: 30 min) | Every `ai_stale_check_interval_hours` (default: 6 hours) |
| **Purpose** | Handle temporary gaps in activity | Handle permanently abandoned content |
| **Operation Types** | `"copy_generation"`, `"vote_generation"` | `"stale_copy"`, `"stale_vote"` |

### Architecture

The stale handler uses the same `AIService` for generation but has its own orchestration logic in `StaleAIService`.

### Key Methods

* **`StaleAIService.run_stale_cycle()`** - Main entry point, processes all stale prompts and phrasesets
* **`_find_stale_prompts()`** - Queries for prompts older than threshold without phrasesets (single query, no N+1)
* **`_find_stale_phrasesets()`** - Queries for phrasesets older than threshold still accepting votes
* **`_get_or_create_stale_player()`** - Manages stale AI players using shared AIService helper

### Workflow

1. **Startup**: Background task starts after delay
2. **Query Phase**: Find all prompts/phrasesets older than `ai_stale_threshold_days`
3. **Copy Phase**: For each stale prompt, generate copy using `AIService.get_impostor_phrase`
4. **Vote Phase**: For each stale phraseset, generate vote using `AIService.generate_vote_choice`
5. **Sleep**: Wait `ai_stale_check_interval_hours` before next cycle

### Error Recovery

* **Failed Copy Generation**: Prompt is re-enqueued for retry
* **Race Conditions**: Double-check pattern prevents conflicts
* **Closed Phrasesets**: Status check before voting prevents voting on finalized sets
* **Metrics Failures**: Wrapped in try/except to prevent blocking the cycle

## Troubleshooting tips

* Verify that at least one API key is configured; missing keys raise `AIServiceError` during initialization.
* When `MetricsTracker` records repeated failures, inspect `ai_metrics.error_message` for provider error details.
* Check phrase cache usage with `used_for_backup_copy` and `used_for_hints` flags to debug cache depletion.
* Monitor CSV cache hit rates in logs to verify pre-cached phrases are being used effectively.
* Use the stale handler configuration to handle permanently abandoned content that backup AI cannot process.
