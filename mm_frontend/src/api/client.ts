import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { getContextualErrorMessage, getActionErrorMessage } from '../utils/errorMessages';
import { offlineQueue, shouldQueueAction } from '../utils/offlineQueue';
import { USERNAME_STORAGE_KEY } from '../utils/storageKeys';
import type {
  Player,
  CreatePlayerResponse,
  ActiveRound,
  PendingResultsResponse,
  DailyBonusResponse,
  RoundAvailability,
  RoundDetails,
  StartPromptResponse,
  StartCopyResponse,
  StartVoteResponse,
  SubmitPhraseResponse,
  HintResponse,
  VoteResponse,
  PhrasesetResults,
  HealthResponse,
  ApiInfo,
  GameStatus,
  ApiError,
  AuthTokenResponse,
  SuggestUsernameResponse,
  PromptFeedbackResponse,
  GetPromptFeedbackResponse,
  PhrasesetListResponse,
  PhrasesetDashboardSummary,
  PhrasesetDetails,
  ClaimPrizeResponse,
  UnclaimedResultsResponse,
  PlayerStatistics,
  TutorialStatus,
  TutorialProgress,
  UpdateTutorialProgressResponse,
  Quest,
  QuestListResponse,
  ClaimQuestRewardResponse,
  DashboardData,
  ChangePasswordResponse,
  UpdateEmailResponse,
  ChangeUsernameResponse,
  AdminPlayerSummary,
  AdminDeletePlayerResponse,
  AdminResetPasswordResponse,
  CreateGuestResponse,
  UpgradeGuestResponse,
  FlagCopyRoundResponse,
  AbandonRoundResponse,
  FlaggedPromptListResponse,
  FlaggedPromptItem,
  BetaSurveySubmissionRequest,
  BetaSurveySubmissionResponse,
  BetaSurveyStatusResponse,
  BetaSurveyListResponse,
  LeaderboardResponse,
  CompletedPhrasesetsResponse,
  PracticePhraseset,
  AdminConfig,
  UpdateAdminConfigResponse,
  OnlineUsersResponse,
  PingUserResponse,
  WsAuthTokenResponse,
  CreatePartySessionRequest,
  CreatePartySessionResponse,
  JoinPartySessionResponse,
  MarkReadyResponse,
  StartPartySessionResponse,
  PartySessionStatusResponse,
  StartPartyPromptResponse,
  StartPartyCopyResponse,
  StartPartyVoteResponse,
  SubmitPartyRoundResponse,
  PartyResultsResponse,
  PartyListResponse,
  PartyPingResponse,
  MemeVoteRound,
  MemeVoteResult,
  MemeCaptionSubmission,
  MemeCaptionResponse,
} from './types';

// Base URL - configure based on environment
const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE_URL = /\/qf($|\/)/.test(baseUrl) ? baseUrl : `${baseUrl}/qf`;

// Helper for dev logging
const isDev = import.meta.env.DEV;
const logApi = (
  method: string,
  endpoint: string,
  status: 'start' | 'success' | 'error',
  details?: unknown,
) => {
  if (!isDev) return;
  const emoji = status === 'start' ? '📤' : status === 'success' ? '✅' : '❌';
  const message = `${emoji} API [${method.toUpperCase()} ${endpoint}]`;
  if (details) {
    console.log(message, details);
  } else {
    console.log(message);
  }
};

// Helper function to extract meaningful error messages using enhanced localization
const extractErrorMessage = (error: unknown, action?: string): string => {
  // Use the new contextual error message system
  if (action) {
    return getActionErrorMessage(action, error);
  }

  const contextualError = getContextualErrorMessage(error);
  return contextualError.message;
};

// Create axios instance with credential support for cookies
// withCredentials: true enables sending/receiving HTTP-only cookies
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
  timeout: 150000, // 150 seconds (2.5 minutes) timeout for hint generation
});

// Export axios instance for direct use (e.g., replaying queued requests)
export const axiosInstance = api;

const clearStoredCredentials = () => {
  localStorage.removeItem(USERNAME_STORAGE_KEY);
};

// Track if we're currently refreshing to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (error?: unknown) => void;
}> = [];

const processQueue = (error: unknown = null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else {
      promise.resolve();
    }
  });
  failedQueue = [];
};

const performTokenRefresh = async (): Promise<void> => {
  try {
    // Call refresh endpoint - cookies are sent/received automatically
    await api.post('/auth/refresh', {});
    logApi('POST', '/auth/refresh', 'success', 'Token refreshed via cookie');
  } catch (error) {
    logApi('POST', '/auth/refresh', 'error', 'Token refresh failed');
    clearStoredCredentials();
    throw error;
  }
};

// Request interceptor for logging outgoing requests
api.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase() || 'UNKNOWN';
  const endpoint = config.url || '';
  logApi(method, endpoint, 'start');

  return config;
});

// Response interceptor for success/error logging, automatic token refresh, and normalization
api.interceptors.response.use(
  (response) => {
    const method = response.config.method?.toUpperCase() || 'UNKNOWN';
    const endpoint = response.config.url || '';
    logApi(method, endpoint, 'success', response.data);

    return response;
  },
  async (error: AxiosError<ApiError>) => {
    // Extend config type to include our custom _retry flag
    interface RetryableConfig extends InternalAxiosRequestConfig {
      _retry?: boolean;
    }
    const originalRequest = error.config as RetryableConfig | undefined;

    // Don't log or process canceled requests - they're intentional (e.g., component unmount, StrictMode double mount)
    const isCanceled =
      error.code === 'ERR_CANCELED' ||
      error.name === 'CanceledError' ||
      error.message === 'canceled' ||
      error.message?.includes('cancel');

    if (isCanceled) {
      return Promise.reject(error);
    }

    if (error.config) {
      const method = error.config.method?.toUpperCase() || 'UNKNOWN';
      const endpoint = error.config.url || '';
      const errorMessage = error.response?.data?.detail || error.message;

      // Don't log 401 errors for endpoints where it's expected (session detection, beta-survey)
      const is401OnSurveyStatus = error.response?.status === 401 && endpoint === '/feedback/beta-survey/status';
      const is401OnBalance = error.response?.status === 401 && endpoint === '/player/balance';

      if (!is401OnSurveyStatus && !is401OnBalance) {
        logApi(method, endpoint, 'error', errorMessage);
      }
    }

    // Handle 401 errors with automatic token refresh
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      originalRequest.url !== '/auth/login' &&
      originalRequest.url !== '/auth/refresh' &&
      originalRequest.url !== '/auth/logout'
    ) {
      // Only attempt refresh if we have evidence of a previous login
      const hasStoredUsername = localStorage.getItem(USERNAME_STORAGE_KEY);

      if (hasStoredUsername) {
        if (isRefreshing) {
          // Queue the request while refresh is in progress
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          })
            .then(() => api(originalRequest))
            .catch((err) => Promise.reject(err));
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
          await performTokenRefresh();
          processQueue(null);
          return api(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError);
          clearStoredCredentials();
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }
    }

    // Error normalization and user-friendly messages
    if (error.response) {
      const { status, data } = error.response;

      let errorPayload: Record<string, unknown>;
      if (data == null) {
        errorPayload = {};
      } else if (Array.isArray(data)) {
        errorPayload = { detail: data };
      } else if (typeof data === 'object') {
        errorPayload = { ...(data as unknown as Record<string, unknown>) };
      } else {
        errorPayload = { detail: String(data) };
      }

      if (status === 401) {
        errorPayload.detail = errorPayload.detail || 'Unauthorized. Please login again.';
      } else if (status === 429) {
        errorPayload.detail = errorPayload.detail || 'Rate limit exceeded. Please try again later.';
      }

      errorPayload.status = status;
      return Promise.reject(errorPayload);
    }

    if (error.code === 'ERR_NETWORK') {
      // Check if we're offline and should queue this request
      const isOffline = typeof navigator !== 'undefined' && !navigator.onLine;

      if (isOffline && originalRequest && shouldQueueAction(originalRequest.method || 'GET', originalRequest.url || '')) {
        // Queue the request for later when we're back online
        const actionId = offlineQueue.addAction({
          type: 'api_call',
          method: originalRequest.method || 'GET',
          url: originalRequest.url || '',
          data: originalRequest.data,
          headers: originalRequest.headers,
          maxRetries: 3,
        });

        logApi(
          originalRequest.method?.toUpperCase() || 'UNKNOWN',
          originalRequest.url || '',
          'error',
          `Queued for offline sync (ID: ${actionId})`
        );

        // Return a specific offline error
        return Promise.reject({
          message: 'You are offline. This action will be synced when connection is restored.',
          isOfflineError: true,
          actionId,
        });
      }

      // Not offline or shouldn't queue - return network error
      return Promise.reject({
        message: 'The backend server may be busy. Please check your connection and try again.',
        isNetworkError: true,
      });
    }

    return Promise.reject(error);
  },
);

export const apiClient = {
  setSession(username: string | null) {
    if (username) {
      localStorage.setItem(USERNAME_STORAGE_KEY, username);
    }
  },

  clearSession() {
    clearStoredCredentials();
  },

  getStoredUsername(): string | null {
    return localStorage.getItem(USERNAME_STORAGE_KEY);
  },

  // Health & Info
  async getHealth(signal?: AbortSignal): Promise<HealthResponse> {
    const { data } = await api.get('/health', { signal });
    return data;
  },

  async getApiInfo(signal?: AbortSignal): Promise<ApiInfo> {
    const { data } = await api.get<ApiInfo>('/', { signal, skipAuth: true });
    return data;
  },

  async getGameStatus(signal?: AbortSignal): Promise<GameStatus> {
    const { data } = await api.get<GameStatus>('/status', { signal, skipAuth: true });
    return data;
  },

  // Player endpoints
  async createPlayer(
    payload: { email: string; password: string },
    signal?: AbortSignal,
  ): Promise<CreatePlayerResponse> {
    const { data } = await api.post('/player', payload, { signal });
    return data;
  },

  async createGuest(signal?: AbortSignal): Promise<CreateGuestResponse> {
    const { data } = await api.post<CreateGuestResponse>('/player/guest', {}, { signal });
    return data;
  },

  async upgradeGuest(
    payload: { email: string; password: string },
    signal?: AbortSignal,
  ): Promise<UpgradeGuestResponse> {
    const { data } = await api.post<UpgradeGuestResponse>('/player/upgrade', payload, { signal });
    return data;
  },

  async login(
    payload: { email: string; password: string },
    signal?: AbortSignal,
  ): Promise<AuthTokenResponse> {
    const { data } = await api.post<AuthTokenResponse>('/auth/login', payload, { signal });
    return data;
  },

  async loginWithUsername(
    payload: { username: string; password: string },
    signal?: AbortSignal,
  ): Promise<AuthTokenResponse> {
    const { data } = await api.post<AuthTokenResponse>('/auth/login/username', payload, { signal });
    return data;
  },

  async suggestUsername(signal?: AbortSignal): Promise<SuggestUsernameResponse> {
    const { data } = await api.get<SuggestUsernameResponse>('/auth/suggest-username', { signal });
    return data;
  },

  async refreshToken(signal?: AbortSignal): Promise<AuthTokenResponse> {
    const { data } = await api.post('/auth/refresh', {}, { signal });
    return data;
  },

  async logout(signal?: AbortSignal): Promise<void> {
    await api.post('/auth/logout', {}, { signal });
    clearStoredCredentials();
  },

  async getWebsocketToken(signal?: AbortSignal): Promise<WsAuthTokenResponse> {
    const { data } = await api.get<WsAuthTokenResponse>('/auth/ws-token', { signal });
    return data;
  },

  async changePassword(
    payload: { current_password: string; new_password: string },
    signal?: AbortSignal,
  ): Promise<ChangePasswordResponse> {
    const { data } = await api.post<ChangePasswordResponse>('/player/password', payload, { signal });
    return data;
  },

  async updateEmail(
    payload: { new_email: string; password: string },
    signal?: AbortSignal,
  ): Promise<UpdateEmailResponse> {
    const { data } = await api.patch<UpdateEmailResponse>('/player/email', payload, { signal });
    return data;
  },

  async changeUsername(
    payload: { new_username: string; password: string },
    signal?: AbortSignal,
  ): Promise<ChangeUsernameResponse> {
    const { data } = await api.patch<ChangeUsernameResponse>('/player/username', payload, { signal });
    return data;
  },

  async deleteAccount(
    payload: { password: string; confirmation: string },
    signal?: AbortSignal,
  ): Promise<void> {
    await api.delete('/player/account', { data: payload, signal });
    clearStoredCredentials();
  },

  async getBalance(signal?: AbortSignal): Promise<Player> {
    const { data } = await api.get('/player/balance', { signal });
    return data;
  },

  async claimDailyBonus(signal?: AbortSignal): Promise<DailyBonusResponse> {
    const { data } = await api.post('/player/claim-daily-bonus', {}, { signal });
    return data;
  },

  async getCurrentRound(signal?: AbortSignal): Promise<ActiveRound> {
    const { data } = await api.get('/player/current-round', { signal });
    return data;
  },

  async getPendingResults(signal?: AbortSignal): Promise<PendingResultsResponse> {
    const { data } = await api.get('/player/pending-results', { signal });
    return data;
  },

  async getPlayerPhrasesets(
    params: { role?: string; status?: string; limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<PhrasesetListResponse> {
    const { data } = await api.get('/player/phrasesets', {
      params,
      signal,
    });
    return data;
  },

  async getPhrasesetsSummary(signal?: AbortSignal): Promise<PhrasesetDashboardSummary> {
    const { data } = await api.get('/player/phrasesets/summary', { signal });
    return data;
  },

  async getUnclaimedResults(signal?: AbortSignal): Promise<UnclaimedResultsResponse> {
    const { data } = await api.get('/player/unclaimed-results', { signal });
    return data;
  },

  async getDashboardData(signal?: AbortSignal): Promise<DashboardData> {
    const { data } = await api.get('/player/dashboard', { signal });
    return data;
  },

  // Round endpoints
  async getRoundAvailability(signal?: AbortSignal): Promise<RoundAvailability> {
    const { data } = await api.get('/rounds/available', { signal });
    return data;
  },

  async getRoundDetails(roundId: string, signal?: AbortSignal): Promise<RoundDetails> {
    const { data } = await api.get(`/rounds/${roundId}`, { signal });
    return data;
  },

  async startPromptRound(signal?: AbortSignal): Promise<StartPromptResponse> {
    const { data } = await api.post('/rounds/prompt', {}, { signal });
    return data;
  },

  async startCopyRound(promptRoundId?: string, signal?: AbortSignal): Promise<StartCopyResponse> {
    const params = promptRoundId ? { prompt_round_id: promptRoundId } : {};
    const { data } = await api.post('/rounds/copy', {}, { signal, params });
    return data;
  },

  async startVoteRound(signal?: AbortSignal): Promise<StartVoteResponse> {
    const { data } = await api.post('/rounds/vote', {}, { signal });
    return data;
  },

  // MemeMint endpoints
  async startMemeVoteRound(signal?: AbortSignal): Promise<MemeVoteRound> {
    const { data } = await api.post('/mm/rounds/vote', {}, { signal });
    return data;
  },

  async submitMemeVote(roundId: string, captionId: string, signal?: AbortSignal): Promise<MemeVoteResult> {
    const { data } = await api.post(`/mm/rounds/vote/${roundId}`, { caption_id: captionId }, { signal });
    return data;
  },

  async submitMemeCaption(request: MemeCaptionSubmission, signal?: AbortSignal): Promise<MemeCaptionResponse> {
    const { data } = await api.post('/mm/rounds/caption', request, { signal });
    return data;
  },

  async submitPhrase(roundId: string, phrase: string, signal?: AbortSignal): Promise<SubmitPhraseResponse> {
    const { data } = await api.post(`/rounds/${roundId}/submit`, { phrase }, { signal });
    return data;
  },

  async getCopyHints(roundId: string, signal?: AbortSignal): Promise<HintResponse> {
    const { data } = await api.get(`/rounds/${roundId}/hints`, { signal });
    return data;
  },

  async flagCopyRound(roundId: string, signal?: AbortSignal): Promise<FlagCopyRoundResponse> {
    const { data } = await api.post(`/rounds/${roundId}/flag`, {}, { signal });
    return data;
  },

  async abandonRound(roundId: string, signal?: AbortSignal): Promise<AbandonRoundResponse> {
    const { data } = await api.post(`/rounds/${roundId}/abandon`, {}, { signal });
    return data;
  },

  // Phraseset endpoints
  async submitVote(phrasesetId: string, phrase: string, signal?: AbortSignal): Promise<VoteResponse> {
    const { data } = await api.post(`/phrasesets/${phrasesetId}/vote`, { phrase }, { signal });
    return data;
  },

  async getPhrasesetResults(phrasesetId: string, signal?: AbortSignal): Promise<PhrasesetResults> {
    const { data } = await api.get(`/phrasesets/${phrasesetId}/results`, { signal });
    return data;
  },

  async getPhrasesetDetails(phrasesetId: string, signal?: AbortSignal): Promise<PhrasesetDetails> {
    const { data } = await api.get(`/phrasesets/${phrasesetId}/details`, { signal });
    return data;
  },

  async getPublicPhrasesetDetails(phrasesetId: string, signal?: AbortSignal): Promise<PhrasesetDetails> {
    const { data } = await api.get(`/phrasesets/${phrasesetId}/public-details`, { signal });
    return data;
  },

  async claimPhrasesetPrize(phrasesetId: string, signal?: AbortSignal): Promise<ClaimPrizeResponse> {
    const { data } = await api.post(`/phrasesets/${phrasesetId}/claim`, {}, { signal });
    return data;
  },

  async getCompletedPhrasesets(
    params: { limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<CompletedPhrasesetsResponse> {
    const { data } = await api.get('/phrasesets/completed', {
      params,
      signal,
    });
    return data;
  },

  async getRandomPracticePhraseset(signal?: AbortSignal): Promise<PracticePhraseset> {
    const { data } = await api.get('/phrasesets/practice/random', { signal });
    return data;
  },

  // Prompt feedback endpoints
  async submitPromptFeedback(
    roundId: string,
    feedbackType: 'like' | 'dislike',
    signal?: AbortSignal,
  ): Promise<PromptFeedbackResponse> {
    const { data } = await api.post(
      `/rounds/${roundId}/feedback`,
      { feedback_type: feedbackType },
      { signal },
    );
    return data;
  },

  async getPromptFeedback(roundId: string, signal?: AbortSignal): Promise<GetPromptFeedbackResponse> {
    const { data } = await api.get(`/rounds/${roundId}/feedback`, { signal });
    return data;
  },

  async getStatistics(signal?: AbortSignal): Promise<PlayerStatistics> {
    const { data } = await api.get('/player/statistics', { signal });
    return data;
  },

  async getWeeklyLeaderboard(signal?: AbortSignal): Promise<LeaderboardResponse> {
    const { data } = await api.get('/player/statistics/weekly-leaderboard', { signal });
    return data;
  },

  async getAllTimeLeaderboard(signal?: AbortSignal): Promise<LeaderboardResponse> {
    const { data } = await api.get('/player/statistics/alltime-leaderboard', { signal });
    return data;
  },

  async getTutorialStatus(signal?: AbortSignal): Promise<TutorialStatus> {
    const { data } = await api.get('/player/tutorial/status', { signal });
    return data;
  },

  async updateTutorialProgress(progress: TutorialProgress, signal?: AbortSignal): Promise<UpdateTutorialProgressResponse> {
    const { data } = await api.post('/player/tutorial/progress', { progress }, { signal });
    return data;
  },

  async resetTutorial(signal?: AbortSignal): Promise<TutorialStatus> {
    const { data } = await api.post('/player/tutorial/reset', {}, { signal });
    return data;
  },

  async submitBetaSurvey(
    payload: BetaSurveySubmissionRequest,
    signal?: AbortSignal,
  ): Promise<BetaSurveySubmissionResponse> {
    const { data } = await api.post<BetaSurveySubmissionResponse>('/feedback/beta-survey', payload, { signal });
    return data;
  },

  async getBetaSurveyStatus(signal?: AbortSignal): Promise<BetaSurveyStatusResponse> {
    logApi('get', '/feedback/beta-survey/status', 'start');
    try {
      const { data } = await api.get<BetaSurveyStatusResponse>('/feedback/beta-survey/status', { signal });
      logApi('get', '/feedback/beta-survey/status', 'success', data);
      return data;
    } catch (error) {
      logApi('get', '/feedback/beta-survey/status', 'error', error);
      throw error;
    }
  },

  async listBetaSurveyResponses(signal?: AbortSignal): Promise<BetaSurveyListResponse> {
    const { data } = await api.get<BetaSurveyListResponse>('/feedback/beta-survey', { signal });
    return data;
  },

  // Quest endpoints
  async getQuests(signal?: AbortSignal): Promise<QuestListResponse> {
    const { data } = await api.get('/quests', { signal });
    return data;
  },

  async getActiveQuests(signal?: AbortSignal): Promise<Quest[]> {
    const { data } = await api.get('/quests/active', { signal });
    return data;
  },

  async getClaimableQuests(signal?: AbortSignal): Promise<Quest[]> {
    const { data } = await api.get('/quests/claimable', { signal });
    return data;
  },

  async getQuest(questId: string, signal?: AbortSignal): Promise<Quest> {
    const { data } = await api.get(`/quests/${questId}`, { signal });
    return data;
  },

  async claimQuestReward(questId: string, signal?: AbortSignal): Promise<ClaimQuestRewardResponse> {
    const { data } = await api.post(`/quests/${questId}/claim`, {}, { signal });
    return data;
  },

  async getOnlineUsers(signal?: AbortSignal): Promise<OnlineUsersResponse> {
    const { data } = await api.get<OnlineUsersResponse>('/users/online', { signal });
    return data;
  },

  async pingOnlineUser(username: string, signal?: AbortSignal): Promise<PingUserResponse> {
    const { data } = await api.post<PingUserResponse>(
      '/users/online/ping',
      { username },
      { signal },
    );
    return data;
  },

  // Admin endpoints
  async getAdminConfig(signal?: AbortSignal): Promise<AdminConfig> {
    const { data } = await api.get<AdminConfig>('/admin/config', { signal });
    return data;
  },

  async updateAdminConfig(key: string, value: number | string, signal?: AbortSignal): Promise<UpdateAdminConfigResponse> {
    const { data } = await api.patch<UpdateAdminConfigResponse>('/admin/config', { key, value }, { signal });
    return data;
  },

  async adminSearchPlayer(
    params: { email?: string; username?: string },
    signal?: AbortSignal,
  ): Promise<AdminPlayerSummary> {
    const { data } = await api.get('/admin/players/search', { params, signal });
    return data;
  },

  async adminDeletePlayer(
    payload: { player_id?: string; email?: string; username?: string; confirmation: 'DELETE' },
    signal?: AbortSignal,
  ): Promise<AdminDeletePlayerResponse> {
    const { data } = await api.delete('/admin/players', {
      data: payload,
      signal,
    });
    return data;
  },

  async adminResetPassword(
    payload: { player_id?: string; email?: string; username?: string },
    signal?: AbortSignal,
  ): Promise<AdminResetPasswordResponse> {
    const { data } = await api.post('/admin/players/reset-password', payload, { signal });
    return data;
  },

  async getFlaggedPrompts(
    status: 'pending' | 'confirmed' | 'dismissed' | 'all' = 'pending',
    signal?: AbortSignal,
  ): Promise<FlaggedPromptListResponse> {
    const queryStatus = status === 'all' ? undefined : status;
    const { data } = await api.get('/admin/flags', {
      params: queryStatus ? { status: queryStatus } : undefined,
      signal,
    });
    return data;
  },

  async resolveFlaggedPrompt(
    flagId: string,
    action: 'confirm' | 'dismiss',
    signal?: AbortSignal,
  ): Promise<FlaggedPromptItem> {
    const { data } = await api.post(`/admin/flags/${flagId}/resolve`, { action }, { signal });
    return data;
  },

  async testPhraseValidation(
    phrase: string,
    validationType: 'basic' | 'prompt' | 'copy',
    promptText?: string | null,
    originalPhrase?: string | null,
    otherCopyPhrase?: string | null,
    signal?: AbortSignal
  ): Promise<{
    is_valid: boolean;
    error_message: string | null;
    word_count: number;
    phrase_length: number;
    words: string[];
    prompt_relevance_score: number | null;
    similarity_to_original: number | null;
    similarity_to_other_copy: number | null;
    prompt_relevance_threshold: number | null;
    similarity_threshold: number | null;
    format_check_passed: boolean;
    dictionary_check_passed: boolean;
    word_conflicts: string[];
  }> {
    const { data } = await api.post('/admin/test-phrase-validation', {
      phrase,
      validation_type: validationType,
      prompt_text: promptText,
      original_phrase: originalPhrase,
      other_copy_phrase: otherCopyPhrase,
    }, { signal });
    return data;
  },

  // Party Mode endpoints
  async createPartySession(
    request: CreatePartySessionRequest = {},
    signal?: AbortSignal,
  ): Promise<CreatePartySessionResponse> {
    try {
      const { data } = await api.post<CreatePartySessionResponse>('/party/create', request, { 
        signal,
        timeout: 10000 // 10 second timeout for party creation
      });
      return data;
    } catch (error) {
      // Type the error as AxiosError or unknown for proper error handling
      const axiosError = error as AxiosError<ApiError>;
      
      // Add more detailed error logging for party creation
      if (axiosError?.response?.status === 500) {
        console.error('Party creation failed with server error:', {
          status: axiosError.response.status,
          statusText: axiosError.response.statusText,
          data: axiosError.response.data,
          message: axiosError.message
        });
        
        // For 500 errors, provide a user-friendly message
        throw {
          ...axiosError,
          message: 'Server error creating party. Please try again in a moment.',
          isServerError: true
        };
      }
      
      console.error('Party creation failed:', {
        status: axiosError?.response?.status,
        statusText: axiosError?.response?.statusText,
        data: axiosError?.response?.data,
        message: axiosError?.message
      });
      
      throw error;
    }
  },

  async listActiveParties(
    signal?: AbortSignal,
  ): Promise<PartyListResponse> {
    const { data } = await api.get<PartyListResponse>('/party/list', { signal });
    return data;
  },

  async joinPartySessionById(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<JoinPartySessionResponse> {
    const { data } = await api.post<JoinPartySessionResponse>(`/party/${sessionId}/join`, {}, { signal });
    return data;
  },

  async joinPartySession(
    partyCode: string,
    signal?: AbortSignal,
  ): Promise<JoinPartySessionResponse> {
    const { data } = await api.post<JoinPartySessionResponse>('/party/join', { party_code: partyCode }, { signal });
    return data;
  },

  async markPartyReady(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<MarkReadyResponse> {
    const { data } = await api.post<MarkReadyResponse>(`/party/${sessionId}/ready`, {}, { signal });
    return data;
  },

  async addAIPlayerToParty(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<{ participant_id: string; player_id: string; username: string; is_ai: boolean }> {
    const { data } = await api.post<{ participant_id: string; player_id: string; username: string; is_ai: boolean }>(`/party/${sessionId}/add-ai`, {}, { signal });
    return data;
  },

  async startPartySession(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<StartPartySessionResponse> {
    const { data } = await api.post<StartPartySessionResponse>(`/party/${sessionId}/start`, {}, { signal });
    return data;
  },

  async getPartySessionStatus(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<PartySessionStatusResponse> {
    const { data } = await api.get<PartySessionStatusResponse>(`/party/${sessionId}/status`, { signal });
    return data;
  },

  async leavePartySession(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<{ success: boolean; message: string }> {
    const { data } = await api.post<{ success: boolean; message: string }>(`/party/${sessionId}/leave`, {}, { signal });
    return data;
  },

  async startPartyPromptRound(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<StartPartyPromptResponse> {
    const { data } = await api.post<StartPartyPromptResponse>(
      `/party/${sessionId}/rounds/prompt`,
      {},
      { signal }
    );
    return data;
  },

  async startPartyCopyRound(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<StartPartyCopyResponse> {
    const { data } = await api.post<StartPartyCopyResponse>(
      `/party/${sessionId}/rounds/copy`,
      {},
      { signal }
    );
    return data;
  },

  async startPartyVoteRound(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<StartPartyVoteResponse> {
    const { data } = await api.post<StartPartyVoteResponse>(
      `/party/${sessionId}/rounds/vote`,
      {},
      { signal }
    );
    return data;
  },

  async submitPartyRound(
    sessionId: string,
    roundId: string,
    payload: { phrase?: string; vote?: string },
    signal?: AbortSignal,
  ): Promise<SubmitPartyRoundResponse> {
    const { data } = await api.post<SubmitPartyRoundResponse>(`/party/${sessionId}/rounds/${roundId}/submit`, payload, { signal });
    return data;
  },

  async getPartyResults(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<PartyResultsResponse> {
    const { data } = await api.get<PartyResultsResponse>(`/party/${sessionId}/results`, { signal });
    return data;
  },

  async pingParty(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<PartyPingResponse> {
    const { data } = await api.post<PartyPingResponse>(`/party/${sessionId}/ping`, {}, { signal });
    return data;
  },
};

export default apiClient;

export { extractErrorMessage, clearStoredCredentials };
