import axios, { AxiosError } from 'axios';
import type {
  IRAuthResponse,
  IRRegisterRequest,
  IRLoginRequest,
  IRUpgradeGuestRequest,
  IRStartSessionResponse,
  IRBalanceResponse,
  IRDashboardData,
  IRClaimBonusResponse,
  IRSubmitBackronymRequest,
  IRSetStatusResponse,
  IRSubmitVoteRequest,
  IRResultsResponse,
  IRPlayerStats,
  IRLeaderboardEntry,
  IRValidateBackronymRequest,
  IRValidateBackronymResponse,
  IRTutorialStatus,
  IRTutorialProgress,
  IRUpdateTutorialProgressResponse,
} from '@crowdcraft/api/types.ts';
import { clearStoredUsername } from '../services/sessionDetection';

// Base URL - configure based on environment
const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_URL = /\/ir($|\/)/.test(baseUrl) ? baseUrl : `${baseUrl}/ir`;

// Create axios instance
export const irClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,  // Send cookies for authentication
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for token refresh
irClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    // Don't log or process canceled requests - they're intentional
    const isCanceled =
      error.code === 'ERR_CANCELED' ||
      error.name === 'CanceledError' ||
      error.message === 'canceled' ||
      error.message?.includes('cancel');

    if (isCanceled) {
      return Promise.reject(error);
    }

    // IR backend does not expose a refresh endpoint; clear any cached session and surface the error
    if (error.response?.status === 401) {
      clearStoredUsername();
    }

    return Promise.reject(error);
  },
);

// Authentication API
export const authAPI = {
  register: async (data: IRRegisterRequest): Promise<IRAuthResponse> => {
    const response = await irClient.post<IRAuthResponse>('/players', data);
    return response.data;
  },

  login: async (data: IRLoginRequest): Promise<IRAuthResponse> => {
    const response = await irClient.post<IRAuthResponse>('/players/login', data);
    return response.data;
  },

  createGuest: async (): Promise<IRAuthResponse> => {
    const response = await irClient.post<IRAuthResponse>('/players/guest');
    return response.data;
  },

  logout: async (): Promise<void> => {
    await irClient.post('/players/logout');
  },

  refresh: async (): Promise<void> => {
    await irClient.post('/players/refresh');
  },

  upgradeGuest: async (data: IRUpgradeGuestRequest): Promise<IRAuthResponse> => {
    const response = await irClient.post<IRAuthResponse>('/players/upgrade', data);
    return response.data;
  },
};

// IRPlayer API
export const playerAPI = {
  getBalance: async (): Promise<IRBalanceResponse> => {
    const response = await irClient.get<IRBalanceResponse>('/players/balance');
    return response.data;
  },

  getDashboard: async (): Promise<IRDashboardData> => {
    const response = await irClient.get<IRDashboardData>('/players/dashboard');
    return response.data;
  },

  claimDailyBonus: async (): Promise<IRClaimBonusResponse> => {
    const response = await irClient.post<IRClaimBonusResponse>('/players/claim-daily-bonus');
    return response.data;
  },

  getStatistics: async (): Promise<IRPlayerStats> => {
    const response = await irClient.get<IRPlayerStats>('/stats/player/statistics');
    return response.data;
  },
};

// Game API
export const gameAPI = {
  startSession: async (): Promise<IRStartSessionResponse> => {
    const response = await irClient.post<IRStartSessionResponse>('/game/start');
    return response.data;
  },

  submitBackronym: async (setId: string, data: IRSubmitBackronymRequest): Promise<void> => {
    await irClient.post(`/game/sets/${setId}/submit`, data);
  },

  validateBackronym: async (setId: string, data: IRValidateBackronymRequest): Promise<IRValidateBackronymResponse> => {
    const response = await irClient.post<IRValidateBackronymResponse>(`/game/sets/${setId}/validate`, data);
    return response.data;
  },

  getSetStatus: async (setId: string): Promise<IRSetStatusResponse> => {
    const response = await irClient.get<IRSetStatusResponse>(`/game/sets/${setId}/status`);
    return response.data;
  },

  submitVote: async (setId: string, data: IRSubmitVoteRequest): Promise<void> => {
    await irClient.post(`/game/sets/${setId}/vote`, data);
  },

  getResults: async (setId: string): Promise<IRResultsResponse> => {
    const response = await irClient.get<IRResultsResponse>(`/game/sets/${setId}/results`);
    return response.data;
  },
};

export const tutorialAPI = {
  getTutorialStatus: async (signal?: AbortSignal): Promise<IRTutorialStatus> => {
    const response = await irClient.get<IRTutorialStatus>('/player/tutorial/status', { signal });
    return response.data;
  },

  updateTutorialProgress: async (
    progress: IRTutorialProgress,
    signal?: AbortSignal,
  ): Promise<IRUpdateTutorialProgressResponse> => {
    const response = await irClient.post<IRUpdateTutorialProgressResponse>(
      '/player/tutorial/progress',
      { progress },
      { signal },
    );
    return response.data;
  },

  resetTutorial: async (signal?: AbortSignal): Promise<IRTutorialStatus> => {
    const response = await irClient.post<IRTutorialStatus>('/player/tutorial/reset', {}, { signal });
    return response.data;
  },
};

// Leaderboard API
export const leaderboardAPI = {
  getCreatorLeaderboard: async (): Promise<IRLeaderboardEntry[]> => {
    const response = await irClient.get<IRLeaderboardEntry[]>('/leaderboard/leaderboards/creators');
    return response.data;
  },

  getVoterLeaderboard: async (): Promise<IRLeaderboardEntry[]> => {
    const response = await irClient.get<IRLeaderboardEntry[]>('/leaderboard/leaderboards/voters');
    return response.data;
  },
};

export default irClient;

// Settings API
export const settingsAPI = {
  changePassword: async (data: { current_password: string; new_password: string }): Promise<{ message: string }> => {
    const response = await irClient.post<{ message: string }>('/settings/password', data);
    return response.data;
  },

  updateEmail: async (data: { new_email: string; password: string }): Promise<{ email: string }> => {
    const response = await irClient.post<{ email: string }>('/settings/email', data);
    return response.data;
  },

  changeUsername: async (data: { new_username: string; password: string }): Promise<{ username: string; message: string }> => {
    const response = await irClient.post<{ username: string; message: string }>('/settings/username', data);
    return response.data;
  },

  deleteAccount: async (data: { password: string; confirmation: string }): Promise<void> => {
    await irClient.post('/settings/delete-account', data);
  },
};
