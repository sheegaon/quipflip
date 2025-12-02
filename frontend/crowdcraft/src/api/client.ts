import axios from 'axios';
import type {
  ApiError,
  ApiInfo,
  AuthTokenResponse,
  GameStatus,
  HealthResponse,
  Player,
  SuggestUsernameResponse,
  WsAuthTokenResponse,
} from './types';

// Base URL points at the API root without any game-specific prefix.
const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const api = axios.create({
  baseURL: baseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

export const axiosInstance = api;

export const login = async (email: string, password: string) => {
  const response = await api.post<AuthTokenResponse>('/auth/login', { email, password });
  return response.data;
};

export const loginWithUsername = async (username: string, password: string) => {
  const response = await api.post<AuthTokenResponse>('/auth/login/username', {
    username,
    password,
  });
  return response.data;
};

export const refreshToken = async () => {
  const response = await api.post<AuthTokenResponse>('/auth/refresh', {});
  return response.data;
};

export const logout = async (refreshTokenValue?: string) => {
  const payload = refreshTokenValue ? { refresh_token: refreshTokenValue } : {};
  await api.post<void>('/auth/logout', payload);
};

export const suggestUsername = async () => {
  const response = await api.get<SuggestUsernameResponse>('/auth/suggest-username');
  return response.data;
};

export const fetchWsToken = async () => {
  const response = await api.get<WsAuthTokenResponse>('/auth/ws-token');
  return response.data;
};

export const fetchHealth = async () => {
  const response = await api.get<HealthResponse>('/health');
  return response.data;
};

export const fetchStatus = async () => {
  const response = await api.get<GameStatus>('/status');
  return response.data;
};

export const fetchApiInfo = async () => {
  const response = await api.get<ApiInfo>('/');
  return response.data;
};

// Export apiClient stub for compatibility with shared services (e.g., sessionDetection)
// Project-specific clients (qf, mm) override this with their full implementations
// This stub exists only to satisfy TypeScript; it should never be called in practice
export const apiClient = {
  getBalance: async (_signal?: AbortSignal): Promise<Player> => {
    throw new Error('getBalance must be implemented by game-specific client (qf/mm)');
  },
  setSession: (_username: string | null): void => {
    throw new Error('setSession must be implemented by game-specific client (qf/mm)');
  },
  clearSession: (): void => {
    throw new Error('clearSession must be implemented by game-specific client (qf/mm)');
  },
  getStoredUsername: (): string | null => {
    throw new Error('getStoredUsername must be implemented by game-specific client (qf/mm)');
  },
  refreshToken: async (_signal?: AbortSignal): Promise<AuthTokenResponse> => {
    throw new Error('refreshToken must be implemented by game-specific client (qf/mm)');
  },
};

export type { ApiError };
