/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiClient from '../api/client.ts';
import { getActionErrorMessage } from '../utils';
import { gameContextLogger } from '../utils';
import { buildPhrasesetListKey, type PhrasesetListKeyParams } from '../utils';
import type {
  QFPendingResult,
  QFPhrasesetListResponse,
  QFPhrasesetDetails as PhrasesetDetailsType,
  QFPhrasesetResults,
  QFPlayerStatistics,
  VoteRoundState,
  MemeVoteResult,
} from '../api/types.ts';

type PlayerPhrasesetParams = PhrasesetListKeyParams;

interface PhrasesetListCacheEntry {
  params: PlayerPhrasesetParams;
  data: QFPhrasesetListResponse | null;
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
  data: QFPhrasesetResults | null;
  loading: boolean;
  error: string | null;
  lastFetched: number | null;
}

interface StatisticsData {
  totalRounds: number;
  totalEarnings: number;
  averageScore: number;
  recentActivity: string[];
}

interface ResultsState {
  pendingResults: QFPendingResult[];
  viewedResultIds: Set<string>;
  memeRounds: Record<string, VoteRoundState>;
  memeVoteResults: Record<string, MemeVoteResult>;
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
  ) => Promise<QFPhrasesetListResponse | null>;
  refreshPhrasesetDetails: (
    phrasesetId: string,
    options?: { force?: boolean }
  ) => Promise<PhrasesetDetailsType | null>;
  refreshPhrasesetResults: (
    phrasesetId: string,
    options?: { force?: boolean }
  ) => Promise<QFPhrasesetResults | null>;
  getStatistics: (signal?: AbortSignal) => Promise<QFPlayerStatistics>;
  markResultsViewed: (phrasesetIds: string[]) => void;
  clearResultsCache: () => void;
  setPendingResults: (results: QFPendingResult[]) => void;
  cacheMemeRound: (round: VoteRoundState) => void;
  cacheMemeVoteResult: (roundId: string, result: MemeVoteResult) => void;
  getCachedMemeRound: (roundId: string) => VoteRoundState | null;
  getCachedMemeVoteResult: (roundId: string) => MemeVoteResult | null;
}

interface ResultsContextType {
  state: ResultsState;
  actions: ResultsActions;
}

export interface ResultsContextConfig {
  enableMemeCaching: boolean;
}

interface ResultsProviderProps {
  children: React.ReactNode;
  isAuthenticated: boolean;
  config: ResultsContextConfig;
}

const isCanceledError = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') return false;
  const maybeError = error as { name?: string; code?: string };
  return maybeError.name === 'CanceledError' || maybeError.code === 'ERR_CANCELED';
};

const ResultsContext = createContext<ResultsContextType | undefined>(undefined);

export const ResultsProvider: React.FC<ResultsProviderProps> = ({ children, isAuthenticated, config }) => {
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
      memeRounds: {},
      memeVoteResults: {},
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
        return { ...prev, viewedResultIds: next };
      }
      
      return prev; // No changes, return same state object
    });
  }, [resultsState.pendingResults]);

  const refreshPlayerPhrasesets = useCallback(async (
    params: PlayerPhrasesetParams = {},
    options: { force?: boolean } = {},
  ): Promise<QFPhrasesetListResponse | null> => {
    gameContextLogger.debug('📊 ResultsContext refreshPlayerPhrasesets called:', { params, options });
    
    const key = buildPhrasesetListKey(params);
    const cached = resultsState.playerPhrasesets[key];

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
  ): Promise<QFPhrasesetResults | null> => {
    gameContextLogger.debug('📊 ResultsContext refreshPhrasesetResults called:', { phrasesetId, options });
    
    const cached = resultsState.phrasesetResults[phrasesetId];

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
  }, [resultsState.phrasesetResults]);

  const getStatistics = useCallback(async (signal?: AbortSignal) => {
    gameContextLogger.debug('📊 ResultsContext getStatistics called');
    
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
      if (isCanceledError(err)) {
        gameContextLogger.debug('🛑 Statistics request canceled');
        setResultsState(prev => ({
          ...prev,
          statisticsLoading: false,
        }));
        throw err;
      }
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

  const setPendingResults = useCallback((results: QFPendingResult[]) => {
    setResultsState(prev => ({
      ...prev,
      pendingResults: results
    }));
  }, []);

  const cacheMemeRound = useCallback(
    (round: VoteRoundState) => {
      if (!config.enableMemeCaching) return;

      setResultsState(prev => ({
        ...prev,
        memeRounds: {
          ...prev.memeRounds,
          [round.round_id]: round,
        },
      }));
    },
    [config.enableMemeCaching],
  );

  const cacheMemeVoteResult = useCallback((roundId: string, result: MemeVoteResult) => {
    if (!config.enableMemeCaching) return;

    setResultsState(prev => ({
      ...prev,
      memeVoteResults: {
        ...prev.memeVoteResults,
        [roundId]: result,
      },
    }));
  }, [config.enableMemeCaching]);

  const getCachedMemeRound = useCallback(
    (roundId: string): VoteRoundState | null => (config.enableMemeCaching ? resultsState.memeRounds[roundId] ?? null : null),
    [config.enableMemeCaching, resultsState.memeRounds],
  );

  const getCachedMemeVoteResult = useCallback(
    (roundId: string): MemeVoteResult | null =>
      config.enableMemeCaching ? resultsState.memeVoteResults[roundId] ?? null : null,
    [config.enableMemeCaching, resultsState.memeVoteResults],
  );

  // Clear cache when user logs out
  useEffect(() => {
    if (!isAuthenticated) {
      setResultsState(prev => ({
        ...prev,
        pendingResults: [],
        viewedResultIds: new Set(),
        memeRounds: {},
        memeVoteResults: {},
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
    cacheMemeRound,
    cacheMemeVoteResult,
    getCachedMemeRound,
    getCachedMemeVoteResult,
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
