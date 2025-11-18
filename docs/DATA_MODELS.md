# Data Model Documentation Index

The backend data layer now mirrors the code layout: shared building blocks live in `backend/models/*_base.py`, while game-specific models live in `backend/models/qf` (Quipflip) and `backend/models/ir` (Initial Reaction). Use the dedicated game guides alongside this index when exploring schemas or planning migrations.

## Where to Look

- [Quipflip Data Models](QF_DATA_MODELS.md) – complete reference for Quipflip tables and their relationships under `backend/models/qf`.
- [Initial Reaction Data Models](IR_DATA_MODELS.md) – companion reference for IR tables under `backend/models/ir`.

## Shared Base Tables

The following primitives are defined once and reused by both games:

- **Player base** (`player_base.py`) – common authentication, profile, and progression fields that each game layers additional attributes onto.
- **Token + session** (`refresh_token_base.py`) – refresh token records shared across games.
- **Transactions + balances** (`transaction_base.py`) – ledger scaffolding for wallet/vault accounting used by both economies.
- **Daily bonus** (`daily_bonus_base.py`) – daily reward tracking reused by both game modes.
- **Quests + surveys** (`quest_base.py`, `survey_response_base.py`) – shared quest progress and survey response shapes.
- **Notifications + online presence** (`notification_base.py`, `user_activity_base.py`) – reusable activity and notification primitives.
- **AI + system configuration** (`ai_metric_base.py`, `system_config_base.py`) – telemetry and feature toggle tables that inform both rule sets.

Each game-specific package imports these bases and adds its own entities (e.g., `Round`, `Phraseset`, and `Vote` for Quipflip; `BackronymSet`, `BackronymEntry`, and `BackronymVote` for Initial Reaction). Consult the game guides for full field-level definitions.
