// API Response Types based on backend documentation
// Common types shared across games
export type GameType = 'qf' | 'mm' | 'ir' | 'tl';

export interface GamePlayerSnapshot {
  game_type: GameType;
  wallet?: number;
  vault?: number;
  tutorial_completed?: boolean;
}

export interface GlobalPlayerInfo {
  player_id: string;
  username: string;
  email?: string | null;
  is_guest: boolean;
  is_admin: boolean;
  created_at: string;
  last_login_date?: string | null;
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  player_id: string;
  username: string;
  player: GlobalPlayerInfo;
  game_type?: GameType | null;
  game_data?: GamePlayerSnapshot | null;
  legacy_wallet?: number | null;
  legacy_vault?: number | null;
  legacy_tutorial_completed?: boolean | null;
}

export interface AuthSessionResponse {
  player_id: string;
  username: string;
  player: GlobalPlayerInfo;
  game_type?: GameType | null;
  game_data?: GamePlayerSnapshot | null;
  legacy_wallet?: number | null;
  legacy_vault?: number | null;
  legacy_tutorial_completed?: boolean | null;
}

export interface WsAuthTokenResponse {
  token: string;
  expires_in: number;
  token_type: 'bearer';
}

export interface SuggestUsernameResponse {
  suggested_username: string;
}

export interface ApiError {
  detail: string;
  message?: string;
  response?: {
    status?: number;
    statusText?: string;
    data?: unknown;
  };
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

export interface Caption {
  caption_id: string;
  text: string;
  author_username?: string | null;
  is_ai?: boolean;
  is_bot?: boolean;
  is_system?: boolean;
  is_seed_caption?: boolean;
  is_circle_member?: boolean;
  in_circle?: boolean;
}

export interface MemeDetails {
  meme_id: string;
  image_url: string;
  title?: string;
  alt_text?: string;
}

export interface MemeCaptionOption {
  caption_id: string;
  text: string;
  author?: string;
  is_original?: boolean;
  riff_on_caption_id?: string | null;
}

export interface MemeVoteResult {
  round_id: string;
  selected_caption_id: string;
  payout: number;
  wallet?: number;
  vault?: number;
  meme?: MemeDetails;
  captions?: MemeCaptionOption[];
  winning_caption_id?: string | null;
  has_submitted_caption?: boolean;
}

// ThinkLink (TL) game types
export type TLTutorialProgress =
  | 'welcome'
  | 'dashboard'
  | 'gameplay'
  | 'scoring'
  | 'strategy'
  | 'completed'
  | 'not_started';

export interface TLDashboardResponse {
  player_id: string;
  username: string;
  tl_wallet: number;
  tl_vault: number;
  tl_tutorial_completed: boolean;
  tl_tutorial_progress: string;
  created_at: string;
}

export interface TLBalanceResponse {
  tl_wallet: number;
  tl_vault: number;
  total_balance: number;
}

export interface TLRoundAvailability {
  can_start_round: boolean;
  error_message?: string | null;
  tl_wallet: number;
  tl_vault: number;
  entry_cost: number;
  max_payout: number;
  starting_balance: number;
}

export interface TLStartRoundResponse {
  round_id: string;
  prompt_text: string;
  snapshot_answer_count: number;
  snapshot_total_weight: number;
  created_at: string;
}

export interface TLSubmitGuessRequest {
  guess_text: string;
}

export interface TLSubmitGuessResponse {
  was_match: boolean;
  matched_answer_count: number;
  matched_cluster_ids: string[];
  new_strikes: number;
  current_coverage: number;
  round_status: string;
  round_id: string;
}

export interface TLRoundDetails {
  round_id: string;
  prompt_id: string;
  prompt_text: string;
  snapshot_answer_count: number;
  snapshot_total_weight: number;
  matched_clusters: string[];
  strikes: number;
  status: string;
  final_coverage?: number | null;
  gross_payout?: number | null;
  wallet_award?: number | null;
  vault_award?: number | null;
  created_at: string;
  ended_at?: string | null;
}

export interface TLAbandonRoundResponse {
  round_id: string;
  status: string;
  refund_amount: number;
}

export type TLRoundHistorySortBy = 'date' | 'payout' | 'coverage';
export type TLRoundHistorySortDirection = 'asc' | 'desc';

export interface TLRoundHistoryItem {
  round_id: string;
  prompt_text: string;
  final_coverage?: number | null;
  gross_payout?: number | null;
  strikes: number;
  status: string;
  created_at: string;
  ended_at?: string | null;
}

export interface TLRoundHistoryResponse {
  rounds: TLRoundHistoryItem[];
}

export interface TLRoundHistoryQuery {
  sort_by?: TLRoundHistorySortBy;
  sort_direction?: TLRoundHistorySortDirection;
  min_coverage?: number;
  max_coverage?: number;
  min_payout?: number;
  max_payout?: number;
  start_date?: string;
  end_date?: string;
}

export interface TLPromptPreviewResponse {
  prompt_id: string;
  prompt_text: string;
}

export interface TLSeedPromptsRequest {
  prompts: string[];
}

export interface TLSeedPromptsResponse {
  created_count: number;
  skipped_duplicates: number;
}

export interface TLCorpusStats {
  prompt_id: string;
  prompt_text: string;
  active_answers: number;
  total_answers: number;
}

export interface TLPruneCorpusResponse {
  removed_answers: number;
  removed_clusters: number;
}

export interface VoteRoundState {
  round_id: string;
  image_id: string;
  image_url: string;
  thumbnail_url?: string | null;
  attribution_text?: string | null;
  captions: Caption[];
  expires_at: string;
  cost: number;
}

// Notification types
export type NotificationType = 'copy_submitted' | 'vote_submitted';
export interface PingWebSocketMessage {
  type: 'ping';
  from_username: string;
  timestamp: string;
  join_url?: string;
}

export interface NotificationWebSocketMessage {
  type: 'notification';
  notification_type: NotificationType;
  actor_username: string;
  action: 'copied' | 'voted on';
  recipient_role: 'prompt' | 'copy';
  phrase_text: string;
  timestamp: string;
}

export type NotificationStreamMessage = NotificationWebSocketMessage | PingWebSocketMessage;

export interface Player extends GlobalPlayerInfo {
  email?: string | null;
  wallet?: number;
  vault?: number;
  starting_balance?: number;
  daily_bonus_available?: boolean;
  daily_bonus_amount?: number;
  outstanding_prompts?: number;
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

export interface QFPromptState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  cost: number;
  prompt_text: string;
  feedback_type?: 'like' | 'dislike' | null;
}

export interface QFCopyState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  cost: number;
  original_phrase: string;
  discount_active: boolean;
  is_second_copy?: boolean;
  prompt_round_id?: string;
}

export interface QFVoteState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  phraseset_id: string;
  prompt_text: string;
  phrases: string[];
}

export interface QFActiveRound {
  round_id: string | null;
  round_type: 'prompt' | 'copy' | 'vote' | null;
  expires_at: string | null;
  state: QFPromptState | QFCopyState | QFVoteState | null;
}

export interface QFFlagCopyRoundResponse {
  flag_id: string;
  refund_amount: number;
  penalty_kept: number;
  status: 'pending' | 'confirmed' | 'dismissed';
  message: string;
}

export interface QFAbandonRoundResponse {
  round_id: string;
  round_type: 'prompt' | 'copy' | 'vote';
  status: 'abandoned';
  refund_amount: number;
  penalty_kept: number;
  message: string;
}

export interface QFFlaggedPromptItem {
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

export interface QFFlaggedPromptListResponse {
  flags: QFFlaggedPromptItem[];
}

export interface QFPendingResult {
  phraseset_id: string;
  prompt_text: string;
  completed_at: string;
  role: string;
  result_viewed: boolean;
  prompt_round_id?: string;
  copy_round_id?: string;
}

export interface QFPendingResultsResponse {
  pending: QFPendingResult[];
}

export interface QFDailyBonusResponse {
  success: boolean;
  amount: number;
  new_wallet: number;
  new_vault: number;
}

export interface QFBetaSurveyAnswerPayload {
  question_id: string;
  value: number | string | string[] | Record<string, unknown> | null;
}

export interface QFBetaSurveySubmissionRequest {
  survey_id: string;
  answers: QFBetaSurveyAnswerPayload[];
}

export interface QFBetaSurveySubmissionResponse {
  status: 'submitted' | 'already_submitted';
  message: string;
}

export interface QFBetaSurveyStatusResponse {
  eligible: boolean;
  has_submitted: boolean;
  total_rounds: number;
}

export interface QFBetaSurveySubmissionRecord {
  response_id: string;
  player_id: string;
  survey_id: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface QFWeeklyLeaderboardEntry {
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

export interface QFGrossEarningsLeaderboardEntry {
  player_id: string;
  username: string;
  vault_balance: number;  // Total vault balance (all-time) or vault balance change (weekly)
  total_rounds: number;
  rank: number | null;
  is_current_player: boolean;
  is_bot?: boolean;
  is_ai?: boolean;
}

export interface QFRoleLeaderboard {
  role: 'prompt' | 'copy' | 'voter';
  leaders: QFWeeklyLeaderboardEntry[];
}

export interface QFGrossEarningsLeaderboard {
  leaders: QFGrossEarningsLeaderboardEntry[];
}

export interface QFLeaderboardResponse {
  prompt_leaderboard: QFRoleLeaderboard;
  copy_leaderboard: QFRoleLeaderboard;
  voter_leaderboard: QFRoleLeaderboard;
  gross_earnings_leaderboard: QFGrossEarningsLeaderboard;
  generated_at: string;
}

export interface QFBetaSurveyListResponse {
  submissions: QFBetaSurveySubmissionRecord[];
}

export interface QFPracticePhraseset {
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
  votes?: QFPhrasesetVoteDetail[];
}

export interface QFRoundAvailability {
  can_prompt: boolean;
  can_copy: boolean;
  can_vote: boolean;
  can_submit_caption: boolean;
  prompts_waiting: number;
  phrasesets_waiting: number;
  copy_discount_active: boolean;
  copy_cost: number;
  current_round_id: string | null;
  // Game constants from config
  prompt_cost: number;
  round_entry_cost: number;
  caption_submission_cost: number;
  free_captions_remaining: number;
  daily_bonus_available: boolean;
  vote_cost: number;
  vote_payout_correct: number;
  abandoned_penalty: number;
}

export interface QFRoundDetails {
  round_id: string;
  type: string;
  status: string;
  expires_at: string;
  prompt_text?: string | null;
  original_phrase?: string | null;
  submitted_phrase?: string | null;
  cost: number;
}

export interface QFStartPromptResponse {
  round_id: string;
  prompt_text: string;
  expires_at: string;
  cost: number;
}

export interface QFStartCopyResponse {
  round_id: string;
  original_phrase: string;
  prompt_round_id: string;
  expires_at: string;
  cost: number;
  discount_active: boolean;
  is_second_copy: boolean;
}

export interface QFStartVoteResponse {
  round_id: string;
  phraseset_id: string;
  prompt_text: string;
  phrases: string[];
  expires_at: string;
}

/**
 * Party context included in round responses when in party mode.
 * Contains player progress and session progress information.
 */
export interface QFPartyContext {
  session_id: string;
  current_phase: string;
  your_progress: {
    prompts_submitted: number;
    prompts_required: number;
    copies_submitted: number;
    copies_required: number;
    votes_submitted: number;
    votes_required: number;
  };
  session_progress: {
    players_ready_for_next_phase: number;
    total_players: number;
  };
}

export interface QFSubmitPhraseResponse {
  success: boolean;
  phrase: string;
  round_type?: 'prompt' | 'copy';
  // Second copy eligibility (for copy rounds only)
  eligible_for_second_copy?: boolean;
  second_copy_cost?: number;
  prompt_round_id?: string;
  original_phrase?: string;
  // Party-specific fields (present when in party mode)
  party_session_id?: string;
  party_round_id?: string;
  party_context?: QFPartyContext;
}

export interface QFHintResponse {
  hints: string[];
}

export interface QFVoteResponse {
  correct: boolean;
  payout: number;
  original_phrase: string;
  your_choice: string;
  // Party-specific fields
  party_session_id?: string;
  party_context?: QFPartyContext;
}

export interface QFVoteResult {
  phrase: string;
  vote_count: number;
  is_original: boolean;
  voters: string[];
}

export interface QFPhrasesetResults {
  prompt_text: string;
  votes: QFVoteResult[];
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

export type QFPhrasesetStatus =
  | 'waiting_copies'
  | 'waiting_copy1'
  | 'active'
  | 'voting'
  | 'closing'
  | 'finalized'
  | 'abandoned';

export interface QFPhrasesetSummary {
  phraseset_id: string | null;
  prompt_round_id: string;
  copy_round_id?: string | null;
  prompt_text: string;
  your_role: 'prompt' | 'copy';
  your_phrase: string | null;
  original_phrase?: string | null;
  status: QFPhrasesetStatus;
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

export interface QFPhrasesetListResponse {
  phrasesets: QFPhrasesetSummary[];
  total: number;
  has_more: boolean;
}

export interface QFPhrasesetDashboardCounts {
  prompts: number;
  copies: number;
  unclaimed_prompts: number;
  unclaimed_copies: number;
}

export interface QFPhrasesetDashboardSummary {
  in_progress: QFPhrasesetDashboardCounts;
  finalized: QFPhrasesetDashboardCounts;
  total_unclaimed_amount: number;
}

export interface QFCompletedPhrasesetItem {
  phraseset_id: string;
  prompt_text: string;
  created_at: string;
  finalized_at: string;
  vote_count: number;
  total_pool: number;
}

export interface QFCompletedPhrasesetsResponse {
  phrasesets: QFCompletedPhrasesetItem[];
}

export interface QFPhrasesetContributor {
  round_id: string;
  player_id: string;
  username: string;
  is_you: boolean;
  is_ai?: boolean;
  email?: string;
  phrase?: string | null;
}

export interface QFPhrasesetVoteDetail {
  vote_id: string;
  voter_id: string;
  voter_username: string;
  is_ai?: boolean;
  email?: string;
  voted_phrase: string;
  correct: boolean;
  voted_at: string;
}

export interface QFPhrasesetActivityEntry {
  activity_id: string;
  phraseset_id?: string;
  prompt_round_id?: string;
  activity_type: string;
  player_id?: string;
  player_username?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface QFPhrasesetDetails {
  phraseset_id: string;
  prompt_round_id: string;
  copy_round_1_id: string | null;
  copy_round_2_id: string | null;
  prompt_text: string;
  status: QFPhrasesetStatus;
  original_phrase: string | null;
  copy_phrase_1: string | null;
  copy_phrase_2: string | null;
  contributors: QFPhrasesetContributor[];
  vote_count: number;
  third_vote_at: string | null;
  fifth_vote_at: string | null;
  closes_at: string | null;
  votes: QFPhrasesetVoteDetail[];
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
  activity: QFPhrasesetActivityEntry[];
  created_at: string;
  finalized_at: string | null;
}

export interface QFClaimPrizeResponse {
  success: boolean;
  amount: number;
  new_wallet: number;
  new_vault: number;
  already_claimed: boolean;
}

export interface QFUnclaimedResult {
  phraseset_id: string;
  prompt_text: string;
  your_role: 'prompt' | 'copy';
  your_phrase: string | null;
  finalized_at: string;
  your_payout: number;
}

export interface QFUnclaimedResultsResponse {
  unclaimed: QFUnclaimedResult[];
  total_unclaimed_amount: number;
}

export interface QFDashboardData {
  player: Player;
  current_round: QFActiveRound;
  current_vote_round?: QFActiveRound | null;
  current_caption_round?: QFActiveRound | null;
  pending_results: QFPendingResult[];
  phraseset_summary: QFPhrasesetDashboardSummary;
  unclaimed_results: QFUnclaimedResult[];
  round_availability: QFRoundAvailability;
}

export interface QFSubmitPromptFeedbackRequest {
  feedback_type: 'like' | 'dislike';
}

export interface QFPromptFeedbackResponse {
  success: boolean;
  feedback_type: 'like' | 'dislike';
  message: string;
}

export interface QFGetPromptFeedbackResponse {
  feedback_type: 'like' | 'dislike' | null;
  feedback_id: string | null;
  created_at: string | null;
}

export interface QFRoleStatistics {
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

export interface QFEarningsBreakdown {
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

export interface QFPlayFrequency {
  total_rounds_played: number;
  days_active: number;
  rounds_per_day: number;
  last_active: string;
  member_since: string;
}

export interface QFHistoricalTrendPoint {
  period: string;
  win_rate: number;
  earnings: number;
  rounds_played: number;
}

export interface QFPlayerStatistics {
  player_id: string;
  username: string;
  email: string;
  wallet: number;
  vault: number;
  prompt_stats: QFRoleStatistics;
  copy_stats: QFRoleStatistics;
  voter_stats: QFRoleStatistics;
  earnings: QFEarningsBreakdown;
  frequency: QFPlayFrequency;
  historical_trends?: QFHistoricalTrendPoint[];
}

export type QFTutorialProgress =
  | 'not_started'
  | 'welcome'
  | 'dashboard'
  | 'prompt_round'
  | 'copy_round'
  | 'vote_round'
  | 'rounds_guide'
  | 'completed';

export interface QFTutorialStatus {
  tutorial_completed: boolean;
  tutorial_progress: QFTutorialProgress;
  tutorial_started_at: string | null;
  tutorial_completed_at: string | null;
}

export interface QFUpdateTutorialProgressResponse {
  success: boolean;
  tutorial_status: QFTutorialStatus;
}

// QFQuest system types
export type QFQuestStatus = 'active' | 'completed' | 'claimed';
export type QFQuestCategory = 'streak' | 'quality' | 'activity' | 'milestone';

export interface QFQuest {
  quest_id: string;
  quest_type: string;
  name: string;
  description: string;
  status: QFQuestStatus;
  progress: Record<string, unknown>;
  reward_amount: number;
  category: QFQuestCategory;
  created_at: string;
  completed_at: string | null;
  claimed_at: string | null;
  progress_percentage: number;
  progress_current: number;
  progress_target: number;
}

export interface QFQuestListResponse {
  quests: QFQuest[];
  total_count: number;
  active_count: number;
  completed_count: number;
  claimed_count: number;
  claimable_count: number;
}

export interface QFClaimQuestRewardResponse {
  success: boolean;
  quest_type: string;
  reward_amount: number;
  new_wallet: number;
  new_vault: number;
}

// Online Users feature types
export interface QFOnlineUser {
  username: string;
  last_action: string;
  last_action_category: string;
  last_activity: string;
  time_ago: string;
  wallet: number;
  vault: number;
  created_at: string;
}

export interface QFOnlineUsersResponse {
  users: QFOnlineUser[];
  total_count: number;
}

export interface QFPingUserResponse {
  success: boolean;
  message: string;
}

// Admin Configuration
export interface QFAdminConfig {
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

export interface QFUpdateAdminConfigResponse {
  success: boolean;
  key: string;
  value: number | string;
  message?: string;
}

// Party Mode types
export interface QFPartyParticipant {
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

export interface QFPartySessionProgress {
  total_prompts: number;
  total_copies: number;
  total_votes: number;
  required_prompts: number;
  required_copies: number;
  required_votes: number;
  players_ready_for_next_phase: number;
  total_players: number;
}

export interface QFPartySession {
  session_id: string;
  party_code: string;
  host_player_id: string;
  status: 'OPEN' | 'IN_PROGRESS' | 'COMPLETED' | 'ABANDONED';
  current_phase: 'LOBBY' | 'PROMPT' | 'COPY' | 'VOTE' | 'RESULTS';
  min_players: number;
  max_players: number;
  phase_started_at: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  participants: QFPartyParticipant[];
  progress: QFPartySessionProgress;
}

export interface QFCreatePartySessionRequest {
  min_players?: number;
  max_players?: number;
  prompts_per_player?: number;
  copies_per_player?: number;
  votes_per_player?: number;
}

export interface QFCreatePartySessionResponse {
  session_id: string;
  party_code: string;
  host_player_id: string;
  status: string;
  current_phase: string;
  created_at: string;
  participants: QFPartyParticipant[];
  min_players: number;
  max_players: number;
}

export interface QFJoinPartySessionRequest {
  party_code: string;
}

export interface QFJoinPartySessionResponse {
  session_id: string;
  party_code: string;
  status: string;
  current_phase: string;
  participants: QFPartyParticipant[];
  participant_count: number;
  min_players: number;
  max_players: number;
}

export interface QFPartyListItem {
  session_id: string;
  host_username: string;
  participant_count: number;
  min_players: number;
  max_players: number;
  created_at: string;
  is_full: boolean;
}

export interface QFPartyListResponse {
  parties: QFPartyListItem[];
  total_count: number;
}

export interface QFMarkReadyResponse {
  participant_id: string;
  status: string;
  session: {
    ready_count: number;
    total_count: number;
    can_start: boolean;
  };
}

export interface QFStartPartySessionResponse {
  session_id: string;
  status: string;
  current_phase: string;
  phase_started_at: string;
  locked_at: string;
  participants: QFPartyParticipant[];
}

export type QFPartySessionStatusResponse = QFPartySession;

// Party Round Response - Discriminated Union based on round_type
export interface QFStartPartyPromptResponse {
  round_type: 'prompt';
  round_id: string;
  party_round_id: string;
  prompt_text: string;
  expires_at: string;
  cost: number;
  status?: string;
  session_progress: {
    your_prompts_submitted: number;
    prompts_required: number;
    players_done: number;
    total_players: number;
  };
  party_context?: QFPartyContext;
}

export interface QFStartPartyCopyResponse {
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
  party_context?: QFPartyContext;
}

export interface QFStartPartyVoteResponse {
  round_type: 'vote';
  round_id: string;
  party_round_id: string;
  phraseset_id: string;
  prompt_text: string;
  phrases: string[];
  expires_at: string;
  cost?: number;
  from_party: boolean;
  session_progress: {
    your_votes_submitted: number;
    votes_required: number;
    players_done: number;
    total_players: number;
  };
  party_context?: QFPartyContext;
}

export type QFStartPartyRoundResponse =
  | QFStartPartyPromptResponse
  | QFStartPartyCopyResponse
  | QFStartPartyVoteResponse;

export interface QFSubmitPartyRoundRequest {
  phrase: string;
}

export interface QFSubmitPartyRoundResponse {
  success: boolean;
  phrase: string;
  round_type: string;
  session_progress: Record<string, number>;
  phase_transition?: Record<string, unknown> | null;
}

export interface QFPartyPlayerStats {
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

export interface QFPartyAward {
  player_id: string;
  username: string;
  metric_value: number;
}

export interface QFPartyPhrasesetSummary {
  phraseset_id: string;
  prompt_text: string;
  original_phrase: string;
  vote_count: number;
  original_player: string;
  most_votes: string;
  votes_breakdown: Record<string, number>;
}

export interface QFPartyResultsResponse {
  session_id: string;
  party_code: string;
  completed_at: string | null;
  rankings: QFPartyPlayerStats[];
  awards: Record<string, QFPartyAward>;
  phrasesets_summary: QFPartyPhrasesetSummary[];
}

export interface QFPartyPingResponse {
  success: boolean;
  message: string;
}

// Party Mode WebSocket message types - Discriminated Union
export type QFPlayerJoinedPayload = {
  player_id: string;
  username: string;
  participant_count: number;
};

export type QFPlayerLeftPayload = QFPlayerJoinedPayload;

export type QFPlayerReadyPayload = {
  player_id: string;
  username: string;
  ready_count: number;
  total_count: number;
};

export type QFPhaseTransitionPayload = {
  old_phase: string;
  new_phase: string;
  message: string;
};

export type QFProgressUpdatePayload = {
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

export type QFSessionStartedPayload = {
  current_phase: string;
  participant_count: number;
  message: string;
};

export type QFSessionCompletedPayload = {
  completed_at: string | null;
  message: string;
};

export type QFSessionUpdatePayload = Record<string, unknown> & {
  reason?: string;
  message?: string;
};

export type QFHostPingPayload = {
  host_player_id: string;
  host_username: string;
  join_url: string;
};

type WebsocketPayload<TBase, TPayload> =
  TBase & ({ data: TPayload } | ({ data?: undefined } & TPayload));

export type QFPartyWebSocketMessage =
  | WebsocketPayload<
    { type: 'player_joined'; session_id: string; timestamp: string },
    QFPlayerJoinedPayload
  >
  | WebsocketPayload<
    { type: 'player_left'; session_id: string; timestamp: string },
    QFPlayerLeftPayload
  >
  | WebsocketPayload<
    { type: 'player_ready'; session_id: string; timestamp: string },
    QFPlayerReadyPayload
  >
  | WebsocketPayload<
    { type: 'session_started'; session_id: string; timestamp: string },
    QFSessionStartedPayload
  >
  | WebsocketPayload<
    { type: 'phase_transition'; session_id: string; timestamp: string },
    QFPhaseTransitionPayload
  >
  | WebsocketPayload<
    { type: 'progress_update'; session_id: string; timestamp: string },
    QFProgressUpdatePayload
  >
  | WebsocketPayload<
    { type: 'session_completed'; session_id: string; timestamp: string },
    QFSessionCompletedPayload
  >
  | WebsocketPayload<
    { type: 'session_update'; session_id: string; timestamp: string },
    QFSessionUpdatePayload
  >
  | WebsocketPayload<
    { type: 'host_ping'; session_id: string; timestamp: string },
    QFHostPingPayload
  >;

// MM game types
export interface MMPromptState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  cost: number;
  prompt_text: string;
  feedback_type?: 'like' | 'dislike' | null;
}

export interface MMCopyState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  cost: number;
  original_phrase: string;
  discount_active: boolean;
  is_second_copy?: boolean;
  prompt_round_id?: string;
}

export interface MMVoteState {
  round_id: string;
  status: 'active' | 'submitted' | 'expired' | 'abandoned';
  expires_at: string;
  phraseset_id: string;
  prompt_text: string;
  phrases: string[];
}

export interface MMActiveRound {
  round_id: string | null;
  round_type: 'prompt' | 'copy' | 'vote' | null;
  expires_at: string | null;
  state: MMPromptState | MMCopyState | MMVoteState | null;
}

export interface MMFlagCopyRoundResponse {
  flag_id: string;
  refund_amount: number;
  penalty_kept: number;
  status: 'pending' | 'confirmed' | 'dismissed';
  message: string;
}

export interface MMAbandonRoundResponse {
  round_id: string;
  round_type: 'prompt' | 'copy' | 'vote';
  status: 'abandoned';
  refund_amount: number;
  penalty_kept: number;
  message: string;
}

export interface MMFlaggedPromptItem {
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

export interface MMFlaggedPromptListResponse {
  flags: MMFlaggedPromptItem[];
}

// IR game types
export interface IRPlayer {
  player_id: string;
  username: string;
  email: string | null;
  wallet: number;
  vault: number;
  is_guest: boolean;
  daily_bonus_available: boolean;
  created_at: string;
  last_login_date: string | null;
}

export interface IRBackronymSet {
  set_id: string;
  word: string;
  mode: 'standard' | 'rapid';
  status: 'open' | 'voting' | 'finalized';
  entry_count: number;
  vote_count: number;
  non_participant_vote_count: number;
  total_pool: number;
  creator_final_pool: number;
  created_at: string;
  transitions_to_voting_at: string | null;
  voting_finalized_at: string | null;
}

export interface IRBackronymEntry {
  entry_id: string;
  set_id: string;
  player_id: string;
  backronym_text: string[];
  is_ai: boolean;
  submitted_at: string;
  vote_share_pct: number | null;
  received_votes: number;
  forfeited_to_vault: number;
}

export interface IRBackronymVote {
  vote_id: string;
  set_id: string;
  player_id: string;
  chosen_entry_id: string;
  is_participant_voter: boolean;
  is_ai: boolean;
  is_correct_popular: boolean | null;
  created_at: string;
}

export interface IRPendingResult {
  set_id: string;
  word: string;
  payout_amount: number;
  result_viewed: boolean;
}

export interface IRSetDetails {
  set: IRBackronymSet;
  entries: IRBackronymEntry[];
  votes: IRBackronymVote[];
  player_entry?: IRBackronymEntry;
  player_vote?: IRBackronymVote;
}

export interface IRPlayerStats {
  player_id: string;
  username: string;
  wallet: number;
  vault: number;
  entries_submitted: number;
  votes_cast: number;
  net_earnings: number;
}

export interface IRLeaderboardEntry {
  player_id: string;
  username: string;
  rank: number;
  vault: number;
  value: number;
}

export interface IRDashboardPlayerSummary {
  player_id: string;
  username: string;
  wallet: number;
  vault: number;
  daily_bonus_available: boolean;
  created_at: string;
}

export interface IRDashboardData {
  player: IRDashboardPlayerSummary;
  active_session: {
    set_id: string;
    word: string;
    status: string;
    has_submitted_entry: boolean;
    has_voted: boolean;
  } | null;
  pending_results: IRPendingResult[];
  wallet: number;
  vault: number;
  daily_bonus_available: boolean;
}

export interface IRRegisterRequest {
  email: string;
  password: string;
  username?: string;
}

export interface IRLoginRequest {
  username?: string;
  email?: string;
  password: string;
}

export interface IRUpgradeGuestRequest {
  username: string;
  email: string;
  password: string;
}

export interface IRSubmitBackronymRequest {
  words: string[];
}

export interface IRValidateBackronymRequest {
  words: string[];
}

export interface IRSubmitVoteRequest {
  entry_id: string;
}

export interface IRValidateBackronymResponse {
  is_valid: boolean;
  error?: string | null;
}

export interface IRAuthResponse {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
  player_id: string;
  username: string;
  wallet?: number;
  vault?: number;
  email?: string;
  password?: string;
  message?: string;
}

export interface IRStartSessionResponse {
  set_id: string;
  word: string;
  mode: string;
  status: string;
}

export interface IRBalanceResponse {
  player_id: string;
  username: string;
  email: string | null;
  wallet: number;
  vault: number;
  starting_balance: number;
  daily_bonus_available: boolean;
  daily_bonus_amount: number;
  last_login_date: string | null;
  created_at: string;
  outstanding_prompts: number;
  is_guest: boolean;
  is_admin?: boolean;
  locked_until: string | null;
  flag_dismissal_streak?: number;
}

export interface IRClaimBonusResponse {
  bonus_amount: number;
  new_balance: number;
  next_claim_available_at: string;
}

export interface IRSetStatusResponse {
  set: IRBackronymSet;
  player_has_submitted: boolean;
  player_has_voted: boolean;
}

export interface IRResultsResponse {
  set: IRBackronymSet;
  entries: IRBackronymEntry[];
  votes: IRBackronymVote[];
  player_entry: IRBackronymEntry | null;
  player_vote: IRBackronymVote | null;
  payout_breakdown: {
    entry_cost: number;
    vote_cost: number;
    gross_payout: number;
    vault_rake: number;
    net_payout: number;
    vote_reward: number;
  } | null;
}

export type IRTutorialProgress =
  | 'not_started'
  | 'welcome'
  | 'dashboard'
  | 'backronym_entry'
  | 'backronym_voting'
  | 'rounds_guide'
  | 'completed';

export interface IRTutorialStatus {
  tutorial_completed: boolean;
  tutorial_progress: IRTutorialProgress;
  tutorial_started_at: string | null;
  tutorial_completed_at: string | null;
}

export interface IRUpdateTutorialProgressResponse {
  success: boolean;
  tutorial_status: IRTutorialStatus;
}

export interface IRApiError {
  detail: string;
  code?: string;
}

// Additional MM game types generated from MemeMint definitions
export interface MMPendingResult {
  phraseset_id: string;
  prompt_text: string;
  completed_at: string;
  role: string;
  result_viewed: boolean;
  prompt_round_id?: string;
  copy_round_id?: string;
}


export interface MMPendingResultsResponse {
  pending: MMPendingResult[];
}


export interface MMDailyBonusResponse {
  success: boolean;
  amount: number;
  new_wallet: number;
  new_vault: number;
}


export interface MMBetaSurveyAnswerPayload {
  question_id: string;
  value: number | string | string[] | Record<string, unknown> | null;
}


export interface MMBetaSurveySubmissionRequest {
  survey_id: string;
  answers: MMBetaSurveyAnswerPayload[];
}


export interface MMBetaSurveySubmissionResponse {
  status: 'submitted' | 'already_submitted';
  message: string;
}


export interface MMBetaSurveyStatusResponse {
  eligible: boolean;
  has_submitted: boolean;
  total_rounds: number;
}


export interface MMBetaSurveySubmissionRecord {
  response_id: string;
  player_id: string;
  survey_id: string;
  payload: Record<string, unknown>;
  created_at: string;
}


export interface MMWeeklyLeaderboardEntry {
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


export interface MMGrossEarningsLeaderboardEntry {
  player_id: string;
  username: string;
  vault_balance: number; // Total vault balance (all-time) or vault balance change (weekly)
  total_rounds: number;
  rank: number | null;
  is_current_player: boolean;
  is_bot?: boolean;
  is_ai?: boolean;
}


export interface MMRoleLeaderboard {
  role: 'prompt' | 'copy' | 'voter';
  leaders: MMWeeklyLeaderboardEntry[];
}


export interface MMGrossEarningsLeaderboard {
  leaders: MMGrossEarningsLeaderboardEntry[];
}


export interface MMLeaderboardResponse {
  prompt_leaderboard: MMRoleLeaderboard;
  copy_leaderboard: MMRoleLeaderboard;
  voter_leaderboard: MMRoleLeaderboard;
  gross_earnings_leaderboard: MMGrossEarningsLeaderboard;
  generated_at: string;
}


export interface MMBetaSurveyListResponse {
  submissions: MMBetaSurveySubmissionRecord[];
}


export interface MMPracticePhraseset {
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
  votes?: MMPhrasesetVoteDetail[];
}


export interface MMRoundAvailability {
  can_vote: boolean;
  can_submit_caption: boolean;
  round_entry_cost: number;
  caption_submission_cost: number;
  free_captions_remaining: number;
  current_round_id?: string | null;
  daily_bonus_available: boolean;
  // Legacy fields kept optional during transition
  can_prompt?: boolean;
  can_copy?: boolean;
  prompts_waiting?: number;
  phrasesets_waiting?: number;
  copy_discount_active?: boolean;
  copy_cost?: number;
  prompt_cost?: number;
  vote_cost?: number;
  vote_payout_correct?: number;
  abandoned_penalty?: number;
}


export interface MMRoundDetails {
  round_id: string;
  type: 'vote' | 'caption_submission';
  status: string;
  expires_at: string;
  image_id: string;
  image_url: string;
  cost: number;
  // For vote rounds
  captions?: Caption[];
  chosen_caption_id?: string | null;
  // For caption submission rounds
  submitted_caption_id?: string | null;
  submitted_caption_text?: string | null;
}


export interface MMStartPromptResponse {
  round_id: string;
  prompt_text: string;
  expires_at: string;
  cost: number;
}


export interface MMStartCopyResponse {
  round_id: string;
  original_phrase: string;
  prompt_round_id: string;
  expires_at: string;
  cost: number;
  discount_active: boolean;
  is_second_copy: boolean;
}


export interface MMStartVoteResponse {
  round_id: string;
  phraseset_id: string;
  prompt_text: string;
  phrases: string[];
  expires_at: string;
}


export interface MMSubmitPhraseResponse {
  success: boolean;
  phrase: string;
  round_type?: 'prompt' | 'copy';
  // Second copy eligibility (for copy rounds only)
  eligible_for_second_copy?: boolean;
  second_copy_cost?: number;
  prompt_round_id?: string;
  original_phrase?: string;
}


export interface MMHintResponse {
  hints: string[];
}


export interface MMVoteResponse {
  correct: boolean;
  payout: number;
  original_phrase: string;
  your_choice: string;
}


export interface MMPhrasesetVoteResult {
  phrase: string;
  vote_count: number;
  is_original: boolean;
  voters: string[];
}


export interface MMPhrasesetResults {
  prompt_text: string;
  votes: MMPhrasesetVoteResult[];
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

// MemeMint types - Updated to match backend schemas

export interface MMMemeImage {
  image_id: string;
  image_url: string;
  thumbnail_url?: string | null;
  attribution_text?: string | null;
}


export interface MMVoteRoundState {
  round_id: string;
  image_id: string;
  image_url: string;
  thumbnail_url?: string | null;
  attribution_text?: string | null;
  captions: Caption[];
  expires_at: string;
  cost: number;
}


export interface MMVoteResult {
  success: boolean;
  chosen_caption_id: string;
  payout: number;
  refund_amount?: number;
  correct: boolean;
  new_wallet: number;
  new_vault: number;
}


export interface MMCaptionSubmissionResult {
  success: boolean;
  caption_id: string;
  cost: number;
  used_free_slot: boolean;
  new_wallet: number;
}


export interface MMDashboardData {
  player: Player;
  round_availability: MMRoundAvailability;
  current_vote_round?: MMVoteRoundState | null;
  current_caption_round?: MMCaptionSubmissionResult | null;
}

// Legacy MemeMint types - kept for backward compatibility during transition

export interface MMMemeDetails {
  meme_id: string;
  image_url: string;
  title?: string;
  alt_text?: string;
}


export interface MMMemeCaptionOption {
  caption_id: string;
  text: string;
  author?: string;
  is_original?: boolean;
  riff_on_caption_id?: string | null;
}


export interface MMMemeVoteRound {
  round_id: string;
  expires_at: string | null;
  meme: MMMemeDetails;
  captions: MMMemeCaptionOption[];
  free_captions_remaining?: number;
  has_submitted_caption?: boolean;
}


export interface MMMemeVoteResult {
  round_id: string;
  selected_caption_id: string;
  payout: number;
  wallet?: number;
  vault?: number;
  meme?: MMMemeDetails;
  captions?: MMMemeCaptionOption[];
  winning_caption_id?: string | null;
  has_submitted_caption?: boolean;
}


export type MMMemeCaptionType = 'original' | 'riff';


export interface MMMemeCaptionSubmission {
  round_id: string;
  text: string;
  // kind and parent_caption_id are determined algorithmically by the backend
  // based on cosine similarity analysis
}


export interface MMMemeCaptionResponse {
  success: boolean;
  caption_id: string;
  cost: number;
  used_free_slot: boolean;
  new_wallet: number;
}


export type MMPhrasesetStatus =
  | 'waiting_copies'
  | 'waiting_copy1'
  | 'active'
  | 'voting'
  | 'closing'
  | 'finalized'
  | 'abandoned';


export interface MMPhrasesetSummary {
  phraseset_id: string | null;
  prompt_round_id: string;
  copy_round_id?: string | null;
  prompt_text: string;
  your_role: 'prompt' | 'copy';
  your_phrase: string | null;
  original_phrase?: string | null;
  status: MMPhrasesetStatus;
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


export interface MMPhrasesetListResponse {
  phrasesets: MMPhrasesetSummary[];
  total: number;
  has_more: boolean;
}


export interface MMPhrasesetDashboardCounts {
  prompts: number;
  copies: number;
  unclaimed_prompts: number;
  unclaimed_copies: number;
}


export interface MMPhrasesetDashboardSummary {
  in_progress: MMPhrasesetDashboardCounts;
  finalized: MMPhrasesetDashboardCounts;
  total_unclaimed_amount: number;
}


export interface MMCompletedPhrasesetItem {
  phraseset_id: string;
  prompt_text: string;
  created_at: string;
  finalized_at: string;
  vote_count: number;
  total_pool: number;
}


export interface MMCompletedPhrasesetsResponse {
  phrasesets: MMCompletedPhrasesetItem[];
}


export interface MMPhrasesetContributor {
  round_id: string;
  player_id: string;
  username: string;
  is_you: boolean;
  is_ai?: boolean;
  email?: string;
  phrase?: string | null;
}


export interface MMPhrasesetVoteDetail {
  vote_id: string;
  voter_id: string;
  voter_username: string;
  is_ai?: boolean;
  email?: string;
  voted_phrase: string;
  correct: boolean;
  voted_at: string;
}


export interface MMPhrasesetActivityEntry {
  activity_id: string;
  phraseset_id?: string;
  prompt_round_id?: string;
  activity_type: string;
  player_id?: string;
  player_username?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}


export interface MMPhrasesetDetails {
  phraseset_id: string;
  prompt_round_id: string;
  copy_round_1_id: string | null;
  copy_round_2_id: string | null;
  prompt_text: string;
  status: MMPhrasesetStatus;
  original_phrase: string | null;
  copy_phrase_1: string | null;
  copy_phrase_2: string | null;
  contributors: MMPhrasesetContributor[];
  vote_count: number;
  third_vote_at: string | null;
  fifth_vote_at: string | null;
  closes_at: string | null;
  votes: MMPhrasesetVoteDetail[];
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
  activity: MMPhrasesetActivityEntry[];
  created_at: string;
  finalized_at: string | null;
}


export interface MMClaimPrizeResponse {
  success: boolean;
  amount: number;
  new_wallet: number;
  new_vault: number;
  already_claimed: boolean;
}


export interface MMUnclaimedResult {
  phraseset_id: string;
  prompt_text: string;
  your_role: 'prompt' | 'copy';
  your_phrase: string | null;
  finalized_at: string;
  your_payout: number;
}


export interface MMUnclaimedResultsResponse {
  unclaimed: MMUnclaimedResult[];
  total_unclaimed_amount: number;
}


export interface MMSubmitPromptFeedbackRequest {
  feedback_type: 'like' | 'dislike';
}


export interface MMPromptFeedbackResponse {
  success: boolean;
  feedback_type: 'like' | 'dislike';
  message: string;
}


export interface MMGetPromptFeedbackResponse {
  feedback_type: 'like' | 'dislike' | null;
  feedback_id: string | null;
  created_at: string | null;
}


export interface MMRoleStatistics {
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


export interface MMEarningsBreakdown {
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


export interface MMPlayFrequency {
  total_rounds_played: number;
  days_active: number;
  rounds_per_day: number;
  last_active: string;
  member_since: string;
}


export interface MMHistoricalTrendPoint {
  period: string;
  win_rate: number;
  earnings: number;
  rounds_played: number;
}


export interface MMPlayerStatistics {
  player_id: string;
  username: string;
  email: string;
  wallet: number;
  vault: number;
  prompt_stats: MMRoleStatistics;
  copy_stats: MMRoleStatistics;
  voter_stats: MMRoleStatistics;
  earnings: MMEarningsBreakdown;
  frequency: MMPlayFrequency;
  historical_trends?: MMHistoricalTrendPoint[];
}


export type MMTutorialProgress =
  | 'not_started'
  | 'welcome'
  | 'dashboard'
  | 'prompt_round'
  | 'copy_round'
  | 'vote_round'
  | 'rounds_guide'
  | 'completed';


export interface MMTutorialStatus {
  tutorial_completed: boolean;
  tutorial_progress: MMTutorialProgress;
  tutorial_started_at: string | null;
  tutorial_completed_at: string | null;
}


export interface MMUpdateTutorialProgressResponse {
  success: boolean;
  tutorial_status: MMTutorialStatus;
}

// MMQuest system types

export type MMQuestStatus = 'active' | 'completed' | 'claimed';

export type MMQuestCategory = 'streak' | 'quality' | 'activity' | 'milestone';


export interface MMQuest {
  quest_id: string;
  quest_type: string;
  name: string;
  description: string;
  status: MMQuestStatus;
  progress: Record<string, unknown>;
  reward_amount: number;
  category: MMQuestCategory;
  created_at: string;
  completed_at: string | null;
  claimed_at: string | null;
  progress_percentage: number;
  progress_current: number;
  progress_target: number;
}


export interface MMQuestListResponse {
  quests: MMQuest[];
  total_count: number;
  active_count: number;
  completed_count: number;
  claimed_count: number;
  claimable_count: number;
}


export interface MMClaimQuestRewardResponse {
  success: boolean;
  quest_type: string;
  reward_amount: number;
  new_wallet: number;
  new_vault: number;
}

// Online Users feature types

export interface MMOnlineUser {
  username: string;
  last_action: string;
  last_action_category: string;
  last_activity: string;
  time_ago: string;
  wallet: number;
  vault: number;
  created_at: string;
}


export interface MMOnlineUsersResponse {
  users: MMOnlineUser[];
  total_count: number;
}


export interface MMPingUserResponse {
  success: boolean;
  message: string;
}

// Admin Configuration

export interface MMAdminConfig {
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


export interface MMUpdateAdminConfigResponse {
  success: boolean;
  key: string;
  value: number | string;
  message?: string;
}

// ===== CIRCLE TYPES =====


export interface MMCircleMember {
  player_id: string;
  username: string;
  role: 'admin' | 'member';
  joined_at: string;
}


export interface MMCircleJoinRequest {
  request_id: string;
  player_id: string;
  username: string;
  requested_at: string;
  status: 'pending' | 'approved' | 'denied';
  resolved_at?: string | null;
  resolved_by_player_id?: string | null;
}


export interface MMCircle {
  circle_id: string;
  name: string;
  description?: string | null;
  created_by_player_id: string;
  created_at: string;
  updated_at: string;
  member_count: number;
  is_public: boolean;
  status: 'active' | 'archived';
  // Contextual fields based on requesting player
  is_member: boolean;
  is_admin: boolean;
  has_pending_request: boolean;
}


export interface MMCircleListResponse {
  circles: MMCircle[];
  total_count: number;
}


export interface MMCircleMembersResponse {
  members: MMCircleMember[];
  total_count: number;
}


export interface MMCircleJoinRequestsResponse {
  join_requests: MMCircleJoinRequest[];
  total_count: number;
}


export interface MMCreateCircleRequest {
  name: string;
  description?: string;
  is_public?: boolean;
}


export interface MMCreateCircleResponse {
  success: boolean;
  circle: MMCircle;
  message: string;
}


export interface MMJoinCircleResponse {
  success: boolean;
  request_id?: string | null;
  message: string;
}


export interface MMApproveJoinRequestResponse {
  success: boolean;
  message: string;
}


export interface MMDenyJoinRequestResponse {
  success: boolean;
  message: string;
}


export interface MMAddMemberRequest {
  player_id: string;
}


export interface MMAddMemberResponse {
  success: boolean;
  message: string;
}


export interface MMRemoveMemberResponse {
  success: boolean;
  message: string;
}


export interface MMLeaveCircleResponse {
  success: boolean;
  message: string;
}
