import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import type {
  AuthResponse,
  RegisterRequest,
  LoginRequest,
  UpgradeGuestRequest,
  StartSessionResponse,
  BalanceResponse,
  DashboardData,
  ClaimBonusResponse,
  SubmitBackronymRequest,
  SetStatusResponse,
  SubmitVoteRequest,
  ResultsResponse,
  PlayerStats,
  LeaderboardEntry,
  ValidateBackronymRequest,
  ValidateBackronymResponse,
  TutorialStatus,
  TutorialProgress,
  UpdateTutorialProgressResponse,
} from './types';
import { getStoredUsername, clearStoredUsername } from '../services/sessionDetection';

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

// Response interceptor for token refresh
irClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    // Extend config type to include our custom _retry flag
    interface RetryableConfig extends InternalAxiosRequestConfig {
      _retry?: boolean;
    }
    const originalRequest = (error.config as RetryableConfig | undefined);

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
  }
);

// Authentication API
export const authAPI = {
  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await irClient.post<AuthResponse>('/players', data);
    return response.data;
  },

  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await irClient.post<AuthResponse>('/players/login', data);
    return response.data;
  },

  createGuest: async (): Promise<AuthResponse> => {
    const response = await irClient.post<AuthResponse>('/players/guest');
    return response.data;
  },

  logout: async (): Promise<void> => {
    await irClient.post('/players/logout');
  },

  refresh: async (): Promise<void> => {
    await irClient.post('/players/refresh');
  },

  upgradeGuest: async (data: UpgradeGuestRequest): Promise<AuthResponse> => {
    const response = await irClient.post<AuthResponse>('/players/upgrade', data);
    return response.data;
  },
};

// Player API
export const playerAPI = {
  getBalance: async (): Promise<BalanceResponse> => {
    const response = await irClient.get<BalanceResponse>('/players/balance');
    return response.data;
  },

  getDashboard: async (): Promise<DashboardData> => {
    const response = await irClient.get<DashboardData>('/players/dashboard');
    return response.data;
  },

  claimDailyBonus: async (): Promise<ClaimBonusResponse> => {
    const response = await irClient.post<ClaimBonusResponse>('/players/claim-daily-bonus');
    return response.data;
  },

  getStatistics: async (): Promise<PlayerStats> => {
    const response = await irClient.get<PlayerStats>('/stats/player/statistics');
    return response.data;
  },
};

// Game API
export const gameAPI = {
  startSession: async (): Promise<StartSessionResponse> => {
    const response = await irClient.post<StartSessionResponse>('/game/start');
    return response.data;
  },

  submitBackronym: async (setId: string, data: SubmitBackronymRequest): Promise<void> => {
    await irClient.post(`/game/sets/${setId}/submit`, data);
  },

  validateBackronym: async (setId: string, data: ValidateBackronymRequest): Promise<ValidateBackronymResponse> => {
    const response = await irClient.post<ValidateBackronymResponse>(`/game/sets/${setId}/validate`, data);
    return response.data;
  },

  getSetStatus: async (setId: string): Promise<SetStatusResponse> => {
    const response = await irClient.get<SetStatusResponse>(`/game/sets/${setId}/status`);
    return response.data;
  },

  submitVote: async (setId: string, data: SubmitVoteRequest): Promise<void> => {
    await irClient.post(`/game/sets/${setId}/vote`, data);
  },

  getResults: async (setId: string): Promise<ResultsResponse> => {
    const response = await irClient.get<ResultsResponse>(`/game/sets/${setId}/results`);
    return response.data;
  },
};

export const tutorialAPI = {
  getTutorialStatus: async (signal?: AbortSignal): Promise<TutorialStatus> => {
    const response = await irClient.get<TutorialStatus>('/player/tutorial/status', { signal });
    return response.data;
  },

  updateTutorialProgress: async (
    progress: TutorialProgress,
    signal?: AbortSignal,
  ): Promise<UpdateTutorialProgressResponse> => {
    const response = await irClient.post<UpdateTutorialProgressResponse>(
      '/player/tutorial/progress',
      { progress },
      { signal },
    );
    return response.data;
  },

  resetTutorial: async (signal?: AbortSignal): Promise<TutorialStatus> => {
    const response = await irClient.post<TutorialStatus>('/player/tutorial/reset', {}, { signal });
    return response.data;
  },
};

// Leaderboard API
export const leaderboardAPI = {
  getCreatorLeaderboard: async (): Promise<LeaderboardEntry[]> => {
    const response = await irClient.get<LeaderboardEntry[]>('/leaderboard/leaderboards/creators');
    return response.data;
  },

  getVoterLeaderboard: async (): Promise<LeaderboardEntry[]> => {
    const response = await irClient.get<LeaderboardEntry[]>('/leaderboard/leaderboards/voters');
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
