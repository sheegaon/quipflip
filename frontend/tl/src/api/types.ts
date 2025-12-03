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

export type TutorialProgress =
  | 'welcome'
  | 'dashboard'
  | 'prompt_round'
  | 'copy_round'
  | 'vote_round'
  | 'rounds_guide'
  | 'completed'
  | 'not_started';
