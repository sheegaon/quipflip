/**
 * Creates a frozen timer date for review mode.
 * Returns an ISO string representing a date 3 minutes from now.
 * This makes the timer appear frozen at 3:00.
 */
export const createFrozenTimerDate = (): string => {
  return new Date(Date.now() + 3 * 60 * 1000).toISOString();
};
