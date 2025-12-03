import axios, { AxiosInstance } from 'axios';
import type {
  DashboardResponse,
  BalanceResponse,
  RoundAvailability,
  StartRoundResponse,
  SubmitGuessRequest,
  SubmitGuessResponse,
  RoundDetails,
  AbandonRoundResponse,
  PromptPreviewResponse,
  SeedPromptsRequest,
  SeedPromptsResponse,
  CorpusStats,
  PruneCorpusResponse,
} from './types';

const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE_URL = /\/tl($|\/)/.test(baseUrl) ? baseUrl : `${baseUrl}/tl`;

class ThinkLinkApiClient {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: API_BASE_URL,
      withCredentials: true,
      timeout: 30000,
    });
  }

  // ========================================================================
  // Player Endpoints
  // ========================================================================

  /**
   * Get player dashboard with balance and tutorial progress
   */
  async getDashboard(signal?: AbortSignal): Promise<DashboardResponse> {
    try {
      const { data } = await this.api.get<DashboardResponse>('/player/dashboard', { signal });
      return data;
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
      throw error;
    }
  }

  /**
   * Get player balance (wallet + vault)
   */
  async getBalance(signal?: AbortSignal): Promise<BalanceResponse> {
    try {
      const { data } = await this.api.get<BalanceResponse>('/player/balance', { signal });
      return data;
    } catch (error) {
      console.error('Failed to fetch balance:', error);
      throw error;
    }
  }

  /**
   * Logout the current player
   */
  async logout(): Promise<void> {
    try {
      await this.api.post('/player/logout', {});
    } catch (error) {
      console.error('Failed to logout:', error);
      throw error;
    }
  }

  // ========================================================================
  // Round Endpoints
  // ========================================================================

  /**
   * Check if player can start a new round and get game info
   */
  async checkRoundAvailability(signal?: AbortSignal): Promise<RoundAvailability> {
    try {
      const { data } = await this.api.get<RoundAvailability>('/rounds/available', { signal });
      return data;
    } catch (error) {
      console.error('Failed to check round availability:', error);
      throw error;
    }
  }

  /**
   * Start a new ThinkLink round
   */
  async startRound(signal?: AbortSignal): Promise<StartRoundResponse> {
    try {
      const { data } = await this.api.post<StartRoundResponse>('/rounds/start', {}, { signal, timeout: 10000 });
      return data;
    } catch (error) {
      const axiosError = error as ApiError;

      if (axiosError?.response?.status === 500) {
        console.error('Round creation failed with server error:', {
          status: axiosError.response.status,
          statusText: axiosError.response.statusText,
          data: axiosError.response.data,
          message: axiosError.message,
        });

        throw {
          ...axiosError,
          message: 'Server error starting round. Please try again in a moment.',
          isServerError: true,
        } as ApiError;
      }

      console.error('Round creation failed:', {
        status: axiosError?.response?.status,
        statusText: axiosError?.response?.statusText,
        data: axiosError?.response?.data,
        message: axiosError?.message,
      });

      throw error;
    }
  }

  /**
   * Submit a guess in an active round
   */
  async submitGuess(
    roundId: string,
    guessText: string,
    signal?: AbortSignal,
  ): Promise<SubmitGuessResponse> {
    try {
      const request: SubmitGuessRequest = { guess_text: guessText };
      const { data } = await this.api.post<SubmitGuessResponse>(`/rounds/${roundId}/guess`, request, {
        signal,
        timeout: 15000,
      });
      return data;
    } catch (error) {
      const axiosError = error as ApiError;

      // Log validation errors for debugging
      if (axiosError?.response?.status === 400) {
        console.debug('Guess validation failed:', {
          status: axiosError.response.status,
          detail: axiosError.response.data?.detail,
        });
      }

      throw error;
    }
  }

  /**
   * Get round details and guess history
   */
  async getRoundDetails(roundId: string, signal?: AbortSignal): Promise<RoundDetails> {
    try {
      const { data } = await this.api.get<RoundDetails>(`/rounds/${roundId}`, { signal });
      return data;
    } catch (error) {
      console.error('Failed to fetch round details:', error);
      throw error;
    }
  }

  /**
   * Abandon active round with partial refund
   */
  async abandonRound(roundId: string, signal?: AbortSignal): Promise<AbandonRoundResponse> {
    try {
      const { data } = await this.api.post<AbandonRoundResponse>(`/rounds/${roundId}/abandon`, {}, { signal });
      return data;
    } catch (error) {
      console.error('Failed to abandon round:', error);
      throw error;
    }
  }

  // ========================================================================
  // Game Info Endpoints
  // ========================================================================

  /**
   * Get a random prompt preview without starting a round
   */
  async previewPrompt(signal?: AbortSignal): Promise<PromptPreviewResponse> {
    try {
      const { data } = await this.api.get<PromptPreviewResponse>('/game/prompts/preview', { signal });
      return data;
    } catch (error) {
      console.error('Failed to fetch prompt preview:', error);
      throw error;
    }
  }

  // ========================================================================
  // Admin Endpoints
  // ========================================================================

  /**
   * Seed prompts from a list (admin only)
   */
  async seedPrompts(
    prompts: string[],
    signal?: AbortSignal,
  ): Promise<SeedPromptsResponse> {
    try {
      const request: SeedPromptsRequest = { prompts };
      const { data } = await this.api.post<SeedPromptsResponse>('/admin/prompts/seed', request, {
        signal,
        timeout: 30000,
      });
      return data;
    } catch (error) {
      console.error('Failed to seed prompts:', error);
      throw error;
    }
  }

  /**
   * Get corpus statistics for a prompt (admin only)
   */
  async getCorpusStats(promptId: string, signal?: AbortSignal): Promise<CorpusStats> {
    try {
      const { data } = await this.api.get<CorpusStats>(`/admin/corpus/${promptId}`, { signal });
      return data;
    } catch (error) {
      console.error('Failed to fetch corpus stats:', error);
      throw error;
    }
  }

  /**
   * Manually trigger corpus pruning for a prompt (admin only)
   */
  async pruneCorpus(promptId: string, signal?: AbortSignal): Promise<PruneCorpusResponse> {
    try {
      const { data } = await this.api.post<PruneCorpusResponse>(
        `/admin/corpus/${promptId}/prune`,
        {},
        { signal },
      );
      return data;
    } catch (error) {
      console.error('Failed to prune corpus:', error);
      throw error;
    }
  }

  // ========================================================================
  // Compatibility Stubs for MM/QF Header Component
  // ========================================================================

  /**
   * Get beta survey status (stub for TL compatibility)
   */
  async getBetaSurveyStatus(): Promise<{ has_submitted: boolean }> {
    // TL doesn't have survey endpoints - return false by default
    return { has_submitted: false };
  }

  /**
   * Get online users (stub endpoint)
   */
  async getOnlineUsers(signal?: AbortSignal): Promise<any> {
    try {
      const { data } = await this.api.get('/users/online', { signal });
      return data;
    } catch {
      return { online_users: [] };
    }
  }

  /**
   * Ping an online user (stub endpoint)
   */
  async pingOnlineUser(username: string, signal?: AbortSignal): Promise<any> {
    try {
      const { data } = await this.api.post(
        '/users/online/ping',
        { username },
        { signal },
      );
      return data;
    } catch {
      return { success: false };
    }
  }
}

export const apiClient = new ThinkLinkApiClient();

export default apiClient;
