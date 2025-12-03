const userTimeZone =
  typeof Intl !== 'undefined' && typeof Intl.DateTimeFormat === 'function'
    ? Intl.DateTimeFormat().resolvedOptions().timeZone
    : undefined;

const hasExplicitTimeZone = (value: string) => /([zZ]|[+-]\d{2}:\d{2})$/.test(value);

const dateOnlyPattern = /^\d{4}-\d{2}-\d{2}$/;

const isoWithoutZonePattern =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?$/;

type DateLike = string | number | Date | null | undefined;

const sanitiseDateString = (rawValue: string) => {
  let value = rawValue.trim();

  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?$/.test(value)) {
    value = value.replace(' ', 'T');
  }

  if (isoWithoutZonePattern.test(value) && !hasExplicitTimeZone(value)) {
    return `${value}Z`;
  }

  return value;
};

export const parseDateLike = (value: DateLike): Date | null => {
  if (value == null) {
    return null;
  }

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  if (typeof value === 'number') {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }



  const trimmed = value.trim();

  if (dateOnlyPattern.test(trimmed)) {
    const parts = trimmed.split('-').map(Number);

    if (parts.length !== 3 || parts.some(Number.isNaN)) {
      return null;
    }

    const [year, month, day] = parts;
    const date = new Date(year, month - 1, day);

    return Number.isNaN(date.getTime()) ? null : date;
  }

  const sanitised = sanitiseDateString(trimmed);
  const parsed = new Date(sanitised);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

export type BaseFormatOptions = {
  fallback?: string;
  includeSeconds?: boolean;
};

export const formatDateTimeInUserZone = (
  value: DateLike,
  options: BaseFormatOptions = {},
) => {
  const { fallback = '—', includeSeconds = false } = options;
  const date = parseDateLike(value);

  if (!date) {
    return fallback;
  }

  const formatOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  };

  if (includeSeconds) {
    formatOptions.second = '2-digit';
  }

  if (userTimeZone) {
    formatOptions.timeZone = userTimeZone;
  }

  return date.toLocaleString(undefined, formatOptions);
};

export type DateOnlyFormatOptions = {
  fallback?: string;
};

export const formatDateInUserZone = (
  value: DateLike,
  options: DateOnlyFormatOptions = {},
) => {
  const { fallback = '—' } = options;
  const date = parseDateLike(value);

  if (!date) {
    return fallback;
  }

  const formatOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  };

  if (userTimeZone) {
    formatOptions.timeZone = userTimeZone;
  }

  return date.toLocaleDateString(undefined, formatOptions);
};

// Compatibility helpers for existing code
export const formatDateTime = (value: DateLike): string =>
  formatDateTimeInUserZone(value, { fallback: '—' });

export const formatDate = (value: DateLike): string =>
  formatDateInUserZone(value, { fallback: '—' });

export const formatTime = (value: DateLike): string => {
  const date = parseDateLike(value);
  if (!date) return '—';

  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: userTimeZone,
  });
};

export const formatRelativeTime = (value: DateLike): string => {
  const date = parseDateLike(value);
  if (!date) return '—';

  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  return formatDate(value);
};

export const getRemainingTime = (
  targetDateString: string,
): {
  minutes: number;
  seconds: number;
  isExpired: boolean;
} => {
  const target = parseDateLike(targetDateString);
  if (!target) {
    return { minutes: 0, seconds: 0, isExpired: true };
  }

  const now = new Date();
  const diffMs = target.getTime() - now.getTime();

  if (diffMs <= 0) {
    return { minutes: 0, seconds: 0, isExpired: true };
  }

  const totalSeconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  return { minutes, seconds, isExpired: false };
};

export const formatCountdown = (minutes: number, seconds: number): string => {
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
};
