// Shared CrowdCraft API types used by game-specific clients
// These types are derived from the common endpoints documented in docs/API.md

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

export interface SuggestUsernameResponse {
  suggested_username: string;
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

// Statistics types used by shared components
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

export interface HistoricalTrendPoint {
  period: string;
  win_rate: number;
  earnings: number;
  rounds_played: number;
}

export interface GrossEarningsLeaderboardEntry {
  player_id: string;
  username: string;
  vault_balance: number;
  total_rounds: number;
  rank: number | null;
  is_current_player: boolean;
  is_bot?: boolean;
  is_ai?: boolean;
}

export interface GrossEarningsLeaderboard {
  leaders: GrossEarningsLeaderboardEntry[];
}

// Player balance type returned by getBalance() - used by sessionDetection
// Matches the common Player schema used by both QF and MM
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
