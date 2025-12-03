import { useState, useEffect } from 'react';
import apiClient from '../api/client.ts';
import type { QFPracticePhraseset } from '../api/types.ts';

interface UsePracticePhrasesetResult {
  phraseset: QFPracticePhraseset | null;
  loading: boolean;
  error: string | null;
}

export const usePracticePhraseset = (): UsePracticePhrasesetResult => {
  const [phraseset, setPhraseset] = useState<QFPracticePhraseset | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const fetchPracticeData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getRandomPracticePhraseset(controller.signal);

        // Only update state if the component is still mounted
        if (!controller.signal.aborted) {
          setPhraseset(data);
        }
      } catch (err) {
        // Only update state if the component is still mounted and the error wasn't from abort
        if (!controller.signal.aborted) {
          console.error('Failed to fetch practice phraseset:', err);
          setError('Unable to load practice round. Please try again.');
        }
      } finally {
        // Only update state if the component is still mounted
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchPracticeData();

    // Cleanup function - abort the request if component unmounts
    return () => {
      controller.abort();
    };
  }, []);

  return { phraseset, loading, error };
};
