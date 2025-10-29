import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiClient from '../api/client';
import { getActionErrorMessage } from '../utils/errorMessages';
import { gameContextLogger } from '../utils/logger';
import { buildPhrasesetListKey, type PhrasesetListKeyParams } from '../utils/gameKeys';
import type { 
  PendingResult, 
  PhrasesetListResponse, 
  PhrasesetDetails as PhrasesetDetailsType, 
  PhrasesetResults 
} from '../api/types';

type PlayerPhrasesetParams = PhrasesetListKeyParams;

interface PhrasesetListCacheEntry {
  params: PlayerPhrasesetParams;
  data: PhrasesetListResponse | null;
  loading: boolean;
  error: string | null;
  lastFetched: number | null;
}

interface PhrasesetDetailsCacheEntry {
  data: PhrasesetDetailsType | null;
  loading: boolean;
  error: string | null;
  lastFetched: number | null;
}

interface PhrasesetResultsCacheEntry {
  data: PhrasesetResults | null;
  loading: boolean;
  error: string | null;
  lastFetched: number | null;
}

interface StatisticsData {
  totalRounds: number;
  totalEarnings: number;
  averageScore: number;
  bestPerformance: any;
  recentActivity: any[];
}

interface ResultsState {
  pendingResults: PendingResult[];
  viewedResultIds: Set<string>;
  playerPhrasesets: Record<string, PhrasesetListCacheEntry>;
  phrasesetDetails: Record<string, PhrasesetDetailsCacheEntry>;
  phrasesetResults: Record<string, PhrasesetResultsCacheEntry>;
  statistics: StatisticsData | null;
  statisticsLoading: boolean;
  statisticsError: string | null;
  lastStatisticsUpdate: number | null;
}

interface ResultsActions {
  refreshPlayerPhrasesets: (
    params?: PlayerPhrasesetParams,
    options?: { force?: boolean }
  ) => Promise<PhrasesetListResponse | null>;
  refreshPhrasesetDetails: (
    phrasesetId: string,
    options?: { force?: boolean }
  ) => Promise<PhrasesetDetailsType | null>;
  refreshPhrasesetResults: (
    phrasesetId: string,
    options?: { force?: boolean }
  ) => Promise<PhrasesetResults | null>;
  getStatistics: (signal?: AbortSignal) => Promise<any>;
  markResultsViewed: (phrasesetIds: string[]) => void;
  clearResultsCache: () => void;
  setPendingResults: (results: PendingResult[]) => void;
}

interface ResultsContextType {
  state: ResultsState;
  actions: ResultsActions;
}

const ResultsContext = createContext<ResultsContextType | undefined>(undefined);

export const ResultsProvider: React.FC<{ 
  children: React.ReactNode;
  isAuthenticated: boolean;
}> = ({ children, isAuthenticated }) => {
  const [resultsState, setResultsState] = useState<ResultsState>(() => {
    // Initialize viewedResultIds from sessionStorage
    let initialViewedResultIds = new Set<string>();
    
    if (typeof window !== 'undefined') {
      try {
        const stored = window.sessionStorage.getItem('viewedResultIds');
        if (stored) {
          const parsed: unknown = JSON.parse(stored);
          if (Array.isArray(parsed)) {
            initialViewedResultIds = new Set(parsed.filter((value): value is string => typeof value === 'string'));
          }
        }
      } catch (err) {
        gameContextLogger.warn('❌ Failed to restore viewed results from sessionStorage:', err);
      }
    }

    return {
      pendingResults: [],
      viewedResultIds: initialViewedResultIds,
      playerPhrasesets: {},
      phrasesetDetails: {},
      phrasesetResults: {},
      statistics: null,
      statisticsLoading: false,
      statisticsError: null,
      lastStatisticsUpdate: null,
    };
  });

  // Persist viewedResultIds to sessionStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;

    try {
      window.sessionStorage.setItem('viewedResultIds', JSON.stringify(Array.from(resultsState.viewedResultIds)));
      gameContextLogger.debug('💾 Viewed results persisted to sessionStorage');
    } catch (err) {
      gameContextLogger.warn('❌ Failed to persist viewed results to sessionStorage:', err);
    }
  }, [resultsState.viewedResultIds]);

  // Sync viewedResultIds with pendingResults
  useEffect(() => {
    setResultsState(prev => {
      const pendingResults = prev.pendingResults;
      const previous = prev.viewedResultIds;
      
      // If no pending results, clear all viewed IDs
      if (pendingResults.length === 0) {
        return previous.size === 0 ? prev : { ...prev, viewedResultIds: new Set() };
      }

      // Create new set starting from server-side viewed state
      const next = new Set<string>();
      
      // Add all result IDs that are marked as viewed on server or were previously viewed locally
      pendingResults.forEach((result) => {
        const id = result.phraseset_id;
        if (id && (result.result_viewed || previous.has(id))) {
          next.add(id);
        }
      });

      // Return previous state if no changes to avoid unnecessary re-renders
      const hasChanges = next.size !== previous.size || !Array.from(next).every(id => previous.has(id));
      if (hasChanges) {
        gameContextLogger.debug('🔄 Updated viewed result IDs:', {
          previous: previous.size,
          new: next.size,
          added: Array.from(next).filter(id => !previous.has(id)),
          removed: Array.from(previous).filter(id => !next.has(id))
        });
        return { ...prev, viewedResultIds: next };
      }
      
      return prev; // No changes, return same state object
    });
  }, [resultsState.pendingResults]); // Add dependency on pendingResults

  const refreshPlayerPhrasesets = useCallback(async (
    params: PlayerPhrasesetParams = {},
    options: { force?: boolean } = {},
  ): Promise<PhrasesetListResponse | null> => {
    gameContextLogger.debug('📊 ResultsContext refreshPlayerPhrasesets called:', { params, options });
    
    const key = buildPhrasesetListKey(params);
    const cached = resultsState.playerPhrasesets[key];

    const token = await apiClient.ensureAccessToken();
    if (!token) {
      gameContextLogger.warn('❌ No valid token for player phrasesets refresh');
      setResultsState(prev => ({
        ...prev,
        playerPhrasesets: {
          ...prev.playerPhrasesets,
          [key]: {
            params,
            data: cached?.data ?? null,
            loading: false,
            error: 'Authentication required. Please log in again.',
            lastFetched: cached?.lastFetched ?? null,
          }
        }
      }));
      return null;
    }

    if (cached?.data && !options.force) {
      gameContextLogger.debug('✅ Using cached player phrasesets data');
      return cached.data;
    }

    gameContextLogger.debug('🔄 Setting player phrasesets loading state');
    setResultsState(prev => ({
      ...prev,
      playerPhrasesets: {
        ...prev.playerPhrasesets,
        [key]: {
          params,
          data: cached?.data ?? null,
          loading: true,
          error: null,
          lastFetched: cached?.lastFetched ?? null,
        }
      }
    }));

    try {
      gameContextLogger.debug('📞 Calling apiClient.getPlayerPhrasesets...');
      const data = await apiClient.getPlayerPhrasesets(params);
      gameContextLogger.debug('✅ Player phrasesets data received:', {
        totalPhrasesets: data.phrasesets?.length || 0
      });

      setResultsState(prev => ({
        ...prev,
        playerPhrasesets: {
          ...prev.playerPhrasesets,
          [key]: {
            params,
            data,
            loading: false,
            error: null,
            lastFetched: Date.now(),
          }
        }
      }));
      
      return data;
    } catch (err) {
      gameContextLogger.error('❌ Player phrasesets refresh failed:', err);
      const errorMessage = getActionErrorMessage('load-tracking', err);
      setResultsState(prev => ({
        ...prev,
        playerPhrasesets: {
          ...prev.playerPhrasesets,
          [key]: {
            params,
            data: cached?.data ?? null,
            loading: false,
            error: errorMessage,
            lastFetched: cached?.lastFetched ?? null,
          }
        }
      }));
      throw err;
    }
  }, [resultsState.playerPhrasesets]);

  const refreshPhrasesetDetails = useCallback(async (
    phrasesetId: string,
    options: { force?: boolean } = {},
  ): Promise<PhrasesetDetailsType | null> => {
    gameContextLogger.debug('📊 ResultsContext refreshPhrasesetDetails called:', { phrasesetId, options });
    
    const cached = resultsState.phrasesetDetails[phrasesetId];

    const token = await apiClient.ensureAccessToken();
    if (!token) {
      gameContextLogger.warn('❌ No valid token for phraseset details refresh');
      setResultsState(prev => ({
        ...prev,
        phrasesetDetails: {
          ...prev.phrasesetDetails,
          [phrasesetId]: {
            data: cached?.data ?? null,
            loading: false,
            error: 'Authentication required. Please log in again.',
            lastFetched: cached?.lastFetched ?? null,
          }
        }
      }));
      return null;
    }

    if (cached?.data && !options.force) {
      gameContextLogger.debug('✅ Using cached phraseset details data');
      return cached.data;
    }

    gameContextLogger.debug('🔄 Setting phraseset details loading state');
    setResultsState(prev => ({
      ...prev,
      phrasesetDetails: {
        ...prev.phrasesetDetails,
        [phrasesetId]: {
          data: cached?.data ?? null,
          loading: true,
          error: null,
          lastFetched: cached?.lastFetched ?? null,
        }
      }
    }));

    try {
      gameContextLogger.debug('📞 Calling apiClient.getPhrasesetDetails...');
      const data = await apiClient.getPhrasesetDetails(phrasesetId);
      gameContextLogger.debug('✅ Phraseset details data received');

      setResultsState(prev => ({
        ...prev,
        phrasesetDetails: {
          ...prev.phrasesetDetails,
          [phrasesetId]: {
            data,
            loading: false,
            error: null,
            lastFetched: Date.now(),
          }
        }
      }));
      
      return data;
    } catch (err) {
      gameContextLogger.error('❌ Phraseset details refresh failed:', err);
      const errorMessage = getActionErrorMessage('load-details', err);
      setResultsState(prev => ({
        ...prev,
        phrasesetDetails: {
          ...prev.phrasesetDetails,
          [phrasesetId]: {
            data: cached?.data ?? null,
            loading: false,
            error: errorMessage,
            lastFetched: cached?.lastFetched ?? null,
          }
        }
      }));
      throw err;
    }
  }, [resultsState.phrasesetDetails]);

  const refreshPhrasesetResults = useCallback(async (
    phrasesetId: string,
    options: { force?: boolean } = {},
  ): Promise<PhrasesetResults | null> => {
    gameContextLogger.debug('📊 ResultsContext refreshPhrasesetResults called:', { phrasesetId, options });
    
    const cached = resultsState.phrasesetResults[phrasesetId];

    const token = await apiClient.ensureAccessToken();
    if (!token) {
      gameContextLogger.warn('❌ No valid token for phraseset results refresh');
      setResultsState(prev => ({
        ...prev,
        phrasesetResults: {
          ...prev.phrasesetResults,
          [phrasesetId]: {
            data: cached?.data ?? null,
            loading: false,
            error: 'Authentication required. Please log in again.',
            lastFetched: cached?.lastFetched ?? null,
          }
        }
      }));
      return null;
    }

    if (cached?.data && !options.force) {
      gameContextLogger.debug('✅ Using cached phraseset results data');
      return cached.data;
    }

    gameContextLogger.debug('🔄 Setting phraseset results loading state');
    setResultsState(prev => ({
      ...prev,
      phrasesetResults: {
        ...prev.phrasesetResults,
        [phrasesetId]: {
          data: cached?.data ?? null,
          loading: true,
          error: null,
          lastFetched: cached?.lastFetched ?? null,
        }
      }
    }));

    try {
      gameContextLogger.debug('📞 Calling apiClient.getPhrasesetResults...');
      const data = await apiClient.getPhrasesetResults(phrasesetId);
      gameContextLogger.debug('✅ Phraseset results data received:', {
        yourPhrase: data.your_phrase,
        yourPoints: data.your_points,
        yourPayout: data.your_payout,
        totalVotes: data.votes?.length || 0
      });

      setResultsState(prev => ({
        ...prev,
        phrasesetResults: {
          ...prev.phrasesetResults,
          [phrasesetId]: {
            data,
            loading: false,
            error: null,
            lastFetched: Date.now(),
          }
        }
      }));
      
      return data;
    } catch (err) {
      gameContextLogger.error('❌ Phraseset results refresh failed:', err);
      const errorStr = String(err);
      const notReady =
        errorStr.includes('Copy round') && errorStr.includes('not found') ||
        errorStr.includes('404') ||
        errorStr.toLowerCase().includes('not found');

      if (notReady) {
        const friendlyMessage = 'This quipset is not ready for results viewing yet. It may still be in progress or missing some data.';
        gameContextLogger.debug('⏳ Phraseset not ready for results:', phrasesetId);
        setResultsState(prev => ({
          ...prev,
          phrasesetResults: {
            ...prev.phrasesetResults,
            [phrasesetId]: {
              data: null,
              loading: false,
              error: friendlyMessage,
              lastFetched: Date.now(),
            }
          }
        }));
        return null;
      }

      const errorMessage = getActionErrorMessage('load-results', err);
      setResultsState(prev => ({
        ...prev,
        phrasesetResults: {
          ...prev.phrasesetResults,
          [phrasesetId]: {
            data: cached?.data ?? null,
            loading: false,
            error: errorMessage,
            lastFetched: cached?.lastFetched ?? null,
          }
        }
      }));
      throw err;
    }
  }, []); // No dependencies to prevent infinite loop

  const getStatistics = useCallback(async (signal?: AbortSignal) => {
    gameContextLogger.debug('📊 ResultsContext getStatistics called');
    
    const token = await apiClient.ensureAccessToken();
    if (!token) {
      gameContextLogger.warn('❌ No valid token for statistics refresh');
      setResultsState(prev => ({
        ...prev,
        statisticsError: 'Authentication required. Please log in again.'
      }));
      return null;
    }

    setResultsState(prev => ({
      ...prev,
      statisticsLoading: true,
      statisticsError: null
    }));

    try {
      gameContextLogger.debug('📞 Calling apiClient.getStatistics...');
      const data = await apiClient.getStatistics(signal);
      gameContextLogger.debug('✅ Statistics data received:', {
        hasData: !!data,
        dataKeys: data ? Object.keys(data) : []
      });

      // Transform the API data to match our StatisticsData interface
      const statisticsData: StatisticsData = {
        totalRounds: (data?.prompt_stats?.total_rounds || 0) + (data?.copy_stats?.total_rounds || 0) + (data?.voter_stats?.total_rounds || 0),
        totalEarnings: data?.earnings?.total_earnings || 0,
        averageScore: (data?.prompt_stats?.win_rate + data?.copy_stats?.win_rate + data?.voter_stats?.win_rate) / 3 || 0,
        bestPerformance: data?.best_performing_phrases?.[0] || null,
        recentActivity: data?.frequency?.last_active ? [data.frequency.last_active] : [],
      };

      setResultsState(prev => ({
        ...prev,
        statistics: statisticsData,
        statisticsLoading: false,
        statisticsError: null,
        lastStatisticsUpdate: Date.now()
      }));
      
      return data;
    } catch (err) {
      gameContextLogger.error('❌ Statistics refresh failed:', err);
      const errorMessage = getActionErrorMessage('load-statistics', err);
      setResultsState(prev => ({
        ...prev,
        statisticsLoading: false,
        statisticsError: errorMessage
      }));
      throw err;
    }
  }, []);

  const markResultsViewed = useCallback((phrasesetIds: string[]) => {
    if (!phrasesetIds || phrasesetIds.length === 0) {
      return;
    }

    gameContextLogger.debug('👁️ Marking results as viewed:', phrasesetIds);

    setResultsState(prev => ({
      ...prev,
      viewedResultIds: (() => {
        const previous = prev.viewedResultIds;
        let changed = false;
        const next = new Set(previous);

        phrasesetIds.forEach((id) => {
          if (!id) return;

          if (!next.has(id)) {
            next.add(id);
            changed = true;
          }
        });

        if (changed) {
          gameContextLogger.debug('✅ Updated viewed results:', Array.from(next));
        }

        return changed ? next : previous;
      })()
    }));
  }, []);

  const clearResultsCache = useCallback(() => {
    gameContextLogger.debug('🧹 Clearing results cache');
    setResultsState(prev => ({
      ...prev,
      playerPhrasesets: {},
      phrasesetDetails: {},
      phrasesetResults: {},
      statistics: null,
      statisticsError: null,
      lastStatisticsUpdate: null
    }));
  }, []);

  const setPendingResults = useCallback((results: PendingResult[]) => {
    gameContextLogger.debug('📋 Setting pending results:', {
      count: results.length,
      resultIds: results.map(r => r.phraseset_id)
    });
    setResultsState(prev => ({
      ...prev,
      pendingResults: results
    }));
  }, []);

  // Clear cache when user logs out
  useEffect(() => {
    if (!isAuthenticated) {
      gameContextLogger.debug('🚪 User logged out, clearing results state');
      setResultsState(prev => ({
        ...prev,
        pendingResults: [],
        viewedResultIds: new Set(),
        playerPhrasesets: {},
        phrasesetDetails: {},
        phrasesetResults: {},
        statistics: null,
        statisticsLoading: false,
        statisticsError: null,
        lastStatisticsUpdate: null
      }));
    }
  }, [isAuthenticated]);

  const actions: ResultsActions = {
    refreshPlayerPhrasesets,
    refreshPhrasesetDetails,
    refreshPhrasesetResults,
    getStatistics,
    markResultsViewed,
    clearResultsCache,
    setPendingResults,
  };

  const value: ResultsContextType = {
    state: resultsState,
    actions,
  };

  return <ResultsContext.Provider value={value}>{children}</ResultsContext.Provider>;
};

export const useResults = (): ResultsContextType => {
  const context = useContext(ResultsContext);
  if (!context) {
    throw new Error('useResults must be used within a ResultsProvider');
  }
  return context;
};