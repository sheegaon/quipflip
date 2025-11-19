// API Response Types based on backend documentation

// Notification types
export type NotificationType = 'copy_submitted' | 'vote_submitted';

export interface NotificationWebSocketMessage {
  type: 'notification';
  notification_type: NotificationType;
  actor_username: string;
  action: 'copied' | 'voted on';
  recipient_role: 'prompt' | 'copy';
  phrase_text: string;
  timestamp: string;
}

export interface Player {
  player_id: string;
  username: string;
  email: string;
  wallet: number;
  vault: number;
  starting_balance: number;
  daily_bonus_available: boolean;
  daily_bonus_amount: number;
  last_login_date: string | null;
  outstanding_prompts: number;
  created_at: string;
  is_guest?: boolean;
  is_admin?: boolean;
  locked_until?: string | null;
  flag_dismissal_streak?: number;
}

export interface ChangePasswordResponse {
  message: string;
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: 'bearer';
}

export interface UpdateEmailResponse {
  email: string;
}

export interface ChangeUsernameResponse {
  username: string;
  message: string;
}

export interface AdminPlayerSummary {
  player_id: string;
  username: string;
  email: string;
  wallet: number;
  created_at: string;
  outstanding_prompts: number;
}

export interface AdminDeletePlayerResponse {
  deleted_player_id: string;
  deleted_username: string;
  deleted_email: string;
  deletion_counts: Record<string, number>;
}

export interface AdminResetPasswordResponse {
  player_id: string;
  username: string;
  email: string;
  generated_password: string;
  message: string;
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  player_id: string;
  username: string;
}

export interface WsAuthTokenResponse {
  token: string;
  expires_in: number;
  token_type: 'bearer';
}

export interface CreatePlayerResponse extends AuthTokenResponse {
  wallet: number;
  vault: number;
  message: string;
}

export interface CreateGuestResponse extends AuthTokenResponse {
  wallet: number;
  vault: number;
  email: string;
  password: string;
  message: string;
}

export interface UpgradeGuestResponse extends AuthTokenResponse {
  message: string;
}

export interface SuggestUsernameResponse {
  suggested_username: string;
}

export interface PromptState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  cost: number;
  prompt_text: string;
  feedback_type?: 'like' | 'dislike' | null;
}

export interface CopyState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  cost: number;
  original_phrase: string;
  discount_active: boolean;
  is_second_copy?: boolean;
  prompt_round_id?: string;
}

export interface VoteState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  phraseset_id: string;
  prompt_text: string;
  phrases: string[];
}

export interface ActiveRound {
  round_id: string | null;
  round_type: 'prompt' | 'copy' | 'vote' | null;
  expires_at: string | null;
  state: PromptState | CopyState | VoteState | null;
}

export interface FlagCopyRoundResponse {
  flag_id: string;
  refund_amount: number;
  penalty_kept: number;
  status: 'pending' | 'confirmed' | 'dismissed';
  message: string;
}

export interface AbandonRoundResponse {
  round_id: string;
  round_type: 'prompt' | 'copy' | 'vote';
  status: 'abandoned';
  refund_amount: number;
  penalty_kept: number;
  message: string;
}

export interface FlaggedPromptItem {
  flag_id: string;
  prompt_round_id: string;
  copy_round_id: string | null;
  reporter_player_id: string;
  reporter_username: string;
  prompt_player_id: string;
  prompt_username: string;
  reviewer_player_id: string | null;
  reviewer_username: string | null;
  status: 'pending' | 'confirmed' | 'dismissed';
  original_phrase: string;
  prompt_text: string | null;
  round_cost: number;
  partial_refund_amount: number;
  penalty_kept: number;
  queue_removed: boolean;
  previous_phraseset_status: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface FlaggedPromptListResponse {
  flags: FlaggedPromptItem[];
}

export interface PendingResult {
  phraseset_id: string;
  prompt_text: string;
  completed_at: string;
  role: string;
  result_viewed: boolean;
  prompt_round_id?: string;
  copy_round_id?: string;
}

export interface PendingResultsResponse {
  pending: PendingResult[];
}

export interface DailyBonusResponse {
  success: boolean;
  amount: number;
  new_wallet: number;
  new_vault: number;
}

export interface BetaSurveyAnswerPayload {
  question_id: string;
  value: number | string | string[] | Record<string, unknown> | null;
}

export interface BetaSurveySubmissionRequest {
  survey_id: string;
  answers: BetaSurveyAnswerPayload[];
}

export interface BetaSurveySubmissionResponse {
  status: 'submitted' | 'already_submitted';
  message: string;
}

export interface BetaSurveyStatusResponse {
  eligible: boolean;
  has_submitted: boolean;
  total_rounds: number;
}

export interface BetaSurveySubmissionRecord {
  response_id: string;
  player_id: string;
  survey_id: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface WeeklyLeaderboardEntry {
  player_id: string;
  username: string;
  role: 'prompt' | 'copy' | 'voter';
  total_costs: number;
  total_earnings: number;
  net_earnings: number;
  win_rate: number;
  total_rounds: number;
  rank: number | null;
  is_current_player: boolean;
}

export interface GrossEarningsLeaderboardEntry {
  player_id: string;
  username: string;
  vault_balance: number;  // Total vault balance (all-time) or vault balance change (weekly)
  total_rounds: number;
  rank: number | null;
  is_current_player: boolean;
  is_bot?: boolean;
  is_ai?: boolean;
}

export interface RoleLeaderboard {
  role: 'prompt' | 'copy' | 'voter';
  leaders: WeeklyLeaderboardEntry[];
}

export interface GrossEarningsLeaderboard {
  leaders: GrossEarningsLeaderboardEntry[];
}

export interface LeaderboardResponse {
  prompt_leaderboard: RoleLeaderboard;
  copy_leaderboard: RoleLeaderboard;
  voter_leaderboard: RoleLeaderboard;
  gross_earnings_leaderboard: GrossEarningsLeaderboard;
  generated_at: string;
}

export interface BetaSurveyListResponse {
  submissions: BetaSurveySubmissionRecord[];
}

export interface PracticePhraseset {
  phraseset_id: string;
  prompt_text: string;
  original_phrase: string;
  copy_phrase_1: string;
  copy_phrase_2: string;
  prompt_player: string;
  copy1_player: string;
  copy2_player: string;
  prompt_player_is_ai?: boolean;
  copy1_player_is_ai?: boolean;
  copy2_player_is_ai?: boolean;
  hints?: string[] | null;
  votes?: PhrasesetVoteDetail[];
}

export interface RoundAvailability {
  can_prompt: boolean;
  can_copy: boolean;
  can_vote: boolean;
  prompts_waiting: number;
  phrasesets_waiting: number;
  copy_discount_active: boolean;
  copy_cost: number;
  current_round_id: string | null;
  // Game constants from config
  prompt_cost: number;
  vote_cost: number;
  vote_payout_correct: number;
  abandoned_penalty: number;
}

export interface RoundDetails {
  round_id: string;
  type: string;
  status: string;
  expires_at: string;
  prompt_text?: string | null;
  original_phrase?: string | null;
  submitted_phrase?: string | null;
  cost: number;
}

export interface StartPromptResponse {
  round_id: string;
  prompt_text: string;
  expires_at: string;
  cost: number;
}

export interface StartCopyResponse {
  round_id: string;
  original_phrase: string;
  prompt_round_id: string;
  expires_at: string;
  cost: number;
  discount_active: boolean;
  is_second_copy: boolean;
}

export interface StartVoteResponse {
  round_id: string;
  phraseset_id: string;
  prompt_text: string;
  phrases: string[];
  expires_at: string;
}

export interface SubmitPhraseResponse {
  success: boolean;
  phrase: string;
  // Second copy eligibility (for copy rounds only)
  eligible_for_second_copy?: boolean;
  second_copy_cost?: number;
  prompt_round_id?: string;
  original_phrase?: string;
}

export interface HintResponse {
  hints: string[];
}

export interface VoteResponse {
  correct: boolean;
  payout: number;
  original_phrase: string;
  your_choice: string;
}

export interface VoteResult {
  phrase: string;
  vote_count: number;
  is_original: boolean;
  voters: string[];
}

export interface PhrasesetResults {
  prompt_text: string;
  votes: VoteResult[];
  your_phrase: string;
  your_role: string;
  original_phrase?: string;
  your_points: number;
  total_points: number;
  your_payout: number;
  vault_skim_amount: number;
  total_pool: number;
  total_votes: number;
  already_collected: boolean;
  finalized_at: string;
  correct_vote_count: number;
  incorrect_vote_count: number;
  correct_vote_points: number;
  incorrect_vote_points: number;
  prize_pool_base: number;
  vote_cost: number;
  vote_payout_correct: number;
  system_contribution: number;
  second_copy_contribution: number;
}

export type PhrasesetStatus =
  | 'waiting_copies'
  | 'waiting_copy1'
  | 'active'
  | 'voting'
  | 'closing'
  | 'finalized'
  | 'abandoned';

export interface PhrasesetSummary {
  phraseset_id: string | null;
  prompt_round_id: string;
  copy_round_id?: string | null;
  prompt_text: string;
  your_role: 'prompt' | 'copy';
  your_phrase: string | null;
  original_phrase?: string | null;
  status: PhrasesetStatus;
  created_at: string;
  updated_at: string | null;
  vote_count: number | null;
  third_vote_at: string | null;
  fifth_vote_at: string | null;
  finalized_at: string | null;
  has_copy1: boolean;
  has_copy2: boolean;
  your_payout: number | null;
  result_viewed: boolean | null;
  new_activity_count: number;
}

export interface PhrasesetListResponse {
  phrasesets: PhrasesetSummary[];
  total: number;
  has_more: boolean;
}

export interface PhrasesetDashboardCounts {
  prompts: number;
  copies: number;
  unclaimed_prompts: number;
  unclaimed_copies: number;
}

export interface PhrasesetDashboardSummary {
  in_progress: PhrasesetDashboardCounts;
  finalized: PhrasesetDashboardCounts;
  total_unclaimed_amount: number;
}

export interface CompletedPhrasesetItem {
  phraseset_id: string;
  prompt_text: string;
  created_at: string;
  finalized_at: string;
  vote_count: number;
  total_pool: number;
}

export interface CompletedPhrasesetsResponse {
  phrasesets: CompletedPhrasesetItem[];
}

export interface PhrasesetContributor {
  round_id: string;
  player_id: string;
  username: string;
  is_you: boolean;
  is_ai?: boolean;
  phrase?: string | null;
}

export interface PhrasesetVoteDetail {
  vote_id: string;
  voter_id: string;
  voter_username: string;
  is_ai?: boolean;
  voted_phrase: string;
  correct: boolean;
  voted_at: string;
}

export interface PhrasesetActivityEntry {
  activity_id: string;
  phraseset_id?: string;
  prompt_round_id?: string;
  activity_type: string;
  player_id?: string;
  player_username?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface PhrasesetDetails {
  phraseset_id: string;
  prompt_round_id: string;
  copy_round_1_id: string | null;
  copy_round_2_id: string | null;
  prompt_text: string;
  status: PhrasesetStatus;
  original_phrase: string | null;
  copy_phrase_1: string | null;
  copy_phrase_2: string | null;
  contributors: PhrasesetContributor[];
  vote_count: number;
  third_vote_at: string | null;
  fifth_vote_at: string | null;
  closes_at: string | null;
  votes: PhrasesetVoteDetail[];
  total_pool: number;
  results: {
    vote_counts: Record<string, number>;
    payouts: Record<
      string,
      {
        player_id: string;
        payout: number;
        points: number;
      }
    >;
    total_pool: number;
  } | null;
  your_role: 'prompt' | 'copy';
  your_phrase: string | null;
  your_payout: number | null;
  result_viewed: boolean;
  activity: PhrasesetActivityEntry[];
  created_at: string;
  finalized_at: string | null;
}

export interface ClaimPrizeResponse {
  success: boolean;
  amount: number;
  new_wallet: number;
  new_vault: number;
  already_claimed: boolean;
}

export interface UnclaimedResult {
  phraseset_id: string;
  prompt_text: string;
  your_role: 'prompt' | 'copy';
  your_phrase: string | null;
  finalized_at: string;
  your_payout: number;
}

export interface UnclaimedResultsResponse {
  unclaimed: UnclaimedResult[];
  total_unclaimed_amount: number;
}

export interface DashboardData {
  player: Player;
  current_round: ActiveRound;
  pending_results: PendingResult[];
  phraseset_summary: PhrasesetDashboardSummary;
  unclaimed_results: UnclaimedResult[];
  round_availability: RoundAvailability;
}

export interface ApiError {
  detail: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  redis: string;
}

export interface ApiInfo {
  message: string;
  version: string;
  environment: string;
  docs: string;
}

export interface GameStatus {
  version: string;
  environment: string;
  phrase_validation: {
    mode: 'local' | 'remote';
    healthy: boolean | null;
  };
}

export interface SubmitPromptFeedbackRequest {
  feedback_type: 'like' | 'dislike';
}

export interface PromptFeedbackResponse {
  success: boolean;
  feedback_type: 'like' | 'dislike';
  message: string;
}

export interface GetPromptFeedbackResponse {
  feedback_type: 'like' | 'dislike' | null;
  feedback_id: string | null;
  created_at: string | null;
}

export interface RoleStatistics {
  role: 'prompt' | 'copy' | 'voter';
  total_rounds: number;
  total_earnings: number;
  average_earnings: number;
  win_rate: number;
  total_phrasesets?: number;
  average_votes_received?: number;
  correct_votes?: number;
  vote_accuracy?: number;
}

export interface EarningsBreakdown {
  prompt_earnings: number;
  copy_earnings: number;
  vote_earnings: number;
  daily_bonuses: number;
  total_earnings: number;
  prompt_spending: number;
  copy_spending: number;
  vote_spending: number;
  total_spending: number;
}

export interface PlayFrequency {
  total_rounds_played: number;
  days_active: number;
  rounds_per_day: number;
  last_active: string;
  member_since: string;
}

export interface HistoricalTrendPoint {
  period: string;
  win_rate: number;
  earnings: number;
  rounds_played: number;
}

export interface PlayerStatistics {
  player_id: string;
  username: string;
  email: string;
  wallet: number;
  vault: number;
  prompt_stats: RoleStatistics;
  copy_stats: RoleStatistics;
  voter_stats: RoleStatistics;
  earnings: EarningsBreakdown;
  frequency: PlayFrequency;
  historical_trends?: HistoricalTrendPoint[];
}

export type TutorialProgress =
  | 'not_started'
  | 'welcome'
  | 'dashboard'
  | 'prompt_round'
  | 'copy_round'
  | 'vote_round'
  | 'rounds_guide'
  | 'completed';

export interface TutorialStatus {
  tutorial_completed: boolean;
  tutorial_progress: TutorialProgress;
  tutorial_started_at: string | null;
  tutorial_completed_at: string | null;
}

export interface UpdateTutorialProgressResponse {
  success: boolean;
  tutorial_status: TutorialStatus;
}

// Quest system types
export type QuestStatus = 'active' | 'completed' | 'claimed';
export type QuestCategory = 'streak' | 'quality' | 'activity' | 'milestone';

export interface Quest {
  quest_id: string;
  quest_type: string;
  name: string;
  description: string;
  status: QuestStatus;
  progress: Record<string, unknown>;
  reward_amount: number;
  category: QuestCategory;
  created_at: string;
  completed_at: string | null;
  claimed_at: string | null;
  progress_percentage: number;
  progress_current: number;
  progress_target: number;
}

export interface QuestListResponse {
  quests: Quest[];
  total_count: number;
  active_count: number;
  completed_count: number;
  claimed_count: number;
  claimable_count: number;
}

export interface ClaimQuestRewardResponse {
  success: boolean;
  quest_type: string;
  reward_amount: number;
  new_wallet: number;
  new_vault: number;
}

// Online Users feature types
export interface OnlineUser {
  username: string;
  last_action: string;
  last_action_category: string;
  last_activity: string;
  time_ago: string;
  wallet: number;
  vault: number;
  created_at: string;
}

export interface OnlineUsersResponse {
  users: OnlineUser[];
  total_count: number;
}

// Admin Configuration
export interface AdminConfig {
  // Game Constants
  starting_balance: number;
  daily_bonus_amount: number;
  prompt_cost: number;
  copy_cost_normal: number;
  copy_cost_discount: number;
  vote_cost: number;
  vote_payout_correct: number;
  abandoned_penalty: number;
  prize_pool_base: number;
  max_outstanding_quips: number;
  copy_discount_threshold: number;

  // Timing
  prompt_round_seconds: number;
  copy_round_seconds: number;
  vote_round_seconds: number;
  grace_period_seconds: number;

  // Vote finalization thresholds
  vote_max_votes: number;
  vote_closing_threshold: number;
  vote_closing_window_minutes: number;
  vote_minimum_threshold: number;
  vote_minimum_window_minutes: number;

  // Phrase Validation
  phrase_min_words: number;
  phrase_max_words: number;
  phrase_max_length: number;
  phrase_min_char_per_word: number;
  phrase_max_char_per_word: number;
  significant_word_min_length: number;

  // AI Service
  ai_provider: string;
  ai_openai_model: string;
  ai_gemini_model: string;
  ai_timeout_seconds: number;
  ai_backup_delay_minutes: number;
  ai_backup_batch_size: number;
  ai_backup_sleep_minutes: number;
  ai_stale_handler_enabled: boolean;
  ai_stale_threshold_days: number;
  ai_stale_check_interval_hours: number;
}

export interface UpdateAdminConfigResponse {
  success: boolean;
  key: string;
  value: number | string;
  message?: string;
}

// Party Mode types
export interface PartyParticipant {
  participant_id: string;
  player_id: string;
  username: string;
  is_ai: boolean;
  is_host: boolean;
  status: 'JOINED' | 'READY' | 'ACTIVE' | 'COMPLETED';
  prompts_submitted: number;
  copies_submitted: number;
  votes_submitted: number;
  prompts_required: number;
  copies_required: number;
  votes_required: number;
  joined_at: string | null;
  ready_at: string | null;
}

export interface PartySessionProgress {
  total_prompts: number;
  total_copies: number;
  total_votes: number;
  required_prompts: number;
  required_copies: number;
  required_votes: number;
  players_ready_for_next_phase: number;
  total_players: number;
}

export interface PartySession {
  session_id: string;
  party_code: string;
  host_player_id: string;
  status: 'LOBBY' | 'ACTIVE' | 'COMPLETED';
  current_phase: 'LOBBY' | 'PROMPT' | 'COPY' | 'VOTE' | 'RESULTS';
  min_players: number;
  max_players: number;
  phase_started_at: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  participants: PartyParticipant[];
  progress: PartySessionProgress;
}

export interface CreatePartySessionRequest {
  min_players?: number;
  max_players?: number;
  prompts_per_player?: number;
  copies_per_player?: number;
  votes_per_player?: number;
}

export interface CreatePartySessionResponse {
  session_id: string;
  party_code: string;
  host_player_id: string;
  status: string;
  current_phase: string;
  created_at: string;
  participants: PartyParticipant[];
  min_players: number;
  max_players: number;
}

export interface JoinPartySessionRequest {
  party_code: string;
}

export interface JoinPartySessionResponse {
  session_id: string;
  party_code: string;
  status: string;
  current_phase: string;
  participants: PartyParticipant[];
  participant_count: number;
  min_players: number;
  max_players: number;
}

export interface PartyListItem {
  session_id: string;
  host_username: string;
  participant_count: number;
  min_players: number;
  max_players: number;
  created_at: string;
  is_full: boolean;
}

export interface PartyListResponse {
  parties: PartyListItem[];
  total_count: number;
}

export interface MarkReadyResponse {
  participant_id: string;
  status: string;
  session: {
    ready_count: number;
    total_count: number;
    can_start: boolean;
  };
}

export interface StartPartySessionResponse {
  session_id: string;
  status: string;
  current_phase: string;
  phase_started_at: string;
  locked_at: string;
  participants: PartyParticipant[];
}

export type PartySessionStatusResponse = PartySession;

// Party Round Response - Discriminated Union based on round_type
export type StartPartyRoundResponse =
  | {
      round_type: 'prompt';
      round_id: string;
      party_round_id: string;
      prompt_text: string;
      expires_at: string;
      cost: number;
      session_progress: {
        your_prompts_submitted: number;
        prompts_required: number;
        players_done: number;
        total_players: number;
      };
    }
  | {
      round_type: 'copy';
      round_id: string;
      party_round_id: string;
      original_phrase: string;
      prompt_round_id: string;
      expires_at: string;
      cost: number;
      discount_active: boolean;
      is_second_copy: boolean;
      from_party: boolean;
      session_progress: {
        your_copies_submitted: number;
        copies_required: number;
        players_done: number;
        total_players: number;
      };
    }
  | {
      round_type: 'vote';
      round_id: string;
      party_round_id: string;
      phraseset_id: string;
      prompt_text: string;
      phrases: string[];
      expires_at: string;
      from_party: boolean;
      session_progress: {
        your_votes_submitted: number;
        votes_required: number;
        players_done: number;
        total_players: number;
      };
    };

export interface SubmitPartyRoundRequest {
  phrase: string;
}

export interface SubmitPartyRoundResponse {
  success: boolean;
  phrase: string;
  round_type: string;
  session_progress: Record<string, number>;
  phase_transition?: Record<string, unknown> | null;
}

export interface PartyPlayerStats {
  player_id: string;
  username: string;
  rank: number;
  spent: number;
  earned: number;
  net: number;
  votes_on_originals: number;
  votes_fooled: number;
  correct_votes: number;
  total_votes: number;
  vote_accuracy: number;
  prompts_submitted: number;
  copies_submitted: number;
  votes_submitted: number;
}

export interface PartyAward {
  player_id: string;
  username: string;
  metric_value: number;
}

export interface PartyPhrasesetSummary {
  phraseset_id: string;
  prompt_text: string;
  original_phrase: string;
  vote_count: number;
  original_player: string;
  most_votes: string;
  votes_breakdown: Record<string, number>;
}

export interface PartyResultsResponse {
  session_id: string;
  party_code: string;
  completed_at: string | null;
  rankings: PartyPlayerStats[];
  awards: Record<string, PartyAward>;
  phrasesets_summary: PartyPhrasesetSummary[];
}

export interface PartyPingResponse {
  success: boolean;
  message: string;
}

// Party Mode WebSocket message types - Discriminated Union
export type PartyWebSocketMessage =
  | {
      type: 'player_joined';
      session_id: string;
      data?: {
        player_id: string;
        username: string;
        participant_count: number;
      };
      player_id?: string;
      username?: string;
      participant_count?: number;
      timestamp: string;
    }
  | {
      type: 'player_left';
      session_id: string;
      data?: {
        player_id: string;
        username: string;
        participant_count: number;
      };
      player_id?: string;
      username?: string;
      participant_count?: number;
      timestamp: string;
    }
  | {
      type: 'player_ready';
      session_id: string;
      data?: {
        player_id: string;
        username: string;
        ready_count: number;
        total_count: number;
      };
      player_id?: string;
      username?: string;
      ready_count?: number;
      total_count?: number;
      timestamp: string;
    }
  | {
      type: 'session_started';
      session_id: string;
      data?: {
        current_phase: string;
        participant_count: number;
        message: string;
      };
      timestamp: string;
    }
  | {
      type: 'phase_transition';
      session_id: string;
      data?: {
        old_phase: string;
        new_phase: string;
        message: string;
      };
      timestamp: string;
    }
  | {
      type: 'player_progress';
      session_id: string;
      data?: {
        player_id: string;
        username: string;
        action: string;
        progress: {
          prompts_submitted: number;
          copies_submitted: number;
          votes_submitted: number;
        };
        session_progress: {
          players_done_with_phase: number;
          total_players: number;
        };
      };
      player_id?: string;
      username?: string;
      action?: string;
      progress?: {
        prompts_submitted: number;
        copies_submitted: number;
        votes_submitted: number;
      };
      session_progress?: {
        players_done_with_phase: number;
        total_players: number;
      };
      timestamp: string;
    }
  | {
      type: 'session_completed';
      session_id: string;
      data?: {
        completed_at: string;
        message: string;
      };
      timestamp: string;
    }
  | {
      type: 'session_update';
      session_id: string;
      data?: Record<string, unknown>;
      reason?: string;
      message?: string;
      timestamp: string;
    }
  | {
      type: 'host_ping';
      session_id: string;
      data?: {
        host_player_id: string;
        host_username: string;
        join_url: string;
      };
      timestamp: string;
    };
