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

  if (dateOnlyPattern.test(value)) {
    return `${value}T00:00:00Z`;
  }

  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{1,9})?$/.test(value)) {
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

  if (typeof value !== 'string') {
    return null;
  }

  const sanitised = sanitiseDateString(value);
  const parsed = new Date(sanitised);

  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

type BaseFormatOptions = {
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

type DateOnlyFormatOptions = {
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

