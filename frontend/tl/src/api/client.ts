import { BaseApiClient, extractErrorMessage, clearStoredCredentials } from '@crowdcraft/api/BaseApiClient.ts';
import type {
  ApiError,
  OnlineUsersResponse,
  PingUserResponse,
} from '@crowdcraft/api/types.ts';

const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_BASE_URL = /\/tl($|\/)/.test(baseUrl) ? baseUrl : `${baseUrl}/tl`;

export const axiosInstance = apiClient.axiosInstance;
