// TypeScript types for Initial Reaction API

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

export interface BackronymSet {
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

export interface BackronymEntry {
  entry_id: string;
  set_id: string;
  player_id: string;
  backronym_text: string[];  // Array of words
  is_ai: boolean;
  submitted_at: string;
  vote_share_pct: number | null;
  received_votes: number;
  forfeited_to_vault: number;
}

export interface BackronymVote {
  vote_id: string;
  set_id: string;
  player_id: string;
  chosen_entry_id: string;
  is_participant_voter: boolean;
  is_ai: boolean;
  is_correct_popular: boolean | null;
  created_at: string;
}

export interface PendingResult {
  set_id: string;
  word: string;
  payout_amount: number;
  result_viewed: boolean;
}

export interface SetDetails {
  set: BackronymSet;
  entries: BackronymEntry[];
  votes: BackronymVote[];
  player_entry?: BackronymEntry;
  player_vote?: BackronymVote;
}

export interface PlayerStats {
  player_id: string;
  username: string;
  wallet: number;
  vault: number;
  entries_submitted: number;
  votes_cast: number;
  net_earnings: number;
}

export interface LeaderboardEntry {
  player_id: string;
  username: string;
  rank: number;
  vault: number;
  value: number;
}

export interface DashboardData {
  player: IRPlayer;
  active_session: {
    set_id: string;
    word: string;
    status: string;
    has_submitted_entry: boolean;
    has_voted: boolean;
  } | null;
  pending_results: PendingResult[];
  wallet: number;
  vault: number;
  daily_bonus_available: boolean;
}

// API Request types
export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface UpgradeGuestRequest {
  username: string;
  email: string;
  password: string;
}

export interface SubmitBackronymRequest {
  words: string[];
}

export interface ValidateBackronymRequest {
  words: string[];
}

export interface SubmitVoteRequest {
  entry_id: string;
}

export interface ValidateBackronymResponse {
  is_valid: boolean;
  error?: string | null;
}

// API Response types
export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  player: IRPlayer;
}

export interface StartSessionResponse {
  set_id: string;
  word: string;
  mode: string;
  status: string;
}

export interface BalanceResponse {
  wallet: number;
  vault: number;
  daily_bonus_available: boolean;
}

export interface ClaimBonusResponse {
  bonus_amount: number;
  new_balance: number;
  next_claim_available_at: string;
}

export interface SetStatusResponse {
  set: BackronymSet;
  player_has_submitted: boolean;
  player_has_voted: boolean;
}

export interface ResultsResponse {
  set: BackronymSet;
  entries: BackronymEntry[];
  votes: BackronymVote[];
  player_entry: BackronymEntry | null;
  player_vote: BackronymVote | null;
  payout_breakdown: {
    entry_cost: number;
    vote_cost: number;
    gross_payout: number;
    vault_rake: number;
    net_payout: number;
    vote_reward: number;
  } | null;
}

export type TutorialProgress =
  | 'not_started'
  | 'welcome'
  | 'dashboard'
  | 'backronym_entry'
  | 'backronym_voting'
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

// Error response type
export interface APIError {
  detail: string;
  code?: string;
}
