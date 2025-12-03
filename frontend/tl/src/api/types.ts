/**
 * ThinkLink (TL) API Types
 *
 * Type definitions for all ThinkLink API endpoints and responses.
 * Aligned with backend schemas in backend/schemas/tl_round.py and backend/routers/tl/player.py
 */

// ============================================================================
// Player State & Dashboard
// ============================================================================

export interface DashboardResponse {
  player_id: string;
  username: string;
  tl_wallet: number;
  tl_vault: number;
  tl_tutorial_completed: boolean;
  tl_tutorial_progress: string;
  created_at: string;
}

export interface BalanceResponse {
  tl_wallet: number;
  tl_vault: number;
  total_balance: number;
}

// ============================================================================
// Round Management
// ============================================================================

export interface RoundAvailability {
  can_start_round: boolean;
  error_message: string | null;
  tl_wallet: number;
  tl_vault: number;
  entry_cost: number;
  max_payout: number;
  starting_balance: number;
}

export interface StartRoundResponse {
  round_id: string;
  prompt_text: string;
  snapshot_answer_count: number;
  snapshot_total_weight: number;
  created_at: string;
}

export interface SubmitGuessRequest {
  guess_text: string;
}

export interface SubmitGuessResponse {
  was_match: boolean;
  matched_answer_count: number;
  matched_cluster_ids: string[];
  new_strikes: number;
  current_coverage: number;
  round_status: string;
  round_id: string;
}

export interface GuessDetail {
  guess_id: string;
  text: string;
  was_match: boolean;
  matched_cluster_ids: string[];
  caused_strike?: boolean;
  created_at: string;
}

export interface RoundDetails {
  round_id: string;
  prompt_id: string;
  prompt_text: string;
  snapshot_answer_count: number;
  snapshot_total_weight: number;
  matched_clusters: string[];
  strikes: number;
  status: string;
  final_coverage: number | null;
  gross_payout: number | null;
  created_at: string;
  ended_at: string | null;
  guesses?: GuessDetail[];
}

export interface AbandonRoundResponse {
  round_id: string;
  status: string;
  refund_amount: number;
}

// ============================================================================
// Game Info
// ============================================================================

export interface PromptPreviewResponse {
  prompt_text: string;
  hint: string;
}

// ============================================================================
// Admin Endpoints
// ============================================================================

export interface SeedPromptsRequest {
  prompts: string[];
}

export interface SeedPromptsResponse {
  created_count: number;
  skipped_count: number;
  total_count: number;
}

export interface CorpusStats {
  prompt_id: string;
  prompt_text: string;
  active_answer_count: number;
  cluster_count: number;
  total_weight: number;
  largest_cluster_size: number;
  smallest_cluster_size: number;
}

export interface PruneCorpusResponse {
  prompt_id: string;
  removed_count: number;
  current_active_count: number;
  target_count: number;
}

// ============================================================================
// Game State
// ============================================================================

/**
 * Round status values
 */
export type RoundStatus = 'active' | 'abandoned' | 'completed';

/**
 * Match outcome type
 */
export interface GuessOutcome {
  was_match: boolean;
  matchedAnswerCount: number;
  matchedClusterIds: string[];
  newStrikes: number;
  currentCoverage: number;
  roundEnded: boolean;
}

/**
 * Game statistics
 */
export interface GameStats {
  roundsCompleted: number;
  totalEarnings: number;
  averageCoverage: number;
  highestPayout: number;
}

// ============================================================================
// Error Types
// ============================================================================

export type TLErrorCode =
  | 'insufficient_balance'
  | 'round_not_found'
  | 'unauthorized'
  | 'round_not_active'
  | 'round_already_ended'
  | 'invalid_phrase'
  | 'off_topic'
  | 'too_similar'
  | 'no_prompts_available'
  | 'invalid_admin_access';

export interface TLError {
  code: TLErrorCode;
  message: string;
  statusCode: number;
}
