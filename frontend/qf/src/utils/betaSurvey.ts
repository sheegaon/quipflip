const SURVEY_DISMISSED_PREFIX = 'betaSurveyDismissed:';
const SURVEY_COMPLETED_PREFIX = 'betaSurveyCompleted:';

export const BETA_SURVEY_ID = 'beta_oct_2025';

const isBrowser = typeof window !== 'undefined';

const safeLocalStorage = () => {
  if (!isBrowser) return null;
  try {
    return window.localStorage;
  } catch (error) {
    console.warn('LocalStorage unavailable for beta survey tracking', error);
    return null;
  }
};

const storage = safeLocalStorage();

const buildKey = (prefix: string, playerId: string) => `${prefix}${playerId}`;

export const hasDismissedSurvey = (playerId: string): boolean => {
  if (!storage) return false;
  return storage.getItem(buildKey(SURVEY_DISMISSED_PREFIX, playerId)) === 'true';
};

export const markSurveyDismissed = (playerId: string): void => {
  if (!storage) return;
  storage.setItem(buildKey(SURVEY_DISMISSED_PREFIX, playerId), 'true');
};

export const clearSurveyDismissed = (playerId: string): void => {
  if (!storage) return;
  storage.removeItem(buildKey(SURVEY_DISMISSED_PREFIX, playerId));
};

export const hasCompletedSurvey = (playerId: string): boolean => {
  if (!storage) return false;
  return storage.getItem(buildKey(SURVEY_COMPLETED_PREFIX, playerId)) === 'true';
};

export const markSurveyCompleted = (playerId: string): void => {
  if (!storage) return;
  storage.setItem(buildKey(SURVEY_COMPLETED_PREFIX, playerId), 'true');
  storage.removeItem(buildKey(SURVEY_DISMISSED_PREFIX, playerId));
};
