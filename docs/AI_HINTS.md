Plan: AI-Generated Hints for Copy Rounds
Overview
Implement a hint system that generates 3 AI-powered copy phrase suggestions to help players during copy rounds, using the same AI logic as the existing backup copy player.
Architecture
1. Database Layer
New Model: backend/models/hint.py
hint_id (UUID, PK)
prompt_round_id (UUID, FK to rounds)
hint_phrases (JSON array of 3 strings)
created_at (timestamp)
generation_provider (string: "openai" or "gemini")
generation_model (string)
Migration: Create Alembic migration to add hints table
2. Backend Service Layer
Extend backend/services/ai/ai_service.py:
Add generate_copy_hints(prompt_round: Round, count: int = 3) -> list[str] method
Reuse existing generate_copy_phrase() logic with same validation
Generate multiple distinct hints using provider/model from settings
Track metrics for each hint generation
Store results in hints table
Extend backend/services/ai/prompt_builder.py:
Add build_hint_prompt(original_phrase: str, prompt_text: str, existing_hints: list[str] = None) -> str
Similar to build_copy_prompt() but emphasize variety
Include instruction to avoid duplicating existing hints
Request different creative approaches (synonyms, related concepts, different word counts)
Extend backend/services/round_service.py:
Add get_or_generate_hints(round_id: UUID) -> list[str] method
Check if hints exist in database
If not, call AI service to generate and cache them
Return cached hints for subsequent requests
3. API Layer
Extend backend/routers/rounds.py:
Add GET /rounds/{round_id}/hints endpoint
Verify player owns the active copy round
Return 3 hint phrases
Consider rate limiting (1 request per round)
New Schema: backend/schemas/hint.py:
HintResponse with hints: list[str] field
4. Frontend Layer
Extend frontend/src/pages/CopyRound.tsx:
Add "Get AI Hints" button (shown once per round)
Display 3 hints in expandable accordion/list
Show loading state while fetching
Mark hints as "inspiration only, not guaranteed valid"
Extend frontend/src/contexts/GameContext.tsx:
Add fetchCopyHints(roundId: string) action
Store hints in state: copyRoundHints: string[] | null
Key Implementation Details
Hint Generation Strategy: Generate 3 diverse hints by:
Calling AI provider 3 times with instruction to be different
Each hint uses full context (original_phrase + prompt_text)
Pass previously generated hints to avoid duplicates
Validation: Apply same validate_copy() checks to ensure hints are valid submissions
Caching: Store generated hints in database to avoid regeneration costs
Cost: Free for MVP (no player charge), evaluate monetization later
UI/UX: Present as optional help tool, not required or pushed
Files to Modify/Create
New: backend/models/hint.py
New: backend/schemas/hint.py
New: backend/alembic/versions/XXX_add_hints_table.py
Modify: backend/services/ai/ai_service.py
Modify: backend/services/ai/prompt_builder.py
Modify: backend/services/round_service.py
Modify: backend/routers/rounds.py
Modify: frontend/src/pages/CopyRound.tsx
Modify: frontend/src/contexts/GameContext.tsx
Modify: frontend/src/api/roundsApi.ts (add fetchHints function)
Testing Strategy
Unit tests for hint generation with mock AI responses
Integration test: verify hints are valid copy phrases
E2E test: request hints from UI during copy round
Verify hints are cached (second request doesn't regenerate)