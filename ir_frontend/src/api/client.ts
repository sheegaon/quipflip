import axios, { AxiosError } from 'axios';
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
} from './types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/ir';

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
    const originalRequest = error.config;

    // If we get a 401 and haven't already tried to refresh
    if (error.response?.status === 401 && originalRequest && !(originalRequest as any)._retry) {
      (originalRequest as any)._retry = true;

      try {
        // Try to refresh the token
        await irClient.post('/auth/refresh');

        // Retry the original request
        return irClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed, redirect to login
        window.location.href = '/';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Authentication API
export const authAPI = {
  register: async (data: RegisterRequest): Promise<AuthResponse> => {
    const response = await irClient.post<AuthResponse>('/auth/register', data);
    return response.data;
  },

  login: async (data: LoginRequest): Promise<AuthResponse> => {
    const response = await irClient.post<AuthResponse>('/auth/login', data);
    return response.data;
  },

  createGuest: async (): Promise<AuthResponse> => {
    const response = await irClient.post<AuthResponse>('/auth/guest');
    return response.data;
  },

  logout: async (): Promise<void> => {
    await irClient.post('/auth/logout');
  },

  refresh: async (): Promise<void> => {
    await irClient.post('/auth/refresh');
  },

  upgradeGuest: async (data: UpgradeGuestRequest): Promise<AuthResponse> => {
    const response = await irClient.post<AuthResponse>('/auth/upgrade', data);
    return response.data;
  },
};

// Player API
export const playerAPI = {
  getBalance: async (): Promise<BalanceResponse> => {
    const response = await irClient.get<BalanceResponse>('/player/balance');
    return response.data;
  },

  getDashboard: async (): Promise<DashboardData> => {
    const response = await irClient.get<DashboardData>('/player/dashboard');
    return response.data;
  },

  claimDailyBonus: async (): Promise<ClaimBonusResponse> => {
    const response = await irClient.post<ClaimBonusResponse>('/player/claim-daily-bonus');
    return response.data;
  },

  getStatistics: async (): Promise<PlayerStats> => {
    const response = await irClient.get<PlayerStats>('/player/statistics');
    return response.data;
  },
};

// Game API
export const gameAPI = {
  startSession: async (): Promise<StartSessionResponse> => {
    const response = await irClient.post<StartSessionResponse>('/start');
    return response.data;
  },

  submitBackronym: async (setId: string, data: SubmitBackronymRequest): Promise<void> => {
    await irClient.post(`/sets/${setId}/submit`, data);
  },

  getSetStatus: async (setId: string): Promise<SetStatusResponse> => {
    const response = await irClient.get<SetStatusResponse>(`/sets/${setId}/status`);
    return response.data;
  },

  submitVote: async (setId: string, data: SubmitVoteRequest): Promise<void> => {
    await irClient.post(`/sets/${setId}/vote`, data);
  },

  getResults: async (setId: string): Promise<ResultsResponse> => {
    const response = await irClient.get<ResultsResponse>(`/sets/${setId}/results`);
    return response.data;
  },
};

// Leaderboard API
export const leaderboardAPI = {
  getCreatorLeaderboard: async (): Promise<LeaderboardEntry[]> => {
    const response = await irClient.get<LeaderboardEntry[]>('/leaderboards/creators');
    return response.data;
  },

  getVoterLeaderboard: async (): Promise<LeaderboardEntry[]> => {
    const response = await irClient.get<LeaderboardEntry[]>('/leaderboards/voters');
    return response.data;
  },
};

export default irClient;
