from backend.services.auth_service import AuthService, AuthError, GameType
from backend.services.system_config_service import SystemConfigService
from backend.services.username_service import (
    UsernameService,
    canonicalize_username,
    is_username_profanity_free,
    normalize_username,
    is_username_input_valid
)
from backend.services.player_service_base import PlayerServiceBase
from backend.services.transaction_service import TransactionService
from backend.services.phrase_validation_client import (
    get_phrase_validation_client,
    PhraseValidationClient
)
from backend.services.phrase_validator import PhraseValidator, get_phrase_validator
from backend.services.tutorial_service import TutorialService

# QF (QuipFlip) services
from backend.services.qf.player_service import PlayerService
from backend.services.qf.round_service import RoundService
from backend.services.qf.vote_service import VoteService
from backend.services.qf.scoring_service import ScoringService
from backend.services.qf.queue_service import QueueService, PROMPT_QUEUE, PHRASESET_QUEUE
from backend.services.qf.cleanup_service import CleanupService
from backend.services.qf.phraseset_service import PhrasesetService
from backend.services.qf.phraseset_activity_service import ActivityService
from backend.services.qf.statistics_service import StatisticsService
from backend.services.qf.flagged_prompt_service import FlaggedPromptService
from backend.services.qf.prompt_seeder import (
    get_current_season,
    load_prompts_from_csv,
    sync_prompts_with_database
)

# AI services
from backend.services.ai.ai_service import AIService, AICopyError, AIServiceError
from backend.services.ai.metrics_service import AIMetricsService
from backend.services.ai.stale_ai_service import StaleAIService

# IR (Initial Reaction) services
from backend.services.ir.player_service import PlayerService as IRPlayerService
from backend.services.ir.player_service import PlayerError as IRPlayerError
from backend.services.ir.backronym_set_service import BackronymSetService as IRBackronymSetService
from backend.services.ir.vote_service import IRVoteService
from backend.services.ir.word_service import WordService as IRWordService
from backend.services.ir.result_view_service import IRResultViewService
from backend.services.ir.statistics_service import IRStatisticsService
from backend.services.ir.scoring_service import IRScoringService
from backend.services.ir.daily_bonus_service import IRDailyBonusService, IRDailyBonusError

# IR aliases (AuthService configured for IR)
IRAuthService = AuthService
# TransactionService works for both games via game_type parameter
IRTransactionService = TransactionService

__all__ = [
    # Core services
    'AuthService',
    'AuthError',
    'GameType',
    'SystemConfigService',
    'UsernameService',
    'canonicalize_username',
    'is_username_profanity_free',
    'normalize_username',
    'is_username_input_valid',
    'PlayerServiceBase',
    'TransactionService',
    'TutorialService',

    # Phrase validation
    'get_phrase_validation_client',
    'PhraseValidationClient',
    'PhraseValidator',
    'get_phrase_validator',

    # QF services
    'PlayerService',
    'RoundService',
    'VoteService',
    'ScoringService',
    'QueueService',
    'PROMPT_QUEUE',
    'PHRASESET_QUEUE',
    'CleanupService',
    'PhrasesetService',
    'ActivityService',
    'StatisticsService',
    'FlaggedPromptService',
    'get_current_season',
    'load_prompts_from_csv',
    'sync_prompts_with_database',

    # AI services
    'AIService',
    'AICopyError',
    'AIServiceError',
    'AIMetricsService',
    'StaleAIService',

    # IR services
    'IRPlayerService',
    'IRPlayerError',
    'IRAuthService',
    'IRBackronymSetService',
    'IRVoteService',
    'IRWordService',
    'IRResultViewService',
    'IRStatisticsService',
    'IRScoringService',
    'IRTransactionService',
    'IRDailyBonusService',
    'IRDailyBonusError',
]
