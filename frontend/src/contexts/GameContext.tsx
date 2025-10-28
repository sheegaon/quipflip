import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { useSmartPolling, PollConfigs } from '../utils/smartPolling';
import { getActionErrorMessage } from '../utils/errorMessages';
import { gameContextLogger } from '../utils/logger';
import { buildPhrasesetListKey, type PhrasesetListKeyParams } from '../utils/gameKeys';
import type {
  Player,
  ActiveRound,
  PendingResult,
  RoundAvailability,
  PhrasesetDashboardSummary,
  UnclaimedResult,
  AuthTokenResponse,
  Quest,
  ClaimQuestRewardResponse,
  PhrasesetListResponse,
  PhrasesetDetails as PhrasesetDetailsType,
  PhrasesetResults,
} from '../api/types';

type PlayerPhrasesetParams = PhrasesetListKeyParams;

interface QuestState {
  quests: Quest[];
  activeQuests: Quest[];
  claimableQuests: Quest[];
  loading: boolean;
  error: string | null;
  lastUpdated: number | null;
}

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

interface GameState {
  isAuthenticated: boolean;
  username: string | null;
  player: Player | null;
  activeRound: ActiveRound | null;
  pendingResults: PendingResult[];
  phrasesetSummary: PhrasesetDashboardSummary | null;
  unclaimedResults: UnclaimedResult[];
  roundAvailability: RoundAvailability | null;
  loading: boolean;
  error: string | null;
  quests: Quest[];
  activeQuests: Quest[];
  claimableQuests: Quest[];
  questsLoading: boolean;
  questsError: string | null;
  hasClaimableQuests: boolean;
  questLastUpdated: number | null;
  playerPhrasesets: Record<string, PhrasesetListCacheEntry>;
  phrasesetDetails: Record<string, PhrasesetDetailsCacheEntry>;
  phrasesetResults: Record<string, PhrasesetResultsCacheEntry>;
  viewedResultIds: Set<string>;
}

interface GameActions {
  startSession: (username: string, tokens: AuthTokenResponse) => void;
  logout: () => Promise<void>;
  refreshDashboard: (signal?: AbortSignal) => Promise<void>;
  refreshBalance: (signal?: AbortSignal) => Promise<void>;
  claimBonus: () => Promise<void>;
  clearError: () => void;
  refreshQuests: () => Promise<void>;
  clearQuestError: () => void;
  claimQuest: (questId: string) => Promise<ClaimQuestRewardResponse>;
  navigateAfterDelay: (path: string, delay?: number) => void;
  startPromptRound: () => Promise<void>;
  startCopyRound: () => Promise<void>;
  startVoteRound: () => Promise<void>;
  refreshPlayerPhrasesets: (
    params?: PlayerPhrasesetParams,
    options?: { force?: boolean },
  ) => Promise<PhrasesetListResponse | null>;
  refreshPhrasesetDetails: (
    phrasesetId: string,
    options?: { force?: boolean },
  ) => Promise<PhrasesetDetailsType | null>;
  refreshPhrasesetResults: (
    phrasesetId: string,
    options?: { force?: boolean },
  ) => Promise<PhrasesetResults | null>;
  claimPhrasesetPrize: (phrasesetId: string) => Promise<void>;
  getStatistics: (signal?: AbortSignal) => Promise<any>;
  markResultsViewed: (phrasesetIds: string[]) => void;
}

interface GameContextType {
  state: GameState;
  actions: GameActions;
}

const GameContext = createContext<GameContextType | undefined>(undefined);

export const GameProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Navigation hook - use directly since we're inside Router
  const navigate = useNavigate();
  
  // Smart polling hook
  const { startPoll, stopPoll, triggerPoll } = useSmartPolling();
  
  // State
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [player, setPlayer] = useState<Player | null>(null);
  const [activeRound, setActiveRound] = useState<ActiveRound | null>(null);
  const [pendingResults, setPendingResults] = useState<PendingResult[]>([]);
  const [phrasesetSummary, setPhrasesetSummary] = useState<PhrasesetDashboardSummary | null>(null);
  const [unclaimedResults, setUnclaimedResults] = useState<UnclaimedResult[]>([]);
  const [roundAvailability, setRoundAvailability] = useState<RoundAvailability | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [questState, setQuestState] = useState<QuestState>({
    quests: [],
    activeQuests: [],
    claimableQuests: [],
    loading: false,
    error: null,
    lastUpdated: null,
  });
  const [phrasesetListCache, setPhrasesetListCache] = useState<Record<string, PhrasesetListCacheEntry>>({});
  const [phrasesetDetailsCache, setPhrasesetDetailsCache] = useState<Record<string, PhrasesetDetailsCacheEntry>>({});
  const [phrasesetResultsCache, setPhrasesetResultsCache] = useState<Record<string, PhrasesetResultsCacheEntry>>({});
  const [viewedResultIds, setViewedResultIds] = useState<Set<string>>(() => {
    if (typeof window === 'undefined') {
      return new Set();
    }

    try {
      const stored = window.sessionStorage.getItem('viewedResultIds');
      if (!stored) {
        return new Set();
      }

      const parsed: unknown = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        return new Set(parsed.filter((value): value is string => typeof value === 'string'));
      }
    } catch (err) {
      console.warn('Failed to restore viewed results from sessionStorage', err);
    }

    return new Set();
  });

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.sessionStorage.setItem('viewedResultIds', JSON.stringify(Array.from(viewedResultIds)));
    } catch (err) {
      console.warn('Failed to persist viewed results to sessionStorage', err);
    }
  }, [viewedResultIds]);

  useEffect(() => {
    setViewedResultIds((previous) => {
      if (pendingResults.length === 0) {
        if (previous.size === 0) {
          return previous;
        }
        return new Set();
      }

      const validIds = new Set(pendingResults.map((result) => result.phraseset_id));
      const next = new Set<string>();
      let changed = false;

      pendingResults.forEach((result) => {
        const id = result.phraseset_id;
        if (!id) {
          return;
        }

        if (result.result_viewed || previous.has(id)) {
          if (!next.has(id)) {
            next.add(id);
            if (!previous.has(id)) {
              changed = true;
            }
          }
        }
      });

      previous.forEach((id) => {
        if (validIds.has(id)) {
          if (!next.has(id)) {
            next.add(id);
            changed = true;
          }
        } else {
          changed = true;
        }
      });

      if (!changed && next.size === previous.size) {
        return previous;
      }

      return next;
    });
  }, [pendingResults]);

  // Initialize session on mount
  useEffect(() => {
    gameContextLogger.debug('Initializing session...');
    const initializeSession = async () => {
      const storedUsername = apiClient.getStoredUsername();
      gameContextLogger.debug('Stored username:', storedUsername);
      if (storedUsername) {
        setUsername(storedUsername);
      }
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Access token check result:', { hasToken: !!token });
      setIsAuthenticated(Boolean(token));
    };
    initializeSession();
  }, []);

  // Monitor authentication state changes
  useEffect(() => {
    gameContextLogger.debug('Authentication state changed:', { isAuthenticated, username });
  }, [isAuthenticated, username]);

  // Create stable actions object using useCallback for all methods
  const startSession = useCallback((nextUsername: string, tokens: AuthTokenResponse) => {
      apiClient.setSession(nextUsername, tokens);
      setUsername(nextUsername);
      setIsAuthenticated(true);
      
      // Immediately load dashboard data after successful login
      setTimeout(async () => {
        try {
          const data = await apiClient.getDashboardData();
          setPlayer(data.player);
          setActiveRound(data.current_round);
          setPendingResults(data.pending_results);
          setPhrasesetSummary(data.phraseset_summary);
          setUnclaimedResults(data.unclaimed_results);
          setRoundAvailability(data.round_availability);
          setError(null);
        } catch (err) {
          console.error('Failed to load dashboard after login:', err);
          const errorMessage = getActionErrorMessage('load-dashboard', err);
          setError(errorMessage);
        }
      }, 100);
  }, []);

  const logout = useCallback(async () => {
      try {
        await apiClient.logout();
      } catch (err) {
        console.warn('Failed to logout cleanly', err);
      } finally {
        // Stop all polling
        stopPoll('dashboard');
        stopPoll('balance');
        
        apiClient.clearSession();
        setIsAuthenticated(false);
        setUsername(null);
        setPlayer(null);
        setActiveRound(null);
        setPendingResults([]);
        setPhrasesetSummary(null);
        setUnclaimedResults([]);
        setRoundAvailability(null);
        setQuestState({
          quests: [],
          activeQuests: [],
          claimableQuests: [],
          loading: false,
          error: null,
          lastUpdated: null,
        });
        setPhrasesetListCache({});
        setPhrasesetDetailsCache({});
        setPhrasesetResultsCache({});
      }
  }, [stopPoll]);

  const refreshDashboard = useCallback(async (signal?: AbortSignal) => {
      gameContextLogger.debug('refreshDashboard called');
      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Token check for dashboard refresh:', { hasToken: !!token });
      
      if (!token) {
        gameContextLogger.warn('No valid token, skipping dashboard refresh');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        gameContextLogger.debug('Making dashboard API call...');
        const data = await apiClient.getDashboardData(signal);
        gameContextLogger.debug('✅ Dashboard data received successfully');
        gameContextLogger.debug('Current round from API:', {
          currentRound: data.current_round ? {
            id: data.current_round.round_id,
            type: data.current_round.round_type,
            status: data.current_round.state?.status
          } : 'null'
        });

        // Update all dashboard state at once
        setPlayer(data.player);
        if (data.player.username && data.player.username !== username) {
          apiClient.setSession(data.player.username);
          setUsername(data.player.username);
        }
        
        // Handle active round properly - if it's submitted, expired, or abandoned, clear it
        if (data.current_round) {
          const roundState = data.current_round.state;
          const roundStatus = roundState?.status;

          // Only show active rounds; clear completed/expired/abandoned rounds
          if (roundStatus === 'active') {
            gameContextLogger.debug('Setting active round:', data.current_round);
            setActiveRound(data.current_round);
          } else {
            gameContextLogger.debug(`Round status is ${roundStatus}, clearing active round`);
            setActiveRound(null);
          }
        } else {
          gameContextLogger.debug('No current round from API, clearing active round');
          setActiveRound(null);
        }
        
        setPendingResults(data.pending_results);
        setPhrasesetSummary(data.phraseset_summary);
        setUnclaimedResults(data.unclaimed_results);
        setRoundAvailability(data.round_availability);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;

        gameContextLogger.error('Dashboard refresh failed:', err);
        const errorMessage = getActionErrorMessage('load-dashboard', err);
        setError(errorMessage);

        // Handle auth errors
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          gameContextLogger.warn('Auth error detected, logging out');
          logout();
        }
      }
  }, [isAuthenticated, username]);

  const refreshBalance = useCallback(async (signal?: AbortSignal) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

      try {
        const data = await apiClient.getBalance(signal);
        setPlayer(data);
        if (data.username && data.username !== username) {
          apiClient.setSession(data.username);
          setUsername(data.username);
        }
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;

        const errorMessage = getActionErrorMessage('refresh-balance', err);
        
        // Only show balance refresh errors if they're auth-related
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          setError(errorMessage);
          logout();
        }
      }
  }, [isAuthenticated, username]);

  const claimBonus = useCallback(async () => {
      console.log('🎯 GameContext claimBonus called');
      
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      console.log('🔍 Token check for claim bonus:', { hasToken: !!token });
      
      if (!token) {
        console.log('❌ No valid token, aborting claim bonus');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        console.log('🔄 Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        console.log('🔄 Setting loading to true');
        setLoading(true);
        console.log('📞 Calling apiClient.claimDailyBonus()...');
        await apiClient.claimDailyBonus();
        console.log('✅ API call successful');
        
        // Trigger immediate dashboard refresh
        console.log('🔄 Triggering dashboard refresh');
        triggerPoll('dashboard');
        
        setError(null);
        console.log('✅ Claim bonus completed successfully');
      } catch (err) {
        console.error('❌ Claim bonus API call failed:', err);
        const message = getActionErrorMessage('claim-bonus', err);
        console.log('📝 Error message:', message);
        setError(message);

        // Handle auth errors
        if (message.toLowerCase().includes('session') || message.toLowerCase().includes('login')) {
          console.log('🚪 Auth error detected, logging out');
          logout();
        }

        throw err;
      } finally {
        console.log('🔄 Setting loading to false');
        setLoading(false);
      }
  }, [isAuthenticated, triggerPoll, logout]);

  const refreshQuests = useCallback(async () => {
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        setQuestState((prev) => ({
          ...prev,
          loading: false,
          error: 'Authentication required. Please log in again.',
        }));
        return;
      }

      setQuestState((prev) => ({
        ...prev,
        loading: true,
        error: null,
      }));

      try {
        const [allQuestsResponse, activeQuestsResponse, claimableQuestsResponse] = await Promise.all([
          apiClient.getQuests(),
          apiClient.getActiveQuests(),
          apiClient.getClaimableQuests(),
        ]);

        setQuestState({
          quests: allQuestsResponse.quests,
          activeQuests: activeQuestsResponse,
          claimableQuests: claimableQuestsResponse,
          loading: false,
          error: null,
          lastUpdated: Date.now(),
        });
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-quests', err);
        setQuestState((prev) => ({
          ...prev,
          loading: false,
          error: errorMessage,
        }));
        throw err;
      }
  }, []);

  const clearQuestError = useCallback(() => {
      setQuestState((prev) => ({
        ...prev,
        error: null,
      }));
  }, []);

  const claimQuest = useCallback(async (questId: string): Promise<ClaimQuestRewardResponse> => {
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        setQuestState((prev) => ({
          ...prev,
          loading: false,
          error: 'Authentication required. Please log in again.',
        }));
        throw new Error('Authentication required');
      }

      setQuestState((prev) => ({
        ...prev,
        loading: true,
        error: null,
      }));

      try {
        const response = await apiClient.claimQuestReward(questId);

        await refreshQuests();
        triggerPoll('dashboard');
        return response;
      } catch (err) {
        const errorMessage = getActionErrorMessage('claim-quest', err);
        setQuestState((prev) => ({
          ...prev,
          loading: false,
          error: errorMessage,
        }));
        throw err;
      } finally {
        setQuestState((prev) => ({
          ...prev,
          loading: false,
        }));
      }
  }, [refreshQuests, triggerPoll]);

  const refreshPlayerPhrasesets = useCallback(async (
      params: PlayerPhrasesetParams = {},
      options: { force?: boolean } = {},
    ): Promise<PhrasesetListResponse | null> => {
      const key = buildPhrasesetListKey(params);
      const cached = phrasesetListCache[key];

      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        setPhrasesetListCache((prev) => ({
          ...prev,
          [key]: {
            params,
            data: cached?.data ?? null,
            loading: false,
            error: 'Authentication required. Please log in again.',
            lastFetched: cached?.lastFetched ?? null,
          },
        }));
        return null;
      }

      if (cached?.data && !options.force) {
        return cached.data;
      }

      setPhrasesetListCache((prev) => ({
        ...prev,
        [key]: {
          params,
          data: cached?.data ?? null,
          loading: true,
          error: null,
          lastFetched: cached?.lastFetched ?? null,
        },
      }));

      try {
        const data = await apiClient.getPlayerPhrasesets(params);
        setPhrasesetListCache((prev) => ({
          ...prev,
          [key]: {
            params,
            data,
            loading: false,
            error: null,
            lastFetched: Date.now(),
          },
        }));
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-tracking', err);
        setPhrasesetListCache((prev) => ({
          ...prev,
          [key]: {
            params,
            data: cached?.data ?? null,
            loading: false,
            error: errorMessage,
            lastFetched: cached?.lastFetched ?? null,
          },
        }));
        throw err;
      }
  }, [phrasesetListCache]);

  const refreshPhrasesetDetails = useCallback(async (
      phrasesetId: string,
      options: { force?: boolean } = {},
    ): Promise<PhrasesetDetailsType | null> => {
      const cached = phrasesetDetailsCache[phrasesetId];

      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        setPhrasesetDetailsCache((prev) => ({
          ...prev,
          [phrasesetId]: {
            data: cached?.data ?? null,
            loading: false,
            error: 'Authentication required. Please log in again.',
            lastFetched: cached?.lastFetched ?? null,
          },
        }));
        return null;
      }

      if (cached?.data && !options.force) {
        return cached.data;
      }

      setPhrasesetDetailsCache((prev) => ({
        ...prev,
        [phrasesetId]: {
          data: cached?.data ?? null,
          loading: true,
          error: null,
          lastFetched: cached?.lastFetched ?? null,
        },
      }));

      try {
        const data = await apiClient.getPhrasesetDetails(phrasesetId);
        setPhrasesetDetailsCache((prev) => ({
          ...prev,
          [phrasesetId]: {
            data,
            loading: false,
            error: null,
            lastFetched: Date.now(),
          },
        }));
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-details', err);
        setPhrasesetDetailsCache((prev) => ({
          ...prev,
          [phrasesetId]: {
            data: cached?.data ?? null,
            loading: false,
            error: errorMessage,
            lastFetched: cached?.lastFetched ?? null,
          },
        }));
        throw err;
      }
  }, [phrasesetDetailsCache]);

  const refreshPhrasesetResults = useCallback(async (
      phrasesetId: string,
      options: { force?: boolean } = {},
    ): Promise<PhrasesetResults | null> => {
      const cached = phrasesetResultsCache[phrasesetId];

      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        setPhrasesetResultsCache((prev) => ({
          ...prev,
          [phrasesetId]: {
            data: cached?.data ?? null,
            loading: false,
            error: 'Authentication required. Please log in again.',
            lastFetched: cached?.lastFetched ?? null,
          },
        }));
        return null;
      }

      if (cached?.data && !options.force) {
        return cached.data;
      }

      setPhrasesetResultsCache((prev) => ({
        ...prev,
        [phrasesetId]: {
          data: cached?.data ?? null,
          loading: true,
          error: null,
          lastFetched: cached?.lastFetched ?? null,
        },
      }));

      try {
        const data = await apiClient.getPhrasesetResults(phrasesetId);
        setPhrasesetResultsCache((prev) => ({
          ...prev,
          [phrasesetId]: {
            data,
            loading: false,
            error: null,
            lastFetched: Date.now(),
          },
        }));
        return data;
      } catch (err) {
        const errorStr = String(err);
        const notReady =
          errorStr.includes('Copy round') && errorStr.includes('not found') ||
          errorStr.includes('404') ||
          errorStr.toLowerCase().includes('not found');

        if (notReady) {
          const friendlyMessage = 'This quipset is not ready for results viewing yet. It may still be in progress or missing some data.';
          setPhrasesetResultsCache((prev) => ({
            ...prev,
            [phrasesetId]: {
              data: null,
              loading: false,
              error: friendlyMessage,
              lastFetched: Date.now(),
            },
          }));
          return null;
        }

        const errorMessage = getActionErrorMessage('load-results', err);
        setPhrasesetResultsCache((prev) => ({
          ...prev,
          [phrasesetId]: {
            data: cached?.data ?? null,
            loading: false,
            error: errorMessage,
            lastFetched: cached?.lastFetched ?? null,
          },
        }));
        throw err;
      }
  }, [phrasesetResultsCache]);

  const clearError = useCallback(() => {
      setError(null);
  }, []);

  const navigateAfterDelay = useCallback((path: string, delay: number = 1500) => {
      setTimeout(() => navigate(path), delay);
  }, [navigate]);

  const startPromptRound = useCallback(async () => {
      gameContextLogger.info('startPromptRound called');

      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Token check for prompt round:', { hasToken: !!token });

      if (!token) {
        gameContextLogger.warn('No valid token, aborting prompt round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      gameContextLogger.debug('Starting prompt round API call...');
      gameContextLogger.debug('Current round availability:', roundAvailability);
      gameContextLogger.debug('Current player state:', {
        balance: player?.balance,
        outstandingPrompts: player?.outstanding_prompts
      });

      try {
        setLoading(true);
        setError(null);
        gameContextLogger.debug('Calling apiClient.startPromptRound()...');
        const response = await apiClient.startPromptRound();
        gameContextLogger.info('✅ API call successful, response:', response);
        
        const newActiveRound = {
          round_type: 'prompt' as const,
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            prompt_text: response.prompt_text,
            expires_at: response.expires_at,
            cost: response.cost,
            status: 'active' as const,
          },
        };
        
        gameContextLogger.debug('Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        // Trigger immediate dashboard refresh to update availability
        gameContextLogger.debug('Triggering dashboard refresh...');
        triggerPoll('dashboard');

        gameContextLogger.info('✅ Prompt round started successfully');
      } catch (err) {
        gameContextLogger.error('Failed to start prompt round:', err);
        const errorMessage = getActionErrorMessage('start-prompt', err);
        gameContextLogger.debug('Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        setLoading(false);
      }
  }, [isAuthenticated, roundAvailability, player?.balance, player?.outstanding_prompts, triggerPoll]);

  const startCopyRound = useCallback(async () => {
      gameContextLogger.info('startCopyRound called');

      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Token check for copy round:', { hasToken: !!token });

      if (!token) {
        gameContextLogger.warn('No valid token, aborting copy round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      gameContextLogger.debug('Starting copy round API call...');
      gameContextLogger.debug('Current round availability:', roundAvailability);
      gameContextLogger.debug('Current player state:', {
        balance: player?.balance,
        promptsWaiting: roundAvailability?.prompts_waiting,
        copyCost: roundAvailability?.copy_cost
      });

      try {
        setLoading(true);
        setError(null);
        gameContextLogger.debug('Calling apiClient.startCopyRound()...');
        const response = await apiClient.startCopyRound();
        gameContextLogger.info('✅ API call successful, response:', response);
        
        const newActiveRound = {
          round_type: 'copy' as const,
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            original_phrase: response.original_phrase,
            expires_at: response.expires_at,
            cost: response.cost,
            discount_active: response.discount_active,
            status: 'active' as const,
          },
        };
        
        gameContextLogger.debug('Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        gameContextLogger.debug('Triggering dashboard refresh...');
        triggerPoll('dashboard');

        gameContextLogger.info('✅ Copy round started successfully');
      } catch (err) {
        gameContextLogger.error('Failed to start copy round:', err);
        const errorMessage = getActionErrorMessage('start-copy', err);
        gameContextLogger.debug('Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        setLoading(false);
      }
  }, [isAuthenticated, roundAvailability, player?.balance, triggerPoll]);

  const startVoteRound = useCallback(async () => {
      gameContextLogger.info('startVoteRound called');

      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Token check for vote round:', { hasToken: !!token });

      if (!token) {
        gameContextLogger.warn('No valid token, aborting vote round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      gameContextLogger.debug('Starting vote round API call...');
      gameContextLogger.debug('Current round availability:', roundAvailability);
      gameContextLogger.debug('Current player state:', {
        balance: player?.balance,
        phrasesetsWaiting: roundAvailability?.phrasesets_waiting
      });

      try {
        setLoading(true);
        setError(null);
        gameContextLogger.debug('Calling apiClient.startVoteRound()...');
        const response = await apiClient.startVoteRound();
        gameContextLogger.info('✅ API call successful, response:', response);
        
        const newActiveRound = {
          round_type: 'vote' as const,
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            phraseset_id: response.phraseset_id,
            prompt_text: response.prompt_text,
            phrases: response.phrases,
            expires_at: response.expires_at,
            status: 'active' as const,
          },
        };
        
        gameContextLogger.debug('Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        gameContextLogger.debug('Triggering dashboard refresh...');
        triggerPoll('dashboard');

        gameContextLogger.info('✅ Vote round started successfully');
      } catch (err) {
        gameContextLogger.error('Failed to start vote round:', err);
        const errorMessage = getActionErrorMessage('start-vote', err);
        gameContextLogger.debug('Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        setLoading(false);
      }
  }, [isAuthenticated, roundAvailability, player?.balance, triggerPoll]);

  const claimPhrasesetPrize = useCallback(async (phrasesetId: string) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

      try {
        await apiClient.claimPhrasesetPrize(phrasesetId);
        
        // Trigger immediate dashboard refresh to update balance
        triggerPoll('dashboard');
        
        setError(null);
      } catch (err) {
        const errorMessage = getActionErrorMessage('claim-prize', err);
        setError(errorMessage);
        throw err;
      }
  }, [isAuthenticated, triggerPoll]);

  const getStatistics = useCallback(async (signal?: AbortSignal) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return null;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

      try {
        const data = await apiClient.getStatistics(signal);
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-statistics', err);
        setError(errorMessage);
        throw err;
      }
  }, [isAuthenticated]);

  const markResultsViewed = useCallback((phrasesetIds: string[]) => {
      if (!phrasesetIds || phrasesetIds.length === 0) {
        return;
      }

      setViewedResultIds((previous) => {
        let changed = false;
        const next = new Set(previous);

        phrasesetIds.forEach((id) => {
          if (!id) {
            return;
          }

          if (!next.has(id)) {
            next.add(id);
            changed = true;
          }
        });

        return changed ? next : previous;
      });
    }, []);

  // Set up smart polling when authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      stopPoll('dashboard');
      stopPoll('balance');
      return;
    }

    // Start dashboard polling with smart intervals
    startPoll(PollConfigs.DASHBOARD, async () => {
      await refreshDashboard();
    });

    // Start balance polling with longer intervals
    startPoll(PollConfigs.BALANCE_REFRESH, async () => {
      await refreshBalance();
    });

    // Cleanup function
    return () => {
      stopPoll('dashboard');
      stopPoll('balance');
    };
  }, [isAuthenticated, startPoll, stopPoll, refreshDashboard, refreshBalance]);

  // Initial dashboard load - only once when authenticated changes
  const hasInitialLoadRef = useRef(false);
  useEffect(() => {
    if (!isAuthenticated) {
      hasInitialLoadRef.current = false;
      return;
    }

    // Prevent duplicate loads in React StrictMode
    if (hasInitialLoadRef.current) return;
    hasInitialLoadRef.current = true;

    const controller = new AbortController();
    refreshDashboard(controller.signal);

    return () => controller.abort();
  }, [isAuthenticated, refreshDashboard]);

  // Quest auto-loading when authenticated
  const hasQuestLoadRef = useRef(false);
  useEffect(() => {
    if (!isAuthenticated) {
      hasQuestLoadRef.current = false;
      setQuestState({
        quests: [],
        activeQuests: [],
        claimableQuests: [],
        loading: false,
        error: null,
        lastUpdated: null,
      });
      return;
    }

    if (hasQuestLoadRef.current) return;
    hasQuestLoadRef.current = true;

    refreshQuests().catch((err) => {
      gameContextLogger.error('Failed to refresh quests:', err);
    });
  }, [isAuthenticated, refreshQuests]);

  const state: GameState = {
    isAuthenticated,
    username,
    player,
    activeRound,
    pendingResults,
    phrasesetSummary,
    unclaimedResults,
    roundAvailability,
    loading,
    error,
    quests: questState.quests,
    activeQuests: questState.activeQuests,
    claimableQuests: questState.claimableQuests,
    questsLoading: questState.loading,
    questsError: questState.error,
    hasClaimableQuests: questState.claimableQuests.length > 0,
    questLastUpdated: questState.lastUpdated,
    playerPhrasesets: phrasesetListCache,
    phrasesetDetails: phrasesetDetailsCache,
    phrasesetResults: phrasesetResultsCache,
    viewedResultIds,
  };

  const actions: GameActions = {
    startSession,
    logout,
    refreshDashboard,
    refreshBalance,
    claimBonus,
    clearError,
    refreshQuests,
    clearQuestError,
    claimQuest,
    navigateAfterDelay,
    startPromptRound,
    startCopyRound,
    startVoteRound,
    refreshPlayerPhrasesets,
    refreshPhrasesetDetails,
    refreshPhrasesetResults,
    claimPhrasesetPrize,
    getStatistics,
    markResultsViewed,
  };

  const value: GameContextType = {
    state,
    actions,
  };

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
};

// Main hook - returns structured API
export const useGame = (): GameContextType => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
};
