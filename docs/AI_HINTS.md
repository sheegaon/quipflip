# AI-Generated Hints for Copy Rounds

## Status: ✅ IMPLEMENTED

## Overview
AI-powered hint system that generates 1-3 copy phrase suggestions to help players during active copy rounds, using the same AI logic and validation as the existing backup copy player.

## Architecture

### 1. Database Layer

**Model: backend/models/hint.py**
- `hint_id` (UUID, PK)
- `prompt_round_id` (UUID, FK to rounds)
- `hint_phrases` (JSON array of 1-3 strings)
- `created_at` (timestamp)
- `generation_provider` (string: "openai" or "gemini")
- `generation_model` (string)

**Migration:** Alembic migration `b8f3d1c4a5e6_add_hints_table.py`

### 2. Backend Service Layer

**Extended backend/services/ai/ai_service.py:**
- Added `generate_copy_hints(prompt_round: Round, count: int = 3) -> list[str]` method
- Reuses existing `generate_copy_phrase()` logic with same validation
- Generates multiple distinct hints using provider/model from settings
- Tracks metrics for each hint generation
- Stores results in hints table

**Extended backend/services/ai/prompt_builder.py:**
- Added `build_hint_prompt(original_phrase: str, prompt_text: str, existing_hints: list[str] = None) -> str`
- Similar to `build_copy_prompt()` but emphasizes variety
- Includes instruction to avoid duplicating existing hints
- Requests different creative approaches (synonyms, related concepts, different word counts)

**Extended backend/services/round_service.py:**
- Added `get_or_generate_hints(round_id: UUID, player: Player, transaction_service: TransactionService) -> list[str]` method
- Checks if hints exist in database (cached)
- If not, charges hint_cost and calls AI service to generate and cache them
- Returns cached hints for subsequent requests at no cost

### 3. API Layer

**Extended backend/routers/rounds.py:**
- Added `GET /rounds/{round_id}/hints` endpoint
- Verifies player owns the active copy round
- Returns 1-3 hint phrases
- Charges hint_cost for new hints, cached hints are free

**New Schema: backend/schemas/hint.py:**
- `HintResponse` with `hints: list[str]` field

### 4. Frontend Layer

**Extended frontend/src/pages/CopyRound.tsx:**
- Added "Get AI Hints" button (shown for active copy rounds)
- Displays hints in expandable UI
- Shows loading state while fetching
- Marks hints as "inspiration only, not guaranteed valid"

**Extended frontend/src/contexts/GameContext.tsx:**
- Added `fetchCopyHints(roundId: string)` action
- Stores hints in state

**Extended frontend/src/api/client.ts:**
- Added `fetchHints(roundId: string)` function

## Key Implementation Details

**Hint Generation Strategy:**
- Generates 1-3 diverse hints by calling AI provider multiple times
- Each hint uses full context (original_phrase + prompt_text)
- Previously generated hints are passed to avoid duplicates
- Each hint is independently validated

**Validation:**
- Apply same `validate_copy()` checks to ensure hints are valid submissions
- Hints that fail validation are not returned to the player

**Caching:**
- Generated hints stored in `hints` table keyed by `prompt_round_id`
- Subsequent requests return cached hints at no cost
- One hint record per prompt round (unique constraint)

**Cost:**
- Configurable via `hint_cost` setting (default: 10 Flipcoins)
- Charged only when generating new hints
- Cached hints are free to retrieve

**UI/UX:**
- Presented as optional help tool
- Not required or pushed
- Available only during active copy rounds

## Files Modified/Created

**New Files:**
- `backend/models/hint.py`
- `backend/schemas/hint.py`
- `backend/migrations/versions/b8f3d1c4a5e6_add_hints_table.py`

**Modified Files:**
- `backend/services/ai/ai_service.py` - Added hint generation
- `backend/services/ai/prompt_builder.py` - Added hint prompts
- `backend/services/round_service.py` - Added hint retrieval/caching
- `backend/routers/rounds.py` - Added hints endpoint
- `backend/config.py` - Added hint_cost setting
- `frontend/src/pages/CopyRound.tsx` - Added hints UI
- `frontend/src/contexts/GameContext.tsx` - Added hints state
- `frontend/src/api/client.ts` - Added hints API call
- `frontend/src/api/types.ts` - Added HintResponse type

## Testing

**Unit Tests (tests/test_ai_service.py):**
- Hint generation with mock AI responses
- Validation of generated hints
- Caching behavior

**Integration Tests (tests/test_round_service.py):**
- Verify hints are valid copy phrases
- Cost charging for new hints
- Free retrieval of cached hints
- Permission checks (player must own round)

**E2E Testing:**
- Request hints from UI during copy round
- Verify hints are cached (second request doesn't regenerate)
- Verify cost is only charged once