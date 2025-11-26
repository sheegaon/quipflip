import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import type { PracticePhraseset } from '../api/types';

interface UsePracticePhrasesetSessionResult {
  phraseset: PracticePhraseset | null;
  loading: boolean;
  error: string | null;
  clearSession: () => void;
}

const STORAGE_KEY = 'quipflip_practice_copy_phraseset';

/**
 * Hook that manages practice phraseset with session storage for copy rounds only.
 *
 * - If a phraseset is already in session storage, it returns that (for copy2 to reuse copy1's data)
 * - Otherwise, it fetches a new random phraseset and stores it (for copy1)
 * - Call clearSession() when the copy flow is complete to fetch a new one next time
 */
export const usePracticePhrasesetSession = (): UsePracticePhrasesetSessionResult => {
  const [phraseset, setPhraseset] = useState<PracticePhraseset | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const fetchOrLoadPhraseset = async () => {
      try {
        setLoading(true);
        setError(null);

        // Try to load from session storage first
        const stored = sessionStorage.getItem(STORAGE_KEY);
        if (stored) {
          try {
            const parsed = JSON.parse(stored) as PracticePhraseset;
            if (!controller.signal.aborted) {
              setPhraseset(parsed);
              setLoading(false);
            }
            return;
          } catch (parseError) {
            console.warn('Failed to parse stored phraseset, fetching new one:', parseError);
            sessionStorage.removeItem(STORAGE_KEY);
          }
        }

        // If not in storage, fetch a new one
        const data = await apiClient.getRandomPracticePhraseset(controller.signal);

        if (!controller.signal.aborted) {
          setPhraseset(data);
          // Store in session storage for subsequent pages
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          console.error('Failed to fetch practice phraseset:', err);
          setError('Unable to load practice round. Please try again.');
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchOrLoadPhraseset();

    return () => {
      controller.abort();
    };
  }, []);

  const clearSession = () => {
    sessionStorage.removeItem(STORAGE_KEY);
  };

  return { phraseset, loading, error, clearSession };
};
