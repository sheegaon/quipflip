import { BaseApiClient, extractErrorMessage, clearStoredCredentials } from '@crowdcraft/api/BaseApiClient.ts';
import type {
  ApiError,
  CreatePartySessionRequest,
  CreatePartySessionResponse,
  JoinPartySessionResponse,
  MarkReadyResponse,
  PartyListResponse,
  PartyPingResponse,
  PartyResultsResponse,
  PartySessionStatusResponse,
  StartPartyCopyResponse,
  StartPartyPromptResponse,
  StartPartySessionResponse,
  StartPartyVoteResponse,
  SubmitPartyRoundResponse,
} from '@crowdcraft/api/types.ts';

const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE_URL = /\/qf($|\/)/.test(baseUrl) ? baseUrl : `${baseUrl}/qf`;

class QuipFlipApiClient extends BaseApiClient {
  constructor() {
    super(API_BASE_URL);
  }

  async createPartySession(
    request: CreatePartySessionRequest = {},
    signal?: AbortSignal,
  ): Promise<CreatePartySessionResponse> {
    try {
      const { data } = await this.api.post<CreatePartySessionResponse>('/party/create', request, {
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

  async listActiveParties(signal?: AbortSignal): Promise<PartyListResponse> {
    const { data } = await this.api.get<PartyListResponse>('/party/list', { signal });
    return data;
  }

  async joinPartySessionById(sessionId: string, signal?: AbortSignal): Promise<JoinPartySessionResponse> {
    const { data } = await this.api.post<JoinPartySessionResponse>(`/party/${sessionId}/join`, {}, { signal });
    return data;
  }

  async joinPartySession(partyCode: string, signal?: AbortSignal): Promise<JoinPartySessionResponse> {
    const { data } = await this.api.post<JoinPartySessionResponse>('/party/join', { party_code: partyCode }, { signal });
    return data;
  }

  async markPartyReady(sessionId: string, signal?: AbortSignal): Promise<MarkReadyResponse> {
    const { data } = await this.api.post<MarkReadyResponse>(`/party/${sessionId}/ready`, {}, { signal });
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

  async startPartySession(sessionId: string, signal?: AbortSignal): Promise<StartPartySessionResponse> {
    const { data } = await this.api.post<StartPartySessionResponse>(`/party/${sessionId}/start`, {}, { signal });
    return data;
  }

  async getPartySessionStatus(sessionId: string, signal?: AbortSignal): Promise<PartySessionStatusResponse> {
    const { data } = await this.api.get<PartySessionStatusResponse>(`/party/${sessionId}/status`, { signal });
    return data;
  }

  async leavePartySession(
    sessionId: string,
    signal?: AbortSignal,
  ): Promise<{ success: boolean; message: string }> {
    const { data } = await this.api.post<{ success: boolean; message: string }>(`/party/${sessionId}/leave`, {}, { signal });
    return data;
  }

  async startPartyPromptRound(sessionId: string, signal?: AbortSignal): Promise<StartPartyPromptResponse> {
    const { data } = await this.api.post<StartPartyPromptResponse>(
      `/party/${sessionId}/rounds/prompt`,
      {},
      { signal },
    );
    return data;
  }

  async startPartyCopyRound(sessionId: string, signal?: AbortSignal): Promise<StartPartyCopyResponse> {
    const { data } = await this.api.post<StartPartyCopyResponse>(
      `/party/${sessionId}/rounds/copy`,
      {},
      { signal },
    );
    return data;
  }

  async startPartyVoteRound(sessionId: string, signal?: AbortSignal): Promise<StartPartyVoteResponse> {
    const { data } = await this.api.post<StartPartyVoteResponse>(
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
  ): Promise<SubmitPartyRoundResponse> {
    const { data } = await this.api.post<SubmitPartyRoundResponse>(
      `/party/${sessionId}/rounds/${roundId}/submit`,
      payload,
      { signal },
    );
    return data;
  }

  async getPartyResults(sessionId: string, signal?: AbortSignal): Promise<PartyResultsResponse> {
    const { data } = await this.api.get<PartyResultsResponse>(`/party/${sessionId}/results`, { signal });
    return data;
  }

  async pingParty(sessionId: string, signal?: AbortSignal): Promise<PartyPingResponse> {
    const { data } = await this.api.post<PartyPingResponse>(`/party/${sessionId}/ping`, {}, { signal });
    return data;
  }
}

export const apiClient = new QuipFlipApiClient();
export const axiosInstance = apiClient.axiosInstance;

export default apiClient;
export { extractErrorMessage, clearStoredCredentials };
