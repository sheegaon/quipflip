import type { PhrasesetSummary } from '../api/types';

/**
 * Get a unique ID for a phraseset summary.
 * For copy rounds, uses copy_round_id to ensure uniqueness when a player has multiple copies.
 * For prompts or fallback, uses phraseset_id or prompt_round_id.
 */
export const getUniqueIdForSummary = (summary: PhrasesetSummary): string => {
  // Debug logging to see what we're getting
  if (summary.your_role === 'copy') {
    console.log('[phrasesetHelpers] Copy round data:', {
      copy_round_id: summary.copy_round_id,
      phraseset_id: summary.phraseset_id,
      prompt_round_id: summary.prompt_round_id,
      your_phrase: summary.your_phrase,
    });
  }

  // For copy rounds, use copy_round_id if available (ensures uniqueness for multiple copies)
  if (summary.your_role === 'copy' && summary.copy_round_id) {
    return summary.copy_round_id;
  }
  // For prompts or fallback, use phraseset_id or prompt_round_id
  return summary.phraseset_id ?? summary.prompt_round_id;
};
