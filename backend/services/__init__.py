from backend.services.auth_service import AuthService, AuthError, GameType
from backend.services.system_config_service import SystemConfigService
from backend.services.username_service import (
    UsernameService,
    canonicalize_username,
    is_username_allowed,
    normalize_username,
    is_username_input_valid
)
from backend.services.player_service_base import PlayerServiceBase, PlayerError
from backend.services.transaction_service import TransactionService
from backend.services.phrase_validator import PhraseValidator, get_phrase_validator, _parse_phrase
from backend.services.tutorial_service import TutorialService

# AI services
from backend.services.ai.ai_service import AIService, AICopyError, AIServiceError
from backend.services.ai.metrics_service import AIMetricsService
from backend.services.ai.stale_ai_service import StaleAIService

# QF (Quipflip) services
from backend.services.qf.player_service import QFPlayerService
from backend.services.qf.round_service import QFRoundService
from backend.services.qf.vote_service import QFVoteService
from backend.services.qf.scoring_service import QFScoringService
from backend.services.qf.queue_service import QFQueueService, PROMPT_QUEUE, PHRASESET_QUEUE
from backend.services.qf.cleanup_service import QFCleanupService
from backend.services.qf.phraseset_service import PhrasesetService
from backend.services.qf.phraseset_activity_service import ActivityService
from backend.services.qf.statistics_service import QFStatisticsService
from backend.services.qf.flagged_prompt_service import FlaggedPromptService
from backend.services.qf.quest_service import QuestService
from backend.services.qf.prompt_seeder import (
    get_current_season,
    load_prompts_from_csv,
    sync_prompts_with_database
)

# IR (Initial Reaction) services
from backend.services.ir.player_service import IRPlayerService as IRPlayerService
from backend.services.ir.player_service import PlayerError as IRPlayerError
from backend.services.ir.backronym_set_service import BackronymSetService as IRBackronymSetService
from backend.services.ir.vote_service import IRVoteService
from backend.services.ir.word_service import WordService as IRWordService
from backend.services.ir.result_view_service import IRResultViewService
from backend.services.ir.statistics_service import IRStatisticsService
from backend.services.ir.scoring_service import IRScoringService
from backend.services.ir.daily_bonus_service import IRDailyBonusService, IRDailyBonusError

# MM (Meme Mint) services
from backend.services.mm.player_service import MMPlayerService
from backend.services.mm.daily_bonus_service import MMDailyBonusService, MMDailyBonusError
from backend.services.mm.daily_state_service import MMPlayerDailyStateService
from backend.services.mm.system_config_service import MMSystemConfigService
from backend.services.mm.cleanup_service import MMCleanupService

# TL (ThinkLink) services
from backend.services.tl.player_service import TLPlayerService
from backend.services.tl.cleanup_service import TLCleanupService

__all__ = [
    # Core services
    'AuthService',
    'AuthError',
    'PlayerError',
    'GameType',
    'SystemConfigService',
    'UsernameService',
    'canonicalize_username',
    'is_username_allowed',
    'normalize_username',
    'is_username_input_valid',
    'PlayerServiceBase',
    'TransactionService',
    'TutorialService',

    # Phrase validation
    'PhraseValidator',
    'get_phrase_validator',
    '_parse_phrase',

    # AI services
    'AIService',
    'AICopyError',
    'AIServiceError',
    'AIMetricsService',
    'StaleAIService',

    # QF services
    'QFPlayerService',
    'QFRoundService',
    'QFVoteService',
    'QFScoringService',
    'QFQueueService',
    'PROMPT_QUEUE',
    'PHRASESET_QUEUE',
    'QFCleanupService',
    'PhrasesetService',
    'ActivityService',
    'QFStatisticsService',
    'FlaggedPromptService',
    'QuestService',
    'get_current_season',
    'load_prompts_from_csv',
    'sync_prompts_with_database',

    # IR services
    'IRPlayerService',
    'IRPlayerError',
    'IRBackronymSetService',
    'IRVoteService',
    'IRWordService',
    'IRResultViewService',
    'IRStatisticsService',
    'IRScoringService',
    'IRDailyBonusService',
    'IRDailyBonusError',

    # MM services
    'MMPlayerService',
    'MMDailyBonusService',
    'MMDailyBonusError',
    'MMPlayerDailyStateService',
    'MMSystemConfigService',
    'MMCleanupService',

    # TL services
    'TLPlayerService',
    'TLCleanupService',
]
