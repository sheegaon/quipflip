// API Response Types based on backend documentation

export interface Player {
  username: string;
  balance: number;
  starting_balance: number;
  daily_bonus_available: boolean;
  daily_bonus_amount: number;
  last_login_date: string;
  outstanding_prompts: number;
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  player_id: string;
  username: string;
}

export interface CreatePlayerResponse extends AuthTokenResponse {
  balance: number;
  message: string;
}

export interface SuggestUsernameResponse {
  suggested_username: string;
}

export interface PromptState {
  round_id: string;
  status: 'active' | 'submitted';
  expires_at: string;
  cost: number;
  prompt_text: string;
  feedback_type?: 'like' | 'dislike' | null;
}

export interface CopyState {
  round_id: string;
  status: 'active' | 'submitted';
  expires_at: string;
  cost: number;
  original_phrase: string;
  discount_active: boolean;
}

export interface VoteState {
  round_id: string;
  status: 'active' | 'submitted';
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

export interface PendingResult {
  phraseset_id: string;
  prompt_text: string;
  completed_at: string;
  role: string;
  payout_claimed: boolean;
}

export interface PendingResultsResponse {
  pending: PendingResult[];
}

export interface DailyBonusResponse {
  success: boolean;
  amount: number;
  new_balance: number;
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
}

export interface PhrasesetResults {
  prompt_text: string;
  votes: VoteResult[];
  your_phrase: string;
  your_role: string;
  your_points: number;
  your_payout: number;
  total_pool: number;
  total_votes: number;
  already_collected: boolean;
  finalized_at: string;
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
  prompt_text: string;
  your_role: 'prompt' | 'copy';
  your_phrase: string | null;
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
  payout_claimed: boolean | null;
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

export interface PhrasesetContributor {
  player_id: string;
  username: string;
  pseudonym: string;
  is_you: boolean;
  phrase?: string | null;
}

export interface PhrasesetVoteDetail {
  vote_id: string;
  voter_id: string;
  voter_username: string;
  voter_pseudonym: string;
  voted_phrase: string;
  correct: boolean;
  voted_at: string;
}

export interface PhrasesetActivityEntry {
  activity_id: string;
  activity_type: string;
  created_at: string;
  player_id?: string | null;
  player_username?: string | null;
  metadata: Record<string, any>;
}

export interface PhrasesetDetails {
  phraseset_id: string;
  prompt_round_id: string;
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
  payout_claimed: boolean;
  activity: PhrasesetActivityEntry[];
  created_at: string;
  finalized_at: string | null;
}

export interface ClaimPrizeResponse {
  success: boolean;
  amount: number;
  new_balance: number;
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

export interface ApiError {
  detail: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  redis: string;
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
