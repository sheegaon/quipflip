import { GUEST_CREDENTIALS_KEY } from './storageKeys';

export interface GuestCredentials {
  username: string;
  email?: string | null;
  password?: string | null;
  timestamp?: number;
}

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
};

const normalizeGuestCredentials = (value: unknown): GuestCredentials | null => {
  if (!isRecord(value)) {
    return null;
  }

  const username = typeof value.username === 'string' ? value.username.trim() : '';
  if (!username) {
    return null;
  }

  const email = typeof value.email === 'string' ? value.email.trim() : undefined;
  const password = typeof value.password === 'string' ? value.password : undefined;
  const timestamp = typeof value.timestamp === 'number' ? value.timestamp : undefined;

  return {
    username,
    email: email || undefined,
    password,
    timestamp,
  };
};

export const getStoredGuestCredentials = (storageKey: string = GUEST_CREDENTIALS_KEY): GuestCredentials | null => {
  if (typeof window === 'undefined') {
    return null;
  }

  const rawValue = window.localStorage.getItem(storageKey);
  if (!rawValue) {
    return null;
  }

  try {
    return normalizeGuestCredentials(JSON.parse(rawValue));
  } catch {
    return null;
  }
};

export const setStoredGuestCredentials = (
  credentials: GuestCredentials,
  storageKey: string = GUEST_CREDENTIALS_KEY,
): void => {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(storageKey, JSON.stringify(credentials));
};

export const clearStoredGuestCredentials = (storageKey: string = GUEST_CREDENTIALS_KEY): void => {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.removeItem(storageKey);
};
