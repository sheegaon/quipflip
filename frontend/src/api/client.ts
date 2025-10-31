import axios, { AxiosError, type AxiosRequestConfig } from 'axios';
import { getContextualErrorMessage, getActionErrorMessage } from '../utils/errorMessages';
import type {
  Player,
  CreatePlayerResponse,
  ActiveRound,
  PendingResultsResponse,
  DailyBonusResponse,
  RoundAvailability,
  StartPromptResponse,
  StartCopyResponse,
  StartVoteResponse,
  SubmitPhraseResponse,
  VoteResponse,
  PhrasesetResults,
  HealthResponse,
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
  AdminPlayerSummary,
  AdminDeletePlayerResponse,
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
} from './types';

// Base URL - configure based on environment
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Helper for dev logging
const isDev = import.meta.env.DEV;
const logApi = (
  method: string,
  endpoint: string,
  status: 'start' | 'success' | 'error',
  details?: any,
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
const extractErrorMessage = (error: any, action?: string): string => {
  // Use the new contextual error message system
  if (action) {
    return getActionErrorMessage(action, error);
  }
  
  const contextualError = getContextualErrorMessage(error);
  return contextualError.message;
};

const ACCESS_TOKEN_KEY = 'quipflip_access_token';
const ACCESS_TOKEN_EXPIRES_KEY = 'quipflip_access_token_expires_at';
const USERNAME_STORAGE_KEY = 'quipflip_username';

let accessToken: string | null = localStorage.getItem(ACCESS_TOKEN_KEY);
let accessTokenExpiresAt = Number(localStorage.getItem(ACCESS_TOKEN_EXPIRES_KEY) ?? '0');

// Create axios instance with credential support for refresh token cookie
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

const setAccessToken = (token: string | null, expiresInSeconds?: number) => {
  accessToken = token;
  if (token) {
    const buffer = 5 * 1000;
    const expiresAt = Date.now() + (expiresInSeconds ?? 0) * 1000 - buffer;
    accessTokenExpiresAt = expiresAt;
    localStorage.setItem(ACCESS_TOKEN_KEY, token);
    if (expiresInSeconds) {
      localStorage.setItem(ACCESS_TOKEN_EXPIRES_KEY, expiresAt.toString());
    }
  } else {
    accessTokenExpiresAt = 0;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(ACCESS_TOKEN_EXPIRES_KEY);
  }
};

const clearStoredCredentials = () => {
  setAccessToken(null);
  localStorage.removeItem(USERNAME_STORAGE_KEY);
};

const shouldAttemptRefresh = () => {
  // If we have an access token that hasn't expired yet, no need to refresh
  if (accessToken && accessTokenExpiresAt && Date.now() < accessTokenExpiresAt) {
    return false;
  }

  // Only attempt refresh if we have evidence of a previous login (stored username)
  // This prevents unnecessary refresh attempts on first visit
  const hasStoredUsername = localStorage.getItem(USERNAME_STORAGE_KEY);
  if (!hasStoredUsername) return false;

  return true;
};

let refreshPromise: Promise<string | null> | null = null;

// Refresh the access token, deduplicating concurrent refresh attempts
const performTokenRefresh = async (): Promise<string | null> => {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = api
    .post<AuthTokenResponse>(
      '/auth/refresh',
      { refresh_token: null },
      {
        skipAuth: true,
      },
    )
    .then((response) => {
      const token = response.data.access_token;
      setAccessToken(token, response.data.expires_in);
      return token;
    })
    .catch((error) => {
      clearStoredCredentials();
      throw error;
    })
    .finally(() => {
      refreshPromise = null;
    });

  return refreshPromise;
};

// Request interceptor to attach auth headers and log outgoing requests
api.interceptors.request.use((config) => {
  if (!config.skipAuth && accessToken) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${accessToken}`;
  }

  const method = config.method?.toUpperCase() || 'UNKNOWN';
  const endpoint = config.url || '';
  logApi(method, endpoint, 'start');

  return config;
});

// Response interceptor for success/error logging, auth refresh, and normalization
api.interceptors.response.use(
  (response) => {
    const method = response.config.method?.toUpperCase() || 'UNKNOWN';
    const endpoint = response.config.url || '';
    logApi(method, endpoint, 'success', response.data);

    return response;
  },
  async (error: AxiosError<ApiError>) => {
    if (error.config) {
      const method = error.config.method?.toUpperCase() || 'UNKNOWN';
      const endpoint = error.config.url || '';
      const errorMessage = error.response?.data?.detail || error.message;
      logApi(method, endpoint, 'error', errorMessage);
    }

    if (error.code === 'ERR_CANCELED') {
      return Promise.reject(error);
    }

    const originalRequest = error.config as (AxiosRequestConfig & { _retry?: boolean; skipAuth?: boolean }) | undefined;
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.skipAuth &&
      originalRequest.url !== '/auth/login' &&
      originalRequest.url !== '/auth/refresh' &&
      originalRequest.url !== '/auth/logout'
    ) {
      // Only attempt refresh if we have evidence of a previous login
      const hasStoredUsername = localStorage.getItem(USERNAME_STORAGE_KEY);
      if (hasStoredUsername) {
        originalRequest._retry = true;
        try {
          const token = await performTokenRefresh();
          if (token && originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return api(originalRequest);
        } catch (refreshError) {
          clearStoredCredentials();
          return Promise.reject(refreshError);
        }
      }
    }

    if (error.response) {
      const { status, data } = error.response;

      let errorPayload: any;
      if (data == null) {
        errorPayload = {};
      } else if (Array.isArray(data)) {
        errorPayload = { detail: data };
      } else if (typeof data === 'object') {
        errorPayload = { ...data };
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
      return Promise.reject({ message: 'The backend server may be busy. Please check your connection and try again.' });
    }

    return Promise.reject(error);
  },
);

export const apiClient = {
  setSession(username: string | null, tokenResponse?: AuthTokenResponse) {
    if (username) {
      localStorage.setItem(USERNAME_STORAGE_KEY, username);
    }
    if (tokenResponse) {
      setAccessToken(tokenResponse.access_token, tokenResponse.expires_in);
    }
  },

  clearSession() {
    clearStoredCredentials();
  },

  getStoredUsername(): string | null {
    return localStorage.getItem(USERNAME_STORAGE_KEY);
  },

  async ensureAccessToken(): Promise<string | null> {
    if (!shouldAttemptRefresh()) {
      return accessToken;
    }
    try {
      return await performTokenRefresh();
    } catch (err) {
      return null;
    }
  },

  // Health & Info
  async getHealth(signal?: AbortSignal): Promise<HealthResponse> {
    const { data } = await api.get('/health', { signal });
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
    const { data } = await api.post<CreateGuestResponse>('/player/guest', {}, {
      signal,
      skipAuth: true,
    });
    return data;
  },

  async upgradeGuest(
    payload: { email: string; password: string },
    signal?: AbortSignal,
  ): Promise<UpgradeGuestResponse> {
    const { data } = await api.post<UpgradeGuestResponse>('/player/upgrade', payload, { signal });
    if (data?.access_token) {
      setAccessToken(data.access_token, data.expires_in);
    }
    return data;
  },

  async login(
    payload: { email: string; password: string },
    signal?: AbortSignal,
  ): Promise<AuthTokenResponse> {
    const { data} = await api.post<AuthTokenResponse>('/auth/login', payload, {
      signal,
      skipAuth: true,
    });
    return data;
  },

  async suggestUsername(signal?: AbortSignal): Promise<SuggestUsernameResponse> {
    const { data } = await api.get<SuggestUsernameResponse>('/auth/suggest-username', {
      signal,
      skipAuth: true,
    });
    return data;
  },

  async refreshToken(signal?: AbortSignal): Promise<AuthTokenResponse> {
    const { data } = await api.post(
      '/auth/refresh',
      {},
      {
        signal,
        skipAuth: true,
      },
    );
    return data;
  },

  async logout(signal?: AbortSignal): Promise<void> {
    await api.post(
      '/auth/logout',
      {},
      {
        signal,
        skipAuth: true,
      },
    );
    clearStoredCredentials();
  },

  async changePassword(
    payload: { current_password: string; new_password: string },
    signal?: AbortSignal,
  ): Promise<ChangePasswordResponse> {
    const { data } = await api.post<ChangePasswordResponse>('/player/password', payload, { signal });
    if (data?.access_token) {
      setAccessToken(data.access_token, data.expires_in);
    }
    return data;
  },

  async updateEmail(
    payload: { new_email: string; password: string },
    signal?: AbortSignal,
  ): Promise<UpdateEmailResponse> {
    const { data } = await api.patch<UpdateEmailResponse>('/player/email', payload, { signal });
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

  async startPromptRound(signal?: AbortSignal): Promise<StartPromptResponse> {
    const { data } = await api.post('/rounds/prompt', {}, { signal });
    return data;
  },

  async startCopyRound(signal?: AbortSignal): Promise<StartCopyResponse> {
    const { data } = await api.post('/rounds/copy', {}, { signal });
    return data;
  },

  async startVoteRound(signal?: AbortSignal): Promise<StartVoteResponse> {
    const { data } = await api.post('/rounds/vote', {}, { signal });
    return data;
  },

  async submitPhrase(roundId: string, phrase: string, signal?: AbortSignal): Promise<SubmitPhraseResponse> {
    const { data } = await api.post(`/rounds/${roundId}/submit`, { phrase }, { signal });
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

  async claimPhrasesetPrize(phrasesetId: string, signal?: AbortSignal): Promise<ClaimPrizeResponse> {
    const { data } = await api.post(`/phrasesets/${phrasesetId}/claim`, {}, { signal });
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

  // Admin endpoints
  async validateAdminPassword(password: string, signal?: AbortSignal): Promise<{ valid: boolean }> {
    const { data } = await api.post('/admin/validate-password', { password }, { signal });
    return data;
  },

  async getAdminConfig(signal?: AbortSignal): Promise<any> {
    const { data } = await api.get('/admin/config', { signal });
    return data;
  },

  async updateAdminConfig(key: string, value: any, signal?: AbortSignal): Promise<{ success: boolean; key: string; value: any; message?: string }> {
    const { data } = await api.patch('/admin/config', { key, value }, { signal });
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
};

export default apiClient;

export { extractErrorMessage, clearStoredCredentials };
