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

    // If we get a 401 and haven't already tried to refresh
    // AND the request is not already an auth endpoint (prevent infinite loops)
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      originalRequest.url !== '/auth/login' &&
      originalRequest.url !== '/auth/refresh' &&
      originalRequest.url !== '/auth/logout'
    ) {
      originalRequest._retry = true;

      if (isRefreshing) {
        // Queue the request while refresh is in progress
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => irClient(originalRequest))
          .catch((err) => Promise.reject(err));
      }

      isRefreshing = true;

      try {
        // Try to refresh the token
        await irClient.post('/auth/refresh');
        processQueue(null);

        // Retry the original request
        return irClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed, redirect to login
        processQueue(refreshError);
        window.location.href = '/';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
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

  validateBackronym: async (setId: string, data: ValidateBackronymRequest): Promise<ValidateBackronymResponse> => {
    const response = await irClient.post<ValidateBackronymResponse>(`/sets/${setId}/validate`, data);
    return response.data;
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
