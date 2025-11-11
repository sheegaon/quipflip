import { useState, useEffect, useCallback } from 'react';
import { useNetwork } from '../contexts/NetworkContext';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  version: string;
}

interface UseOfflineCacheOptions {
  staleTime?: number; // Time in ms before cache is considered stale (default: 5 minutes)
  cacheTime?: number; // Time in ms to keep cache (default: 30 minutes)
  enabled?: boolean; // Enable/disable the hook (default: true)
}

interface UseOfflineCacheResult<T> {
  data: T | null;
  isLoading: boolean;
  isStale: boolean;
  isOffline: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

const CACHE_VERSION = '1.0';

/**
 * Custom hook for offline-aware data caching
 *
 * Implements a cache-first strategy when offline:
 * - When online: fetches fresh data and updates cache
 * - When offline: returns cached data with stale indicator
 * - Automatically refetches when coming back online
 *
 * @param key Unique cache key
 * @param fetcher Async function to fetch data
 * @param options Cache configuration options
 * @returns Cache result with data, loading state, and refetch function
 */
export const useOfflineCache = <T>(
  key: string,
  fetcher: () => Promise<T>,
  options: UseOfflineCacheOptions = {}
): UseOfflineCacheResult<T> => {
  const {
    staleTime = 5 * 60 * 1000, // 5 minutes
    cacheTime = 30 * 60 * 1000, // 30 minutes
    enabled = true,
  } = options;

  const { isOffline } = useNetwork();
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isStale, setIsStale] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const cacheKey = `quipflip_cache_${key}`;

  /**
   * Get cached data from localStorage
   */
  const getCachedData = useCallback((): CacheEntry<T> | null => {
    try {
      const cached = localStorage.getItem(cacheKey);
      if (!cached) return null;

      const entry: CacheEntry<T> = JSON.parse(cached);

      // Check if cache has expired
      const age = Date.now() - entry.timestamp;
      if (age > cacheTime) {
        localStorage.removeItem(cacheKey);
        return null;
      }

      // Check if version matches
      if (entry.version !== CACHE_VERSION) {
        localStorage.removeItem(cacheKey);
        return null;
      }

      return entry;
    } catch (err) {
      console.error('Failed to read cache:', err);
      return null;
    }
  }, [cacheKey, cacheTime]);

  /**
   * Save data to cache
   */
  const setCachedData = useCallback(
    (newData: T): void => {
      try {
        const entry: CacheEntry<T> = {
          data: newData,
          timestamp: Date.now(),
          version: CACHE_VERSION,
        };
        localStorage.setItem(cacheKey, JSON.stringify(entry));
      } catch (err) {
        console.error('Failed to write cache:', err);
      }
    },
    [cacheKey]
  );

  /**
   * Check if cached data is stale
   */
  const isCacheStale = useCallback(
    (entry: CacheEntry<T>): boolean => {
      const age = Date.now() - entry.timestamp;
      return age > staleTime;
    },
    [staleTime]
  );

  /**
   * Fetch data from the server
   */
  const fetchData = useCallback(async (): Promise<void> => {
    if (!enabled) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await fetcher();
      setData(result);
      setCachedData(result);
      setIsStale(false);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to fetch data');
      setError(error);

      // If offline, try to use cached data
      if (isOffline) {
        const cached = getCachedData();
        if (cached) {
          setData(cached.data);
          setIsStale(true);
          console.log('Using cached data while offline');
        }
      }
    } finally {
      setIsLoading(false);
    }
  }, [enabled, fetcher, setCachedData, isOffline, getCachedData]);

  /**
   * Initialize: Load cached data or fetch fresh data
   */
  useEffect(() => {
    if (!enabled) return;

    const cached = getCachedData();

    if (cached) {
      // Use cached data immediately
      setData(cached.data);
      setIsStale(isCacheStale(cached));

      // If online and cache is stale, fetch fresh data in background
      if (!isOffline && isCacheStale(cached)) {
        fetchData();
      }
    } else {
      // No cache, fetch fresh data
      if (!isOffline) {
        fetchData();
      }
    }
  }, [key, enabled]); // Only run on key or enabled change

  /**
   * Refetch when coming back online
   */
  useEffect(() => {
    if (!isOffline && enabled && data !== null && isStale) {
      console.log('Back online! Refetching stale data...');
      fetchData();
    }
  }, [isOffline, enabled, data, isStale]); // Dependencies for auto-refetch

  /**
   * Manual refetch function
   */
  const refetch = useCallback(async (): Promise<void> => {
    await fetchData();
  }, [fetchData]);

  return {
    data,
    isLoading,
    isStale,
    isOffline,
    error,
    refetch,
  };
};

/**
 * Clear all offline caches
 */
export const clearOfflineCaches = (): void => {
  try {
    const keys = Object.keys(localStorage);
    const cacheKeys = keys.filter(key => key.startsWith('quipflip_cache_'));

    cacheKeys.forEach(key => {
      localStorage.removeItem(key);
    });

    console.log(`Cleared ${cacheKeys.length} offline cache entries`);
  } catch (error) {
    console.error('Failed to clear offline caches:', error);
  }
};

/**
 * Get cache statistics
 */
export const getCacheStats = (): { count: number; totalSize: number } => {
  try {
    const keys = Object.keys(localStorage);
    const cacheKeys = keys.filter(key => key.startsWith('quipflip_cache_'));

    let totalSize = 0;
    cacheKeys.forEach(key => {
      const item = localStorage.getItem(key);
      if (item) {
        totalSize += item.length;
      }
    });

    return {
      count: cacheKeys.length,
      totalSize,
    };
  } catch (error) {
    console.error('Failed to get cache stats:', error);
    return { count: 0, totalSize: 0 };
  }
};
