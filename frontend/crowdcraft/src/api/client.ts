import axios from 'axios';
import type {
  ApiError,
  ApiInfo,
  AuthTokenResponse,
  GameStatus,
  HealthResponse,
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

export type { ApiError };
