import { BaseApiClient, extractErrorMessage, clearStoredCredentials } from '@crowdcraft/api/BaseApiClient.ts';
import type {
  CaptionSubmissionResult,
  Circle,
  CircleJoinRequestsResponse,
  CircleListResponse,
  CircleMembersResponse,
  MemeCaptionResponse,
  MemeCaptionSubmission,
  MemeVoteResult,
  MemeVoteRound,
  VoteResult,
  VoteRoundState,
  AddMemberRequest,
  AddMemberResponse,
  ApproveJoinRequestResponse,
  CreateCircleRequest,
  CreateCircleResponse,
  DenyJoinRequestResponse,
  JoinCircleResponse,
  LeaveCircleResponse,
  RemoveMemberResponse,
  OnlineUsersResponse,
  PingUserResponse,
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

  async startMemeVoteRound(signal?: AbortSignal): Promise<MemeVoteRound> {
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

  async submitMemeVote(roundId: string, captionId: string, signal?: AbortSignal): Promise<MemeVoteResult> {
    const data = await this.submitMemeMintVote(roundId, captionId, signal);
    return {
      round_id: roundId,
      selected_caption_id: data.chosen_caption_id,
      payout: data.payout,
      wallet: data.new_wallet,
      vault: data.new_vault,
    };
  }

  async submitMemeCaption(request: MemeCaptionSubmission, signal?: AbortSignal): Promise<MemeCaptionResponse> {
    const { data } = await this.api.post('/rounds/caption', request, { signal });
    return data;
  }

  async getMemeMintRoundAvailability(signal?: AbortSignal) {
    return this.getRoundAvailability(signal);
  }

  async getMemeMintRoundDetails(roundId: string, signal?: AbortSignal) {
    return this.getRoundDetails(roundId, signal);
  }

  async startMemeMintVoteRound(signal?: AbortSignal): Promise<VoteRoundState> {
    const { data } = await this.api.post('/rounds/vote', {}, { signal });
    return data;
  }

  async submitMemeMintVote(roundId: string, captionId: string, signal?: AbortSignal): Promise<VoteResult> {
    const { data } = await this.api.post(`/rounds/vote/${roundId}/submit`, { caption_id: captionId }, { signal });
    return data;
  }

  async submitMemeMintCaption(
    payload: { round_id: string; text: string; kind?: 'original' | 'riff'; parent_caption_id?: string | null },
    signal?: AbortSignal,
  ): Promise<CaptionSubmissionResult> {
    const backendPayload = {
      round_id: payload.round_id,
      text: payload.text,
    };
    const { data } = await this.api.post('/rounds/caption', backendPayload, { signal });
    return data;
  }

  async getOnlineUsers(signal?: AbortSignal): Promise<OnlineUsersResponse> {
    const { data } = await this.api.get<OnlineUsersResponse>(`${QF_API_BASE_URL}/users/online`, {
      signal,
    });
    return data;
  }

  async pingOnlineUser(username: string, signal?: AbortSignal): Promise<PingUserResponse> {
    const { data } = await this.api.post<PingUserResponse>(
      `${QF_API_BASE_URL}/users/online/ping`,
      { username },
      { signal },
    );
    return data;
  }

  async listCircles(params: { limit?: number; offset?: number } = {}, signal?: AbortSignal): Promise<CircleListResponse> {
    const { data } = await this.api.get<CircleListResponse>('/circles', {
      params,
      signal,
    });
    return data;
  }

  async getCircle(circleId: string, signal?: AbortSignal): Promise<Circle> {
    const { data } = await this.api.get<Circle>(`/circles/${circleId}`, { signal });
    return data;
  }

  async createCircle(payload: CreateCircleRequest, signal?: AbortSignal): Promise<CreateCircleResponse> {
    const { data } = await this.api.post<CreateCircleResponse>('/circles', payload, { signal });
    return data;
  }

  async joinCircle(circleId: string, signal?: AbortSignal): Promise<JoinCircleResponse> {
    const { data } = await this.api.post<JoinCircleResponse>(`/circles/${circleId}/join`, {}, { signal });
    return data;
  }

  async leaveCircle(circleId: string, signal?: AbortSignal): Promise<LeaveCircleResponse> {
    const { data } = await this.api.delete<LeaveCircleResponse>(`/circles/${circleId}/leave`, { signal });
    return data;
  }

  async getCircleMembers(circleId: string, signal?: AbortSignal): Promise<CircleMembersResponse> {
    const { data } = await this.api.get<CircleMembersResponse>(`/circles/${circleId}/members`, {
      signal,
    });
    return data;
  }

  async addCircleMember(
    circleId: string,
    payload: AddMemberRequest,
    signal?: AbortSignal,
  ): Promise<AddMemberResponse> {
    const { data } = await this.api.post<AddMemberResponse>(`/circles/${circleId}/members`, payload, { signal });
    return data;
  }

  async removeCircleMember(circleId: string, playerId: string, signal?: AbortSignal): Promise<RemoveMemberResponse> {
    const { data } = await this.api.delete<RemoveMemberResponse>(`/circles/${circleId}/members/${playerId}`, {
      signal,
    });
    return data;
  }

  async getCircleJoinRequests(circleId: string, signal?: AbortSignal): Promise<CircleJoinRequestsResponse> {
    const { data } = await this.api.get<CircleJoinRequestsResponse>(`/circles/${circleId}/join-requests`, {
      signal,
    });
    return data;
  }

  async approveJoinRequest(
    circleId: string,
    requestId: string,
    signal?: AbortSignal,
  ): Promise<ApproveJoinRequestResponse> {
    const { data } = await this.api.post<ApproveJoinRequestResponse>(
      `/circles/${circleId}/join-requests/${requestId}/approve`,
      {},
      { signal },
    );
    return data;
  }

  async denyJoinRequest(circleId: string, requestId: string, signal?: AbortSignal): Promise<DenyJoinRequestResponse> {
    const { data } = await this.api.post<DenyJoinRequestResponse>(
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
