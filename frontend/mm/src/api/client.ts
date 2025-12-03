import { BaseApiClient, extractErrorMessage, clearStoredCredentials } from '@crowdcraft/api/BaseApiClient.ts';
import type {
  MMCaptionSubmissionResult,
  MMCircle,
  MMCircleJoinRequestsResponse,
  MMCircleListResponse,
  MMCircleMembersResponse,
  MMMemeCaptionResponse,
  MMMemeCaptionSubmission,
  MMMemeVoteResult,
  MMMemeVoteRound,
  MMVoteResult,
  MMVoteRoundState,
  MMAddMemberRequest,
  MMAddMemberResponse,
  MMApproveJoinRequestResponse,
  MMCreateCircleRequest,
  MMCreateCircleResponse,
  MMDenyJoinRequestResponse,
  MMJoinCircleResponse,
  MMLeaveCircleResponse,
  MMRemoveMemberResponse,
  MMOnlineUsersResponse,
  MMPingUserResponse,
  MMBetaSurveyListResponse,
  MMBetaSurveyStatusResponse,
  MMBetaSurveySubmissionRequest,
  MMBetaSurveySubmissionResponse,
  MMQuest,
  MMQuestListResponse,
  MMClaimQuestRewardResponse,
} from '@crowdcraft/api/types.ts';

const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const ROOT_API_URL = baseUrl
  .replace(/\/mm($|\/)/, '')
  .replace(/\/qf($|\/)/, '');

const API_BASE_URL = `${ROOT_API_URL}/mm`;
const QF_API_BASE_URL = `${ROOT_API_URL}/qf`;

class MemeMintApiClient extends BaseApiClient {
  constructor() {
    super(API_BASE_URL);
  }

  override async getQuests(signal?: AbortSignal): Promise<MMQuestListResponse> {
    const { data } = await this.api.get<MMQuestListResponse>('/quests', {
      baseURL: QF_API_BASE_URL,
      signal,
    });
    return data;
  }

  override async getActiveQuests(signal?: AbortSignal): Promise<MMQuest[]> {
    const { data } = await this.api.get<MMQuest[]>('/quests/active', {
      baseURL: QF_API_BASE_URL,
      signal,
    });
    return data;
  }

  override async getClaimableQuests(signal?: AbortSignal): Promise<MMQuest[]> {
    const { data } = await this.api.get<MMQuest[]>('/quests/claimable', {
      baseURL: QF_API_BASE_URL,
      signal,
    });
    return data;
  }

  override async getQuest(questId: string, signal?: AbortSignal): Promise<MMQuest> {
    const { data } = await this.api.get<MMQuest>(`/quests/${questId}`, {
      baseURL: QF_API_BASE_URL,
      signal,
    });
    return data;
  }

  override async claimQuestReward(questId: string, signal?: AbortSignal): Promise<MMClaimQuestRewardResponse> {
    const { data } = await this.api.post<MMClaimQuestRewardResponse>(
      `/quests/${questId}/claim`,
      {},
      {
        baseURL: QF_API_BASE_URL,
        signal,
      },
    );
    return data;
  }

  async startMemeVoteRound(signal?: AbortSignal): Promise<MMMemeVoteRound> {
    const data = await this.startMemeMintVoteRound(signal);
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

  async submitMemeVote(roundId: string, captionId: string, signal?: AbortSignal): Promise<MMMemeVoteResult> {
    const data = await this.submitMemeMintVote(roundId, captionId, signal);
    return {
      round_id: roundId,
      selected_caption_id: data.chosen_caption_id,
      payout: data.payout,
      wallet: data.new_wallet,
      vault: data.new_vault,
    };
  }

  async submitMemeCaption(request: MMMemeCaptionSubmission, signal?: AbortSignal): Promise<MMMemeCaptionResponse> {
    const { data } = await this.api.post('/rounds/caption', request, { signal });
    return data;
  }

  async getMemeMintRoundAvailability(signal?: AbortSignal) {
    return this.getRoundAvailability(signal);
  }

  async getMemeMintRoundDetails(roundId: string, signal?: AbortSignal) {
    return this.getRoundDetails(roundId, signal);
  }

  async startMemeMintVoteRound(signal?: AbortSignal): Promise<MMVoteRoundState> {
    const { data } = await this.api.post('/rounds/vote', {}, { signal });
    return data;
  }

  async submitMemeMintVote(roundId: string, captionId: string, signal?: AbortSignal): Promise<MMVoteResult> {
    const { data } = await this.api.post(`/rounds/vote/${roundId}/submit`, { caption_id: captionId }, { signal });
    return data;
  }

  async submitMemeMintCaption(
    payload: { round_id: string; text: string; kind?: 'original' | 'riff'; parent_caption_id?: string | null },
    signal?: AbortSignal,
  ): Promise<MMCaptionSubmissionResult> {
    const backendPayload = {
      round_id: payload.round_id,
      text: payload.text,
    };
    const { data } = await this.api.post('/rounds/caption', backendPayload, { signal });
    return data;
  }

  async getOnlineUsers(signal?: AbortSignal): Promise<MMOnlineUsersResponse> {
    const { data } = await this.api.get<MMOnlineUsersResponse>('/users/online', {
      baseURL: QF_API_BASE_URL,
      signal,
    });
    return data;
  }

  async pingOnlineUser(username: string, signal?: AbortSignal): Promise<MMPingUserResponse> {
    const { data } = await this.api.post<MMPingUserResponse>(
      '/users/online/ping',
      { username },
      { baseURL: QF_API_BASE_URL, signal },
    );
    return data;
  }

  override async submitBetaSurvey(
    payload: MMBetaSurveySubmissionRequest,
    signal?: AbortSignal,
  ): Promise<MMBetaSurveySubmissionResponse> {
    const { data } = await this.api.post<MMBetaSurveySubmissionResponse>('/feedback/beta-survey', payload, {
      baseURL: QF_API_BASE_URL,
      signal,
    });
    return data;
  }

  override async getBetaSurveyStatus(signal?: AbortSignal): Promise<MMBetaSurveyStatusResponse> {
    const { data } = await this.api.get<MMBetaSurveyStatusResponse>('/feedback/beta-survey/status', {
      baseURL: QF_API_BASE_URL,
      signal,
    });
    return data;
  }

  override async listBetaSurveyResponses(signal?: AbortSignal): Promise<MMBetaSurveyListResponse> {
    const { data } = await this.api.get<MMBetaSurveyListResponse>('/feedback/beta-survey', {
      baseURL: QF_API_BASE_URL,
      signal,
    });
    return data;
  }

  async listCircles(params: { limit?: number; offset?: number } = {}, signal?: AbortSignal): Promise<MMCircleListResponse> {
    const { data } = await this.api.get<MMCircleListResponse>('/circles', {
      params,
      signal,
    });
    return data;
  }

  async getCircle(circleId: string, signal?: AbortSignal): Promise<MMCircle> {
    const { data } = await this.api.get<MMCircle>(`/circles/${circleId}`, { signal });
    return data;
  }

  async createCircle(payload: MMCreateCircleRequest, signal?: AbortSignal): Promise<MMCreateCircleResponse> {
    const { data } = await this.api.post<MMCreateCircleResponse>('/circles', payload, { signal });
    return data;
  }

  async joinCircle(circleId: string, signal?: AbortSignal): Promise<MMJoinCircleResponse> {
    const { data } = await this.api.post<MMJoinCircleResponse>(`/circles/${circleId}/join`, {}, { signal });
    return data;
  }

  async leaveCircle(circleId: string, signal?: AbortSignal): Promise<MMLeaveCircleResponse> {
    const { data } = await this.api.delete<MMLeaveCircleResponse>(`/circles/${circleId}/leave`, { signal });
    return data;
  }

  async getCircleMembers(circleId: string, signal?: AbortSignal): Promise<MMCircleMembersResponse> {
    const { data } = await this.api.get<MMCircleMembersResponse>(`/circles/${circleId}/members`, {
      signal,
    });
    return data;
  }

  async addCircleMember(
    circleId: string,
    payload: MMAddMemberRequest,
    signal?: AbortSignal,
  ): Promise<MMAddMemberResponse> {
    const { data } = await this.api.post<MMAddMemberResponse>(`/circles/${circleId}/members`, payload, { signal });
    return data;
  }

  async removeCircleMember(circleId: string, playerId: string, signal?: AbortSignal): Promise<MMRemoveMemberResponse> {
    const { data } = await this.api.delete<MMRemoveMemberResponse>(`/circles/${circleId}/members/${playerId}`, {
      signal,
    });
    return data;
  }

  async getCircleJoinRequests(circleId: string, signal?: AbortSignal): Promise<MMCircleJoinRequestsResponse> {
    const { data } = await this.api.get<MMCircleJoinRequestsResponse>(`/circles/${circleId}/join-requests`, {
      signal,
    });
    return data;
  }

  async approveJoinRequest(
    circleId: string,
    requestId: string,
    signal?: AbortSignal,
  ): Promise<MMApproveJoinRequestResponse> {
    const { data } = await this.api.post<MMApproveJoinRequestResponse>(
      `/circles/${circleId}/join-requests/${requestId}/approve`,
      {},
      { signal },
    );
    return data;
  }

  async denyJoinRequest(circleId: string, requestId: string, signal?: AbortSignal): Promise<MMDenyJoinRequestResponse> {
    const { data } = await this.api.post<MMDenyJoinRequestResponse>(
      `/circles/${circleId}/join-requests/${requestId}/deny`,
      {},
      { signal },
    );
    return data;
  }
}

export const apiClient = new MemeMintApiClient();
export const axiosInstance = apiClient.axiosInstance;

export default apiClient;
export { extractErrorMessage, clearStoredCredentials };
