import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import { getContextualErrorMessage, getActionErrorMessage } from '../utils/errorMessages.ts';
import { offlineQueue, shouldQueueAction } from '../utils/offlineQueue.ts';
import { USERNAME_STORAGE_KEY } from '../utils/storageKeys.ts';
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
  FlagCopyRoundResponse,
  AbandonRoundResponse,
  FlaggedPromptListResponse,
  FlaggedPromptItem,
  CreateGuestResponse,
  UpgradeGuestResponse,
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
} from './types.ts';

export const extractErrorMessage = (error: unknown, action?: string): string => {
  if (action) {
    return getActionErrorMessage(action, error);
  }

  const contextualError = getContextualErrorMessage(error);
  return contextualError.message;
};

export const clearStoredCredentials = (): void => {
  localStorage.removeItem(USERNAME_STORAGE_KEY);
};

export class BaseApiClient {
  protected api: AxiosInstance;
  protected isRefreshing = false;
  protected failedQueue: Array<{ resolve: (value?: unknown) => void; reject: (error?: unknown) => void }> = [];
  protected readonly isDev = import.meta.env.DEV;

  constructor(baseURL: string) {
    this.api = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true,
      timeout: 150000,
    });

    this.attachInterceptors();
  }

  public get axiosInstance(): AxiosInstance {
    return this.api;
  }

  protected logApi(
    method: string,
    endpoint: string,
    status: 'start' | 'success' | 'error',
    details?: unknown,
  ) {
    if (!this.isDev) return;
    const emoji = status === 'start' ? '📤' : status === 'success' ? '✅' : '❌';
    const message = `${emoji} API [${method.toUpperCase()} ${endpoint}]`;
    // eslint-disable-next-line no-console
    if (details) {
      console.log(message, details);
    } else {
      console.log(message);
    }
  }

  protected processQueue(error: unknown = null) {
    this.failedQueue.forEach((promise) => {
      if (error) {
        promise.reject(error);
      } else {
        promise.resolve();
      }
    });
    this.failedQueue = [];
  }

  protected async performTokenRefresh() {
    try {
      await this.api.post('/auth/refresh', {});
      this.logApi('POST', '/auth/refresh', 'success', 'Token refreshed via cookie');
    } catch (error) {
      this.logApi('POST', '/auth/refresh', 'error', 'Token refresh failed');
      clearStoredCredentials();
      throw error;
    }
  }

  protected attachInterceptors() {
    this.api.interceptors.request.use((config) => {
      const method = config.method?.toUpperCase() || 'UNKNOWN';
      const endpoint = config.url || '';
      this.logApi(method, endpoint, 'start');

      return config;
    });

    this.api.interceptors.response.use(
      (response) => {
        const method = response.config.method?.toUpperCase() || 'UNKNOWN';
        const endpoint = response.config.url || '';
        this.logApi(method, endpoint, 'success', response.data);

        return response;
      },
      async (error: AxiosError<ApiError>) => {
        interface RetryableConfig extends InternalAxiosRequestConfig {
          _retry?: boolean;
        }
        const originalRequest = error.config as RetryableConfig | undefined;

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

          const is401OnSurveyStatus = error.response?.status === 401 && endpoint === '/feedback/beta-survey/status';
          const is401OnBalance = error.response?.status === 401 && endpoint === '/player/balance';

          if (!is401OnSurveyStatus && !is401OnBalance) {
            this.logApi(method, endpoint, 'error', errorMessage);
          }
        }

        if (
          error.response?.status === 401 &&
          originalRequest &&
          !originalRequest._retry &&
          originalRequest.url !== '/auth/login' &&
          originalRequest.url !== '/auth/refresh' &&
          originalRequest.url !== '/auth/logout'
        ) {
          const hasStoredUsername = localStorage.getItem(USERNAME_STORAGE_KEY);

          if (hasStoredUsername) {
            if (this.isRefreshing) {
              return new Promise((resolve, reject) => {
                this.failedQueue.push({ resolve, reject });
              })
                .then(() => this.api(originalRequest))
                .catch((err) => Promise.reject(err));
            }

            originalRequest._retry = true;
            this.isRefreshing = true;

            try {
              await this.performTokenRefresh();
              this.processQueue(null);
              return this.api(originalRequest);
            } catch (refreshError) {
              this.processQueue(refreshError);
              clearStoredCredentials();
              return Promise.reject(refreshError);
            } finally {
              this.isRefreshing = false;
            }
          }
        }

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
          const isOffline = typeof navigator !== 'undefined' && !navigator.onLine;

          if (isOffline && originalRequest && shouldQueueAction(originalRequest.method || 'GET', originalRequest.url || '')) {
            const actionId = offlineQueue.addAction({
              type: 'api_call',
              method: originalRequest.method || 'GET',
              url: originalRequest.url || '',
              data: originalRequest.data,
              headers: originalRequest.headers,
              maxRetries: 3,
            });

            this.logApi(
              originalRequest.method?.toUpperCase() || 'UNKNOWN',
              originalRequest.url || '',
              'error',
              `Queued for offline sync (ID: ${actionId})`,
            );

            return Promise.reject({
              message: 'You are offline. This action will be synced when connection is restored.',
              isOfflineError: true,
              actionId,
            });
          }

          return Promise.reject({
            message: 'The backend server may be busy. Please check your connection and try again.',
            isNetworkError: true,
          });
        }

        return Promise.reject(error);
      },
    );
  }

  setSession(username: string | null) {
    if (username) {
      localStorage.setItem(USERNAME_STORAGE_KEY, username);
    }
  }

  clearSession() {
    clearStoredCredentials();
  }

  getStoredUsername(): string | null {
    return localStorage.getItem(USERNAME_STORAGE_KEY);
  }

  async getHealth(signal?: AbortSignal): Promise<HealthResponse> {
    const { data } = await this.api.get('/health', { signal });
    return data;
  }

  async getApiInfo(signal?: AbortSignal): Promise<ApiInfo> {
    const { data } = await this.api.get<ApiInfo>('/', { signal });
    return data;
  }

  async getGameStatus(signal?: AbortSignal): Promise<GameStatus> {
    const { data } = await this.api.get<GameStatus>('/status', { signal });
    return data;
  }

  async createPlayer(payload: { email: string; password: string }, signal?: AbortSignal): Promise<CreatePlayerResponse> {
    const { data } = await this.api.post('/player', payload, { signal });
    return data;
  }

  async createGuest(signal?: AbortSignal): Promise<CreateGuestResponse> {
    const { data } = await this.api.post<CreateGuestResponse>('/player/guest', {}, { signal });
    return data;
  }

  async upgradeGuest(payload: { email: string; password: string }, signal?: AbortSignal): Promise<UpgradeGuestResponse> {
    const { data } = await this.api.post<UpgradeGuestResponse>('/player/upgrade', payload, { signal });
    return data;
  }

  async login(payload: { email: string; password: string }, signal?: AbortSignal): Promise<AuthTokenResponse> {
    const { data } = await this.api.post<AuthTokenResponse>('/auth/login', payload, { signal });
    return data;
  }

  async loginWithUsername(payload: { username: string; password: string }, signal?: AbortSignal): Promise<AuthTokenResponse> {
    const { data } = await this.api.post<AuthTokenResponse>('/auth/login/username', payload, { signal });
    return data;
  }

  async suggestUsername(signal?: AbortSignal): Promise<SuggestUsernameResponse> {
    const { data } = await this.api.get<SuggestUsernameResponse>('/auth/suggest-username', { signal });
    return data;
  }

  async refreshToken(signal?: AbortSignal): Promise<AuthTokenResponse> {
    const { data } = await this.api.post('/auth/refresh', {}, { signal });
    return data;
  }

  async logout(signal?: AbortSignal): Promise<void> {
    await this.api.post('/auth/logout', {}, { signal });
    clearStoredCredentials();
  }

  async getWebsocketToken(signal?: AbortSignal): Promise<WsAuthTokenResponse> {
    const { data } = await this.api.get<WsAuthTokenResponse>('/auth/ws-token', { signal });
    return data;
  }

  async changePassword(
    payload: { current_password: string; new_password: string },
    signal?: AbortSignal,
  ): Promise<ChangePasswordResponse> {
    const { data } = await this.api.post<ChangePasswordResponse>('/player/password', payload, { signal });
    return data;
  }

  async updateEmail(
    payload: { new_email: string; password: string },
    signal?: AbortSignal,
  ): Promise<UpdateEmailResponse> {
    const { data } = await this.api.patch<UpdateEmailResponse>('/player/email', payload, { signal });
    return data;
  }

  async changeUsername(
    payload: { new_username: string; password: string },
    signal?: AbortSignal,
  ): Promise<ChangeUsernameResponse> {
    const { data } = await this.api.patch<ChangeUsernameResponse>('/player/username', payload, { signal });
    return data;
  }

  async deleteAccount(payload: { password: string; confirmation: string }, signal?: AbortSignal): Promise<void> {
    await this.api.delete('/player/account', { data: payload, signal });
    clearStoredCredentials();
  }

  async getBalance(signal?: AbortSignal): Promise<Player> {
    const { data } = await this.api.get('/player/balance', { signal });
    return data;
  }

  async claimDailyBonus(signal?: AbortSignal): Promise<DailyBonusResponse> {
    const { data } = await this.api.post('/player/claim-daily-bonus', {}, { signal });
    return data;
  }

  async getCurrentRound(signal?: AbortSignal): Promise<ActiveRound> {
    const { data } = await this.api.get('/player/current-round', { signal });
    return data;
  }

  async getPendingResults(signal?: AbortSignal): Promise<PendingResultsResponse> {
    const { data } = await this.api.get('/player/pending-results', { signal });
    return data;
  }

  async getPlayerPhrasesets(
    params: { role?: string; status?: string; limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<PhrasesetListResponse> {
    const { data } = await this.api.get('/player/phrasesets', {
      params,
      signal,
    });
    return data;
  }

  async getPhrasesetsSummary(signal?: AbortSignal): Promise<PhrasesetDashboardSummary> {
    const { data } = await this.api.get('/player/phrasesets/summary', { signal });
    return data;
  }

  async getUnclaimedResults(signal?: AbortSignal): Promise<UnclaimedResultsResponse> {
    const { data } = await this.api.get('/player/unclaimed-results', { signal });
    return data;
  }

  async getDashboardData(signal?: AbortSignal): Promise<DashboardData> {
    const { data } = await this.api.get('/player/dashboard', { signal });
    return data;
  }

  async getRoundAvailability(signal?: AbortSignal): Promise<RoundAvailability> {
    const { data } = await this.api.get('/rounds/available', { signal });
    return data;
  }

  async getRoundDetails(roundId: string, signal?: AbortSignal): Promise<RoundDetails> {
    const { data } = await this.api.get(`/rounds/${roundId}`, { signal });
    return data;
  }

  async startPromptRound(signal?: AbortSignal): Promise<StartPromptResponse> {
    const { data } = await this.api.post('/rounds/prompt', {}, { signal });
    return data;
  }

  async startCopyRound(promptRoundId?: string, signal?: AbortSignal): Promise<StartCopyResponse> {
    const params = promptRoundId ? { prompt_round_id: promptRoundId } : {};
    const { data } = await this.api.post('/rounds/copy', {}, { signal, params });
    return data;
  }

  async startVoteRound(signal?: AbortSignal): Promise<StartVoteResponse> {
    const { data } = await this.api.post('/rounds/vote', {}, { signal });
    return data;
  }

  async submitPhrase(roundId: string, phrase: string, signal?: AbortSignal): Promise<SubmitPhraseResponse> {
    const { data } = await this.api.post(`/rounds/${roundId}/submit`, { phrase }, { signal });
    return data;
  }

  async getCopyHints(roundId: string, signal?: AbortSignal): Promise<HintResponse> {
    const { data } = await this.api.get(`/rounds/${roundId}/hints`, { signal });
    return data;
  }

  async flagCopyRound(roundId: string, signal?: AbortSignal): Promise<FlagCopyRoundResponse> {
    const { data } = await this.api.post(`/rounds/${roundId}/flag`, {}, { signal });
    return data;
  }

  async abandonRound(roundId: string, signal?: AbortSignal): Promise<AbandonRoundResponse> {
    const { data } = await this.api.post(`/rounds/${roundId}/abandon`, {}, { signal });
    return data;
  }

  async submitVote(phrasesetId: string, phrase: string, signal?: AbortSignal): Promise<VoteResponse> {
    const { data } = await this.api.post(`/phrasesets/${phrasesetId}/vote`, { phrase }, { signal });
    return data;
  }

  async getPhrasesetResults(phrasesetId: string, signal?: AbortSignal): Promise<PhrasesetResults> {
    const { data } = await this.api.get(`/phrasesets/${phrasesetId}/results`, { signal });
    return data;
  }

  async getPhrasesetDetails(phrasesetId: string, signal?: AbortSignal): Promise<PhrasesetDetails> {
    const { data } = await this.api.get(`/phrasesets/${phrasesetId}/details`, { signal });
    return data;
  }

  async getPublicPhrasesetDetails(phrasesetId: string, signal?: AbortSignal): Promise<PhrasesetDetails> {
    const { data } = await this.api.get(`/phrasesets/${phrasesetId}/public-details`, { signal });
    return data;
  }

  async claimPhrasesetPrize(phrasesetId: string, signal?: AbortSignal): Promise<ClaimPrizeResponse> {
    const { data } = await this.api.post(`/phrasesets/${phrasesetId}/claim`, {}, { signal });
    return data;
  }

  async getCompletedPhrasesets(
    params: { limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<CompletedPhrasesetsResponse> {
    const { data } = await this.api.get('/phrasesets/completed', {
      params,
      signal,
    });
    return data;
  }

  async getRandomPracticePhraseset(signal?: AbortSignal): Promise<PracticePhraseset> {
    const { data } = await this.api.get('/phrasesets/practice/random', { signal });
    return data;
  }

  async submitPromptFeedback(
    roundId: string,
    feedbackType: 'like' | 'dislike',
    signal?: AbortSignal,
  ): Promise<PromptFeedbackResponse> {
    const { data } = await this.api.post(
      `/rounds/${roundId}/feedback`,
      { feedback_type: feedbackType },
      { signal },
    );
    return data;
  }

  async getPromptFeedback(roundId: string, signal?: AbortSignal): Promise<GetPromptFeedbackResponse> {
    const { data } = await this.api.get(`/rounds/${roundId}/feedback`, { signal });
    return data;
  }

  async getStatistics(signal?: AbortSignal): Promise<PlayerStatistics> {
    const { data } = await this.api.get('/player/statistics', { signal });
    return data;
  }

  async getWeeklyLeaderboard(signal?: AbortSignal): Promise<LeaderboardResponse> {
    const { data } = await this.api.get('/player/statistics/weekly-leaderboard', { signal });
    return data;
  }

  async getAllTimeLeaderboard(signal?: AbortSignal): Promise<LeaderboardResponse> {
    const { data } = await this.api.get('/player/statistics/alltime-leaderboard', { signal });
    return data;
  }

  async getTutorialStatus(signal?: AbortSignal): Promise<TutorialStatus> {
    const { data } = await this.api.get('/player/tutorial/status', { signal });
    return data;
  }

  async updateTutorialProgress(progress: TutorialProgress, signal?: AbortSignal): Promise<UpdateTutorialProgressResponse> {
    const { data } = await this.api.post('/player/tutorial/progress', { progress }, { signal });
    return data;
  }

  async resetTutorial(signal?: AbortSignal): Promise<TutorialStatus> {
    const { data } = await this.api.post('/player/tutorial/reset', {}, { signal });
    return data;
  }

  async submitBetaSurvey(
    payload: BetaSurveySubmissionRequest,
    signal?: AbortSignal,
  ): Promise<BetaSurveySubmissionResponse> {
    const { data } = await this.api.post<BetaSurveySubmissionResponse>('/feedback/beta-survey', payload, { signal });
    return data;
  }

  async getBetaSurveyStatus(signal?: AbortSignal): Promise<BetaSurveyStatusResponse> {
    this.logApi('get', '/feedback/beta-survey/status', 'start');
    try {
      const { data } = await this.api.get<BetaSurveyStatusResponse>('/feedback/beta-survey/status', { signal });
      this.logApi('get', '/feedback/beta-survey/status', 'success', data);
      return data;
    } catch (error) {
      this.logApi('get', '/feedback/beta-survey/status', 'error', error);
      throw error;
    }
  }

  async listBetaSurveyResponses(signal?: AbortSignal): Promise<BetaSurveyListResponse> {
    const { data } = await this.api.get<BetaSurveyListResponse>('/feedback/beta-survey', { signal });
    return data;
  }

  async getQuests(signal?: AbortSignal): Promise<QuestListResponse> {
    const { data } = await this.api.get('/quests', { signal });
    return data;
  }

  async getActiveQuests(signal?: AbortSignal): Promise<Quest[]> {
    const { data } = await this.api.get('/quests/active', { signal });
    return data;
  }

  async getClaimableQuests(signal?: AbortSignal): Promise<Quest[]> {
    const { data } = await this.api.get('/quests/claimable', { signal });
    return data;
  }

  async getQuest(questId: string, signal?: AbortSignal): Promise<Quest> {
    const { data } = await this.api.get(`/quests/${questId}`, { signal });
    return data;
  }

  async claimQuestReward(questId: string, signal?: AbortSignal): Promise<ClaimQuestRewardResponse> {
    const { data } = await this.api.post(`/quests/${questId}/claim`, {}, { signal });
    return data;
  }

  async getOnlineUsers(signal?: AbortSignal): Promise<OnlineUsersResponse> {
    const { data } = await this.api.get<OnlineUsersResponse>('/users/online', { signal });
    return data;
  }

  async pingOnlineUser(username: string, signal?: AbortSignal): Promise<PingUserResponse> {
    const { data } = await this.api.post<PingUserResponse>(
      '/users/online/ping',
      { username },
      { signal },
    );
    return data;
  }

  async getAdminConfig(signal?: AbortSignal): Promise<AdminConfig> {
    const { data } = await this.api.get<AdminConfig>('/admin/config', { signal });
    return data;
  }

  async updateAdminConfig(key: string, value: number | string, signal?: AbortSignal): Promise<UpdateAdminConfigResponse> {
    const { data } = await this.api.patch<UpdateAdminConfigResponse>('/admin/config', { key, value }, { signal });
    return data;
  }

  async adminSearchPlayer(
    params: { email?: string; username?: string },
    signal?: AbortSignal,
  ): Promise<AdminPlayerSummary> {
    const { data } = await this.api.get('/admin/players/search', { params, signal });
    return data;
  }

  async adminDeletePlayer(
    payload: { player_id?: string; email?: string; username?: string; confirmation: 'DELETE' },
    signal?: AbortSignal,
  ): Promise<AdminDeletePlayerResponse> {
    const { data } = await this.api.delete('/admin/players', {
      data: payload,
      signal,
    });
    return data;
  }

  async adminResetPassword(
    payload: { player_id?: string; email?: string; username?: string },
    signal?: AbortSignal,
  ): Promise<AdminResetPasswordResponse> {
    const { data } = await this.api.post('/admin/players/reset-password', payload, { signal });
    return data;
  }

  async getFlaggedPrompts(
    status: 'pending' | 'confirmed' | 'dismissed' | 'all' = 'pending',
    signal?: AbortSignal,
  ): Promise<FlaggedPromptListResponse> {
    const queryStatus = status === 'all' ? undefined : status;
    const { data } = await this.api.get('/admin/flags', {
      params: queryStatus ? { status: queryStatus } : undefined,
      signal,
    });
    return data;
  }

  async resolveFlaggedPrompt(
    flagId: string,
    action: 'confirm' | 'dismiss',
    signal?: AbortSignal,
  ): Promise<FlaggedPromptItem> {
    const { data } = await this.api.post(`/admin/flags/${flagId}/resolve`, { action }, { signal });
    return data;
  }

  async testPhraseValidation(
    phrase: string,
    validationType: 'basic' | 'prompt' | 'copy',
    promptText?: string | null,
    originalPhrase?: string | null,
    otherCopyPhrase?: string | null,
    signal?: AbortSignal,
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
    const { data } = await this.api.post(
      '/admin/test-phrase-validation',
      {
        phrase,
        validation_type: validationType,
        prompt_text: promptText,
        original_phrase: originalPhrase,
        other_copy_phrase: otherCopyPhrase,
      },
      { signal },
    );
    return data;
  }
}
