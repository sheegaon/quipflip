import { BaseApiClient, extractErrorMessage, clearStoredCredentials } from '@crowdcraft/api/BaseApiClient.ts';
import type {
  ApiError,
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
  QFOnlineUsersResponse,
  QFPingUserResponse,
} from '@crowdcraft/api/types.ts';

const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE_URL = /\/qf($|\/)/.test(baseUrl) ? baseUrl : `${baseUrl}/qf`;

class QuipFlipApiClient extends BaseApiClient {
  constructor() {
    super(API_BASE_URL);
  }

  async createPartySession(
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
      const axiosError = error as ApiError;

      if (axiosError?.response?.status === 500) {
        console.error('Party creation failed with server error:', {
          status: axiosError.response.status,
          statusText: axiosError.response.statusText,
          data: axiosError.response.data,
          message: axiosError.message,
        });

        throw {
          ...axiosError,
          message: 'Server error creating party. Please try again in a moment.',
          isServerError: true,
        } as ApiError;
      }

      console.error('Party creation failed:', {
        status: axiosError?.response?.status,
        statusText: axiosError?.response?.statusText,
        data: axiosError?.response?.data,
        message: axiosError?.message,
      });

      throw error;
    }
  }

  async listActiveParties(signal?: AbortSignal): Promise<QFPartyListResponse> {
    const { data } = await this.api.get<QFPartyListResponse>('/party/list', { signal });
    return data;
  }

  async joinPartySessionById(sessionId: string, signal?: AbortSignal): Promise<QFJoinPartySessionResponse> {
    const { data } = await this.api.post<QFJoinPartySessionResponse>(`/party/${sessionId}/join`, {}, { signal });
    return data;
  }

  async joinPartySession(partyCode: string, signal?: AbortSignal): Promise<QFJoinPartySessionResponse> {
    const { data } = await this.api.post<QFJoinPartySessionResponse>('/party/join', { party_code: partyCode }, { signal });
    return data;
  }

  async markPartyReady(sessionId: string, signal?: AbortSignal): Promise<QFMarkReadyResponse> {
    const { data } = await this.api.post<QFMarkReadyResponse>(`/party/${sessionId}/ready`, {}, { signal });
    return data;
  }

  async addAIPlayerToParty(
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

  async startPartySession(sessionId: string, signal?: AbortSignal): Promise<QFStartPartySessionResponse> {
    const { data } = await this.api.post<QFStartPartySessionResponse>(`/party/${sessionId}/start`, {}, { signal });
    return data;
  }

  async getPartySessionStatus(sessionId: string, signal?: AbortSignal): Promise<QFPartySessionStatusResponse> {
    const { data } = await this.api.get<QFPartySessionStatusResponse>(`/party/${sessionId}/status`, { signal });
    return data;
  }

  async leavePartySession(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<{ success: boolean; message: string }> {
    const { data } = await this.api.post<{ success: boolean; message: string }>(`/party/${sessionId}/leave`, {}, { signal });
    return data;
  }

  async startPartyPromptRound(sessionId: string, signal?: AbortSignal): Promise<QFStartPartyPromptResponse> {
    const { data } = await this.api.post<QFStartPartyPromptResponse>(
      `/party/${sessionId}/rounds/prompt`,
      {},
      { signal },
    );
    return data;
  }

  async startPartyCopyRound(sessionId: string, signal?: AbortSignal): Promise<QFStartPartyCopyResponse> {
    const { data } = await this.api.post<QFStartPartyCopyResponse>(
      `/party/${sessionId}/rounds/copy`,
      {},
      { signal },
    );
    return data;
  }

  async startPartyVoteRound(sessionId: string, signal?: AbortSignal): Promise<QFStartPartyVoteResponse> {
    const { data } = await this.api.post<QFStartPartyVoteResponse>(
      `/party/${sessionId}/rounds/vote`,
      {},
      { signal },
    );
    return data;
  }

  async submitPartyRound(
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

  async getPartyResults(sessionId: string, signal?: AbortSignal): Promise<QFPartyResultsResponse> {
    const { data } = await this.api.get<QFPartyResultsResponse>(`/party/${sessionId}/results`, { signal });
    return data;
  }

  async pingParty(sessionId: string, signal?: AbortSignal): Promise<QFPartyPingResponse> {
    const { data } = await this.api.post<QFPartyPingResponse>(`/party/${sessionId}/ping`, {}, { signal });
    return data;
  }

  async getOnlineUsers(signal?: AbortSignal): Promise<QFOnlineUsersResponse> {
    const { data } = await this.api.get<QFOnlineUsersResponse>('/users/online', { signal });
    return data;
  }

  async pingOnlineUser(username: string, signal?: AbortSignal): Promise<QFPingUserResponse> {
    const { data } = await this.api.post<QFPingUserResponse>(
      '/users/online/ping',
      { username },
      { signal },
    );
    return data;
  }
}

export const apiClient = new QuipFlipApiClient();
export const axiosInstance = apiClient.axiosInstance;

export default apiClient;
export { extractErrorMessage, clearStoredCredentials };
