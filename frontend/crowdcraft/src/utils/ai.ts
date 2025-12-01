export const AI_EMAIL_DOMAIN = '@quipflip.internal';

type AiDetectable = {
  is_ai?: boolean;
  email?: string;
};

/**
 * Detect whether a player should be treated as AI.
 * Falls back to the email domain if the backend flag is missing.
 */
export const isAiPlayer = (player?: AiDetectable | null): boolean => {
  if (!player) return false;

  if (player.is_ai) {
    return true;
  }

  return player.email?.toLowerCase().endsWith(AI_EMAIL_DOMAIN) ?? false;
};
