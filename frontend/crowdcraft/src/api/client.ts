import axios from 'axios';
import { BaseApiClient, extractErrorMessage, clearStoredCredentials } from './BaseApiClient.ts';
import type {
  ApiError,
  AuthTokenResponse,
  MMCircle,
  MMCircleJoinRequestsResponse,
  MMCircleListResponse,
  MMCircleMembersResponse,
  MMAddMemberRequest,
  MMAddMemberResponse,
  MMClaimQuestRewardResponse,
  MMCreateCircleRequest,
  MMCreateCircleResponse,
  MMJoinCircleResponse,
  MMLeaveCircleResponse,
  MMRemoveMemberResponse,
  MMApproveJoinRequestResponse,
  MMDenyJoinRequestResponse,
  MMCaptionSubmissionResult,
  MMBetaSurveyListResponse,
  MMBetaSurveyStatusResponse,
  MMBetaSurveySubmissionRequest,
  MMBetaSurveySubmissionResponse,
  MMMemeCaptionResponse,
  MMMemeCaptionSubmission,
  MMMemeVoteResult,
  MMMemeVoteRound,
  MMOnlineUsersResponse,
  MMPingUserResponse,
  MMQuest,
  MMQuestListResponse,
  MMVoteResult,
  MMVoteRoundState,
  MMTutorialProgress,
  MMUpdateTutorialProgressResponse,
  TLDashboardResponse,
  TLBalanceResponse,
  TLRoundAvailability,
  TLStartRoundResponse,
  TLSubmitGuessResponse,
  TLRoundDetails,
  TLAbandonRoundResponse,
  TLPromptPreviewResponse,
  TLSeedPromptsResponse,
  TLCorpusStats,
  TLPruneCorpusResponse,
  QFCreatePartySessionRequest,
  QFCreatePartySessionResponse,
  QFJoinPartySessionResponse,
  QFMarkReadyResponse,
  QFPartyListResponse,
  QFPartyPingResponse,
  QFPartyResultsResponse,
  QFPartySessionStatusResponse,
  QFStartPartyCopyResponse,
  QFStartPartyPromptResponse,
  QFStartPartySessionResponse,
  QFStartPartyVoteResponse,
  QFSubmitPartyRoundResponse,
} from './types.ts';

const rawBaseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const QF_API_BASE_URL = /\/qf($|\/)/.test(rawBaseUrl) ? rawBaseUrl : `${rawBaseUrl}/qf`;
const MM_API_BASE_URL = /\/mm($|\/)/.test(rawBaseUrl) ? rawBaseUrl : `${rawBaseUrl}/mm`;
const TL_API_BASE_URL = /\/tl($|\/)/.test(rawBaseUrl) ? rawBaseUrl : `${rawBaseUrl}/tl`;

class CrowdcraftApiClient extends BaseApiClient {
  private readonly mmApi: BaseApiClient;
  private readonly tlApi: BaseApiClient;
  private readonly rootApi = axios.create({
    baseURL: rawBaseUrl,
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true,
  });

  private _handleApiError(error: unknown, context: string, customMessage: string): never {
    const axiosError = error as ApiError;

    if (axiosError?.response?.status === 500) {
      console.error(`${context} failed with server error:`, {
        status: axiosError.response.status,
        statusText: axiosError.response.statusText,
        data: axiosError.response.data,
        message: axiosError.message,
      });

      throw {
        ...axiosError,
        message: customMessage,
        isServerError: true,
      } as ApiError;
    }

    console.error(`${context} failed:`, {
      status: axiosError?.response?.status,
      statusText: axiosError?.response?.statusText,
      data: axiosError?.response?.data,
      message: axiosError?.message,
    });

    throw error;
  }

  constructor() {
    super(QF_API_BASE_URL);
    this.mmApi = new BaseApiClient(MM_API_BASE_URL);
    this.tlApi = new BaseApiClient(TL_API_BASE_URL);
  }

  get axiosInstance() {
    return this.api;
  }

  get mmAxiosInstance() {
    return this.mmApi.axiosInstance;
  }

  get tlAxiosInstance() {
    return this.tlApi.axiosInstance;
  }

  // QF Party Mode APIs
  async qfCreatePartySession(
    request: QFCreatePartySessionRequest = {},
    signal?: AbortSignal,
  ): Promise<QFCreatePartySessionResponse> {
    try {
      const { data } = await this.api.post<QFCreatePartySessionResponse>('/party/create', request, {
        signal,
        timeout: 10000,
      });
      return data;
    } catch (error) {
      this._handleApiError(error, 'Party creation', 'Server error creating party. Please try again in a moment.');
    }
  }

  async qfListActiveParties(signal?: AbortSignal): Promise<QFPartyListResponse> {
    const { data } = await this.api.get<QFPartyListResponse>('/party/list', { signal });
    return data;
  }

  async qfJoinPartySessionById(sessionId: string, signal?: AbortSignal): Promise<QFJoinPartySessionResponse> {
    const { data } = await this.api.post<QFJoinPartySessionResponse>(`/party/${sessionId}/join`, {}, { signal });
    return data;
  }

  async qfJoinPartySession(partyCode: string, signal?: AbortSignal): Promise<QFJoinPartySessionResponse> {
    const { data } = await this.api.post<QFJoinPartySessionResponse>('/party/join', { party_code: partyCode }, { signal });
    return data;
  }

  async qfMarkPartyReady(sessionId: string, signal?: AbortSignal): Promise<QFMarkReadyResponse> {
    const { data } = await this.api.post<QFMarkReadyResponse>(`/party/${sessionId}/ready`, {}, { signal });
    return data;
  }

  async qfAddAIPlayerToParty(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<{ participant_id: string; player_id: string; username: string; is_ai: boolean }> {
    const { data } = await this.api.post<{ participant_id: string; player_id: string; username: string; is_ai: boolean }>(
      `/party/${sessionId}/add-ai`,
      {},
      { signal },
    );
    return data;
  }

  async qfStartPartySession(sessionId: string, signal?: AbortSignal): Promise<QFStartPartySessionResponse> {
    const { data } = await this.api.post<QFStartPartySessionResponse>(`/party/${sessionId}/start`, {}, { signal });
    return data;
  }

  async qfGetPartySessionStatus(sessionId: string, signal?: AbortSignal): Promise<QFPartySessionStatusResponse> {
    const { data } = await this.api.get<QFPartySessionStatusResponse>(`/party/${sessionId}/status`, { signal });
    return data;
  }

  async qfLeavePartySession(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<{ success: boolean; message: string }> {
    const { data } = await this.api.post<{ success: boolean; message: string }>(`/party/${sessionId}/leave`, {}, { signal });
    return data;
  }

  async qfStartPartyPromptRound(sessionId: string, signal?: AbortSignal): Promise<QFStartPartyPromptResponse> {
    const { data } = await this.api.post<QFStartPartyPromptResponse>(`/party/${sessionId}/rounds/prompt`, {}, { signal });
    return data;
  }

  async qfStartPartyCopyRound(sessionId: string, signal?: AbortSignal): Promise<QFStartPartyCopyResponse> {
    const { data } = await this.api.post<QFStartPartyCopyResponse>(`/party/${sessionId}/rounds/copy`, {}, { signal });
    return data;
  }

  async qfStartPartyVoteRound(sessionId: string, signal?: AbortSignal): Promise<QFStartPartyVoteResponse> {
    const { data } = await this.api.post<QFStartPartyVoteResponse>(`/party/${sessionId}/rounds/vote`, {}, { signal });
    return data;
  }

  async qfSubmitPartyRound(
    sessionId: string,
    roundId: string,
    payload: { phrase?: string; vote?: string },
    signal?: AbortSignal,
  ): Promise<QFSubmitPartyRoundResponse> {
    const { data } = await this.api.post<QFSubmitPartyRoundResponse>(
      `/party/${sessionId}/rounds/${roundId}/submit`,
      payload,
      { signal },
    );
    return data;
  }

  async qfGetPartyResults(sessionId: string, signal?: AbortSignal): Promise<QFPartyResultsResponse> {
    const { data } = await this.api.get<QFPartyResultsResponse>(`/party/${sessionId}/results`, { signal });
    return data;
  }

  async qfPingParty(sessionId: string, signal?: AbortSignal): Promise<QFPartyPingResponse> {
    const { data } = await this.api.post<QFPartyPingResponse>(`/party/${sessionId}/ping`, {}, { signal });
    return data;
  }

  // MM gameplay helpers
  async mmStartVoteRound(signal?: AbortSignal): Promise<MMMemeVoteRound> {
    const data = await this.mmStartVoteRoundRaw(signal);
    return {
      round_id: data.round_id,
      expires_at: data.expires_at,
      meme: {
        meme_id: data.image_id,
        image_url: data.image_url,
        alt_text: data.attribution_text || undefined,
      },
      captions: data.captions.map((caption) => ({
        caption_id: caption.caption_id,
        text: caption.text,
        is_original: true,
        riff_on_caption_id: null,
      })),
    };
  }

  async mmSubmitVote(roundId: string, captionId: string, signal?: AbortSignal): Promise<MMMemeVoteResult> {
    const data = await this.mmSubmitVoteRaw(roundId, captionId, signal);
    return {
      round_id: roundId,
      selected_caption_id: data.chosen_caption_id,
      payout: data.payout,
      wallet: data.new_wallet,
      vault: data.new_vault,
    };
  }

  async mmSubmitCaption(request: MMMemeCaptionSubmission, signal?: AbortSignal): Promise<MMMemeCaptionResponse> {
    const { data } = await this.mmApi.axiosInstance.post('/rounds/caption', request, { signal });
    return data;
  }

  async mmGetRoundAvailability(signal?: AbortSignal) {
    return this.mmApi.getRoundAvailability(signal);
  }

  async mmGetRoundDetails(roundId: string, signal?: AbortSignal) {
    return this.mmApi.getRoundDetails(roundId, signal);
  }

  async mmStartVoteRoundRaw(signal?: AbortSignal): Promise<MMVoteRoundState> {
    const { data } = await this.mmApi.axiosInstance.post('/rounds/vote', {}, { signal });
    return data;
  }

  async mmSubmitVoteRaw(roundId: string, captionId: string, signal?: AbortSignal): Promise<MMVoteResult> {
    const { data } = await this.mmApi.axiosInstance.post(`/rounds/vote/${roundId}/submit`, { caption_id: captionId }, { signal });
    return data;
  }

  async mmSubmitCaptionRaw(
    payload: { round_id: string; text: string; kind?: 'original' | 'riff'; parent_caption_id?: string | null },
    signal?: AbortSignal,
  ): Promise<MMCaptionSubmissionResult> {
    const backendPayload = {
      round_id: payload.round_id,
      text: payload.text,
    };
    const { data } = await this.mmApi.axiosInstance.post('/rounds/caption', backendPayload, { signal });
    return data;
  }

  async mmGetOnlineUsers(signal?: AbortSignal): Promise<MMOnlineUsersResponse> {
    const { data } = await this.api.get<MMOnlineUsersResponse>('/users/online', { signal });
    return data;
  }

  async mmPingOnlineUser(username: string, signal?: AbortSignal): Promise<MMPingUserResponse> {
    const { data } = await this.api.post<MMPingUserResponse>('/users/online/ping', { username }, { signal });
    return data;
  }

  async mmSubmitBetaSurvey(
    payload: MMBetaSurveySubmissionRequest,
    signal?: AbortSignal,
  ): Promise<MMBetaSurveySubmissionResponse> {
    const { data } = await this.api.post<MMBetaSurveySubmissionResponse>('/feedback/beta-survey', payload, { signal });
    return data;
  }

  async mmGetBetaSurveyStatus(signal?: AbortSignal): Promise<MMBetaSurveyStatusResponse> {
    const { data } = await this.api.get<MMBetaSurveyStatusResponse>('/feedback/beta-survey/status', { signal });
    return data;
  }

  async mmListBetaSurveyResponses(signal?: AbortSignal): Promise<MMBetaSurveyListResponse> {
    const { data } = await this.api.get<MMBetaSurveyListResponse>('/feedback/beta-survey', { signal });
    return data;
  }

  async mmGetQuests(signal?: AbortSignal): Promise<MMQuestListResponse> {
    const { data } = await this.api.get<MMQuestListResponse>('/quests', { signal });
    return data;
  }

  async mmGetActiveQuests(signal?: AbortSignal): Promise<MMQuest[]> {
    const { data } = await this.api.get<MMQuest[]>('/quests/active', { signal });
    return data;
  }

  async mmGetClaimableQuests(signal?: AbortSignal): Promise<MMQuest[]> {
    const { data } = await this.api.get<MMQuest[]>('/quests/claimable', { signal });
    return data;
  }

  async mmGetQuest(questId: string, signal?: AbortSignal): Promise<MMQuest> {
    const { data } = await this.api.get<MMQuest>(`/quests/${questId}`, { signal });
    return data;
  }

  async mmClaimQuestReward(questId: string, signal?: AbortSignal): Promise<MMClaimQuestRewardResponse> {
    const { data } = await this.api.post<MMClaimQuestRewardResponse>(`/quests/${questId}/claim`, {}, { signal });
    return data;
  }

  // MM Circles
  async mmListCircles(params: { limit?: number; offset?: number } = {}, signal?: AbortSignal): Promise<MMCircleListResponse> {
    const { data } = await this.mmApi.axiosInstance.get<MMCircleListResponse>('/circles', {
      params,
      signal,
    });
    return data;
  }

  async mmGetCircle(circleId: string, signal?: AbortSignal): Promise<MMCircle> {
    const { data } = await this.mmApi.axiosInstance.get<MMCircle>(`/circles/${circleId}`, { signal });
    return data;
  }

  async mmCreateCircle(payload: MMCreateCircleRequest, signal?: AbortSignal): Promise<MMCreateCircleResponse> {
    const { data } = await this.mmApi.axiosInstance.post<MMCreateCircleResponse>('/circles', payload, { signal });
    return data;
  }

  async mmJoinCircle(circleId: string, signal?: AbortSignal): Promise<MMJoinCircleResponse> {
    const { data } = await this.mmApi.axiosInstance.post<MMJoinCircleResponse>(`/circles/${circleId}/join`, {}, { signal });
    return data;
  }

  async mmLeaveCircle(circleId: string, signal?: AbortSignal): Promise<MMLeaveCircleResponse> {
    const { data } = await this.mmApi.axiosInstance.delete<MMLeaveCircleResponse>(`/circles/${circleId}/leave`, { signal });
    return data;
  }

  async mmGetCircleMembers(circleId: string, signal?: AbortSignal): Promise<MMCircleMembersResponse> {
    const { data } = await this.mmApi.axiosInstance.get<MMCircleMembersResponse>(`/circles/${circleId}/members`, {
      signal,
    });
    return data;
  }

  async mmAddCircleMember(
    circleId: string,
    payload: MMAddMemberRequest,
    signal?: AbortSignal,
  ): Promise<MMAddMemberResponse> {
    const { data } = await this.mmApi.axiosInstance.post<MMAddMemberResponse>(`/circles/${circleId}/members`, payload, {
      signal,
    });
    return data;
  }

  async mmRemoveCircleMember(circleId: string, playerId: string, signal?: AbortSignal): Promise<MMRemoveMemberResponse> {
    const { data } = await this.mmApi.axiosInstance.delete<MMRemoveMemberResponse>(
      `/circles/${circleId}/members/${playerId}`,
      { signal },
    );
    return data;
  }

  async mmGetCircleJoinRequests(circleId: string, signal?: AbortSignal): Promise<MMCircleJoinRequestsResponse> {
    const { data } = await this.mmApi.axiosInstance.get<MMCircleJoinRequestsResponse>(`/circles/${circleId}/join-requests`, {
      signal,
    });
    return data;
  }

  async mmApproveJoinRequest(
    circleId: string,
    requestId: string,
    signal?: AbortSignal,
  ): Promise<MMApproveJoinRequestResponse> {
    const { data } = await this.mmApi.axiosInstance.post<MMApproveJoinRequestResponse>(
      `/circles/${circleId}/join-requests/${requestId}/approve`,
      {},
      { signal },
    );
    return data;
  }

  async mmDenyJoinRequest(circleId: string, requestId: string, signal?: AbortSignal): Promise<MMDenyJoinRequestResponse> {
    const { data } = await this.mmApi.axiosInstance.post<MMDenyJoinRequestResponse>(
      `/circles/${circleId}/join-requests/${requestId}/deny`,
      {},
      { signal },
    );
    return data;
  }

  // MM equivalents of shared player/auth methods
  async mmCreatePlayer(payload: { email: string; password: string }, signal?: AbortSignal) {
    return this.mmApi.createPlayer(payload, signal);
  }

  async mmCreateGuest(signal?: AbortSignal) {
    return this.mmApi.createGuest(signal);
  }

  async mmUpgradeGuest(payload: { email: string; password: string }, signal?: AbortSignal) {
    return this.mmApi.upgradeGuest(payload, signal);
  }

  async mmLogin(payload: { email: string; password: string }, signal?: AbortSignal): Promise<AuthTokenResponse> {
    return this.mmApi.login(payload, signal);
  }

  async mmLoginWithUsername(payload: { username: string; password: string }, signal?: AbortSignal): Promise<AuthTokenResponse> {
    return this.mmApi.loginWithUsername(payload, signal);
  }

  async mmGetHealth(signal?: AbortSignal) {
    return this.mmApi.getHealth(signal);
  }

  async mmGetApiInfo(signal?: AbortSignal) {
    return this.mmApi.getApiInfo(signal);
  }

  async mmGetGameStatus(signal?: AbortSignal) {
    return this.mmApi.getGameStatus(signal);
  }

  async mmGetBalance(signal?: AbortSignal) {
    return this.mmApi.getBalance(signal);
  }

  async mmClaimDailyBonus(signal?: AbortSignal) {
    return this.mmApi.claimDailyBonus(signal);
  }

  async mmGetDashboardData(signal?: AbortSignal) {
    return this.mmApi.getDashboardData(signal);
  }

  async mmGetCopyHints(roundId: string, signal?: AbortSignal) {
    return this.mmApi.getCopyHints(roundId, signal);
  }

  async mmFlagCopyRound(roundId: string, signal?: AbortSignal) {
    return this.mmApi.flagCopyRound(roundId, signal);
  }

  async mmAbandonRound(roundId: string, signal?: AbortSignal) {
    return this.mmApi.abandonRound(roundId, signal);
  }

  async mmClaimPhrasesetPrize(phrasesetId: string, signal?: AbortSignal) {
    return this.mmApi.claimPhrasesetPrize(phrasesetId, signal);
  }

  async mmGetWeeklyLeaderboard(signal?: AbortSignal) {
    return this.mmApi.getWeeklyLeaderboard(signal);
  }

  async mmGetAllTimeLeaderboard(signal?: AbortSignal) {
    return this.mmApi.getAllTimeLeaderboard(signal);
  }

  async mmChangePassword(payload: { current_password: string; new_password: string }, signal?: AbortSignal) {
    return this.mmApi.changePassword(payload, signal);
  }

  async mmUpdateEmail(payload: { new_email: string; password: string }, signal?: AbortSignal) {
    return this.mmApi.updateEmail(payload, signal);
  }

  async mmChangeUsername(payload: { new_username: string; password: string }, signal?: AbortSignal) {
    return this.mmApi.changeUsername(payload, signal);
  }

  async mmDeleteAccount(payload: { password: string; confirmation: string }, signal?: AbortSignal) {
    return this.mmApi.deleteAccount(payload, signal);
  }

  async mmLogout(signal?: AbortSignal) {
    return this.mmApi.logout(signal);
  }

  async mmSubmitPromptFeedback(roundId: string, feedbackType: 'like' | 'dislike', signal?: AbortSignal) {
    return this.mmApi.submitPromptFeedback(roundId, feedbackType, signal);
  }

  async mmGetPromptFeedback(roundId: string, signal?: AbortSignal) {
    return this.mmApi.getPromptFeedback(roundId, signal);
  }

  async mmGetStatistics(signal?: AbortSignal) {
    return this.mmApi.getStatistics(signal);
  }

  async mmGetTutorialStatus(signal?: AbortSignal) {
    return this.mmApi.getTutorialStatus(signal);
  }

  async mmUpdateTutorialProgress(
    progress: MMTutorialProgress,
    signal?: AbortSignal,
  ): Promise<MMUpdateTutorialProgressResponse> {
    const { data } = await this.mmApi.axiosInstance.post<MMUpdateTutorialProgressResponse>(
      '/player/tutorial/progress',
      { progress },
      { signal },
    );
    return data;
  }

  async mmResetTutorial(signal?: AbortSignal) {
    return this.mmApi.resetTutorial(signal);
  }

  async mmAdminConfig(signal?: AbortSignal) {
    return this.mmApi.getAdminConfig(signal);
  }

  async mmUpdateAdminConfig(key: string, value: number | string, signal?: AbortSignal) {
    return this.mmApi.updateAdminConfig(key, value, signal);
  }

  async mmGetFlaggedPrompts(status?: 'pending' | 'confirmed' | 'dismissed' | 'all', signal?: AbortSignal) {
    return this.mmApi.getFlaggedPrompts(status, signal);
  }

  async mmResolveFlaggedPrompt(flagId: string, action: 'confirm' | 'dismiss', signal?: AbortSignal) {
    return this.mmApi.resolveFlaggedPrompt(flagId, action, signal);
  }

  async mmTestPhraseValidation(
    phrase: string,
    validationType: 'basic' | 'prompt' | 'copy',
    promptText?: string | null,
    originalPhrase?: string | null,
    otherCopyPhrase?: string | null,
    signal?: AbortSignal,
  ) {
    return this.mmApi.testPhraseValidation(phrase, validationType, promptText, originalPhrase, otherCopyPhrase, signal);
  }

  async mmAdminSearchPlayer(params: { email?: string; username?: string }, signal?: AbortSignal) {
    return this.mmApi.adminSearchPlayer(params, signal);
  }

  async mmAdminDeletePlayer(
    payload: { player_id?: string; email?: string; username?: string; confirmation: 'DELETE' },
    signal?: AbortSignal,
  ) {
    return this.mmApi.adminDeletePlayer(payload, signal);
  }

  async mmAdminResetPassword(payload: { player_id?: string; email?: string; username?: string }, signal?: AbortSignal) {
    return this.mmApi.adminResetPassword(payload, signal);
  }

  // TL gameplay helpers
  async tlGetDashboard(signal?: AbortSignal): Promise<TLDashboardResponse> {
    const { data } = await this.tlApi.axiosInstance.get<TLDashboardResponse>('/player/dashboard', { signal });
    return data;
  }

  async tlGetBalance(signal?: AbortSignal): Promise<TLBalanceResponse> {
    const { data } = await this.tlApi.axiosInstance.get<TLBalanceResponse>('/player/balance', { signal });
    return data;
  }

  async tlCheckRoundAvailability(signal?: AbortSignal): Promise<TLRoundAvailability> {
    const { data } = await this.tlApi.axiosInstance.get<TLRoundAvailability>('/rounds/available', { signal });
    return data;
  }

  async tlStartRound(signal?: AbortSignal): Promise<TLStartRoundResponse> {
    try {
      const { data } = await this.tlApi.axiosInstance.post<TLStartRoundResponse>('/rounds/start', {}, { signal, timeout: 10000 });
      return data;
    } catch (error) {
      this._handleApiError(error, 'Round creation', 'Server error starting round. Please try again in a moment.');
    }
  }

  async tlSubmitGuess(roundId: string, guessText: string, signal?: AbortSignal): Promise<TLSubmitGuessResponse> {
    const request = { guess_text: guessText };
    const { data } = await this.tlApi.axiosInstance.post<TLSubmitGuessResponse>(`/rounds/${roundId}/guess`, request, {
      signal,
    });
    return data;
  }

  async tlGetRoundDetails(roundId: string, signal?: AbortSignal): Promise<TLRoundDetails> {
    const { data } = await this.tlApi.axiosInstance.get<TLRoundDetails>(`/rounds/${roundId}`, { signal });
    return data;
  }

  async tlAbandonRound(roundId: string, signal?: AbortSignal): Promise<TLAbandonRoundResponse> {
    const { data } = await this.tlApi.axiosInstance.post<TLAbandonRoundResponse>(`/rounds/${roundId}/abandon`, {}, { signal });
    return data;
  }

  async tlPreviewPrompt(signal?: AbortSignal): Promise<TLPromptPreviewResponse> {
    const { data } = await this.tlApi.axiosInstance.get<TLPromptPreviewResponse>('/game/prompts/preview', { signal });
    return data;
  }

  async tlSeedPrompts(prompts: string[], signal?: AbortSignal): Promise<TLSeedPromptsResponse> {
    const requestPayload = { prompts };
    const { data } = await this.tlApi.axiosInstance.post<TLSeedPromptsResponse>('/admin/prompts/seed', requestPayload, {
      signal,
      timeout: 30000,
    });
    return data;
  }

  async tlGetCorpusStats(promptId: string, signal?: AbortSignal): Promise<TLCorpusStats> {
    const { data } = await this.tlApi.axiosInstance.get<TLCorpusStats>(`/admin/corpus/${promptId}`, { signal });
    return data;
  }

  async tlPruneCorpus(promptId: string, signal?: AbortSignal): Promise<TLPruneCorpusResponse> {
    const { data } = await this.tlApi.axiosInstance.post<TLPruneCorpusResponse>(`/admin/corpus/${promptId}/prune`, {}, {
      signal,
    });
    return data;
  }

  async tlGetOnlineUsers(signal?: AbortSignal): Promise<MMOnlineUsersResponse> {
    const { data } = await this.tlApi.axiosInstance.get<MMOnlineUsersResponse>('/users/online', { signal });
    return data;
  }

  async tlPingOnlineUser(username: string, signal?: AbortSignal): Promise<MMPingUserResponse> {
    const { data } = await this.tlApi.axiosInstance.post<MMPingUserResponse>('/users/online/ping', { username }, { signal });
    return data;
  }

  // Root level helpers
  async logoutEverywhere(refreshTokenValue?: string) {
    const payload = refreshTokenValue ? { refresh_token: refreshTokenValue } : {};
    await this.rootApi.post<void>('/auth/logout', payload);
  }
}

export const apiClient = new CrowdcraftApiClient();
export const axiosInstance = apiClient.axiosInstance;
export const mmAxiosInstance = apiClient.mmAxiosInstance;
export const tlAxiosInstance = apiClient.tlAxiosInstance;

export default apiClient;
export { extractErrorMessage, clearStoredCredentials };
