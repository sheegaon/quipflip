/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '@crowdcraft/api/client.ts';
import { useSmartPolling, PollConfigs } from '@crowdcraft/utils/smartPolling.ts';
import { getActionErrorMessage } from '@crowdcraft/utils/errorMessages.ts';
import { gameContextLogger } from '@crowdcraft/utils/logger.ts';
import { detectUserSession, associateVisitorWithPlayer } from '@crowdcraft/services/sessionDetection';
import { SessionState } from '@crowdcraft/types/session.ts';
import { GUEST_CREDENTIALS_KEY } from '@crowdcraft/utils/storageKeys.ts';
import type { Player, TLRoundAvailability, TLAbandonRoundResponse, TLRoundDetails } from '@crowdcraft/api/types.ts';

// ThinkLink specific helpers
export type TLPlayer = Player & {
  tl_wallet?: number;
  tl_vault?: number;
  tl_tutorial_completed?: boolean;
  tl_tutorial_progress?: string;
};

type PendingResult = never;
type PhrasesetDashboardSummary = null;
type UnclaimedResult = never;
type ActiveRound = TLRoundDetails | null;

type GameState = {
  isAuthenticated: boolean;
  username: string | null;
  player: TLPlayer | null;
  showNewUserWelcome: boolean;
  activeRound: ActiveRound;
  pendingResults: PendingResult[];
  phrasesetSummary: PhrasesetDashboardSummary;
  unclaimedResults: UnclaimedResult[];
  roundAvailability: TLRoundAvailability | null;
  loading: boolean;
  error: string | null;
  sessionState: SessionState;
  visitorId: string | null;
};

type GameActions = {
  startSession: (username: string, options?: { isNewPlayer?: boolean }) => void;
  dismissNewUserWelcome: () => void;
  logout: () => Promise<void>;
  refreshDashboard: (signal?: AbortSignal) => Promise<void>;
  refreshBalance: (signal?: AbortSignal) => Promise<void>;
  refreshRoundAvailability: (signal?: AbortSignal) => Promise<void>;
  clearError: () => void;
  navigateAfterDelay: (path: string, delay?: number) => void;
  abandonRound: (roundId: string) => Promise<TLAbandonRoundResponse>;
  updateActiveRound: (roundData: ActiveRound) => void;
  setGlobalError: (message: string) => void;
};

type GameContextType = {
  state: GameState;
  actions: GameActions;
};

const GameContext = createContext<GameContextType | undefined>(undefined);

export const GameProvider: React.FC<{
  children: React.ReactNode;
  onPendingResultsChange?: (results: PendingResult[]) => void;
  onDashboardTrigger?: () => void;
}> = ({ children, onPendingResultsChange, onDashboardTrigger }) => {
  const navigate = useNavigate();
  const { startPoll, stopPoll } = useSmartPolling();

  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [player, setPlayer] = useState<TLPlayer | null>(null);
  const [showNewUserWelcome, setShowNewUserWelcome] = useState(false);
  const [activeRound, setActiveRound] = useState<ActiveRound>(null);
  const [pendingResults, setPendingResults] = useState<PendingResult[]>([]);
  const [phrasesetSummary] = useState<PhrasesetDashboardSummary>(null);
  const [unclaimedResults, setUnclaimedResults] = useState<UnclaimedResult[]>([]);
  const [roundAvailability, setRoundAvailability] = useState<TLRoundAvailability | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionState, setSessionState] = useState<SessionState>(SessionState.CHECKING);
  const [visitorId, setVisitorId] = useState<string | null>(null);

  const hasInitialLoadRef = useRef(false);

  useEffect(() => {
    if (onPendingResultsChange) {
      onPendingResultsChange(pendingResults);
    }
  }, [pendingResults, onPendingResultsChange]);

  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    const initializeSession = async () => {
      gameContextLogger.debug('🔍 Starting ThinkLink session detection on app load');

      try {
        const result = await detectUserSession('tl', controller.signal);
        if (!isMounted) return;

        setSessionState(result.state);
        setVisitorId(result.visitorId);
        setIsAuthenticated(result.isAuthenticated);

        if (result.isAuthenticated && result.username) {
          setUsername(result.username);
          if (result.player) {
            setPlayer(result.player as TLPlayer);
          }
        } else if (result.state === SessionState.NEW) {
          gameContextLogger.debug('🎭 New ThinkLink visitor detected, creating guest account');
          try {
            const guestResponse = await apiClient.createGuest();
            if (!isMounted) return;

            localStorage.setItem(GUEST_CREDENTIALS_KEY, JSON.stringify({
              email: guestResponse.email,
              password: guestResponse.password,
              timestamp: Date.now(),
            }));

            apiClient.setSession(guestResponse.username);
            setUsername(guestResponse.username);
            setIsAuthenticated(true);
            setSessionState(SessionState.RETURNING_USER);
            setShowNewUserWelcome(true);

            if (result.visitorId) {
              associateVisitorWithPlayer(result.visitorId, guestResponse.username);
            }

            const playerData = await apiClient.tlGetBalance(controller.signal);
            if (isMounted) {
              setPlayer({ ...playerData, username: guestResponse.username });
            }
          } catch (guestErr) {
            if (controller.signal.aborted) return;
            gameContextLogger.error('❌ Failed to create ThinkLink guest account:', guestErr);
            if (isMounted) {
              setUsername(null);
              setPlayer(null);
              setIsAuthenticated(false);
            }
          }
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        gameContextLogger.error('❌ ThinkLink session detection failed:', err);
        if (isMounted) {
          setSessionState(SessionState.NEW);
          setIsAuthenticated(false);
          setUsername(null);
          setPlayer(null);
        }
      }
    };

    initializeSession();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  const startSession = useCallback(
    (nextUsername: string, options?: { isNewPlayer?: boolean }) => {
      gameContextLogger.debug('🎯 GameContext startSession called:', { username: nextUsername });

      apiClient.setSession(nextUsername);
      setUsername(nextUsername);
      setIsAuthenticated(true);
      setShowNewUserWelcome(Boolean(options?.isNewPlayer));
      setSessionState(SessionState.RETURNING_USER);

      if (visitorId) {
        associateVisitorWithPlayer(visitorId, nextUsername);
      }
    },
    [visitorId],
  );

  const logout = useCallback(async () => {
    gameContextLogger.debug('🚪 GameContext logout called');

    try {
      await apiClient.logout();
    } catch (err) {
      gameContextLogger.warn('⚠️ Failed to logout cleanly:', err);
    } finally {
      stopPoll('dashboard');
      stopPoll('balance');

      apiClient.clearSession();
      setIsAuthenticated(false);
      setUsername(null);
      setPlayer(null);
      setActiveRound(null);
      setPendingResults([]);
      setUnclaimedResults([]);
      setRoundAvailability(null);
      setShowNewUserWelcome(false);
      setLoading(false);
      setError(null);
      localStorage.removeItem(GUEST_CREDENTIALS_KEY);
      setSessionState(visitorId ? SessionState.RETURNING_VISITOR : SessionState.NEW);
    }
  }, [stopPoll, visitorId]);

  const dismissNewUserWelcome = useCallback(() => {
    setShowNewUserWelcome(false);
  }, []);

  const refreshDashboard = useCallback(
    async (signal?: AbortSignal) => {
      const storedUsername = apiClient.getStoredUsername();
      if (!storedUsername) {
        gameContextLogger.debug('⏭️ Skipping ThinkLink dashboard refresh: no active session detected');
        return;
      }

      try {
        const data = await apiClient.tlGetDashboard(signal);
        const normalizedPlayer: TLPlayer = {
          username: data.username,
          wallet: data.tl_wallet,
          vault: data.tl_vault,
          tl_wallet: data.tl_wallet,
          tl_vault: data.tl_vault,
          tl_tutorial_completed: data.tl_tutorial_completed,
          tl_tutorial_progress: data.tl_tutorial_progress,
          created_at: data.created_at,
        };

        setPlayer(prev => ({ ...prev, ...normalizedPlayer }));
        if (data.username && data.username !== username) {
          apiClient.setSession(data.username);
          setUsername(data.username);
        }

        setPendingResults([]);
        setUnclaimedResults([]);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') {
          return;
        }

        gameContextLogger.error('❌ ThinkLink dashboard refresh failed:', err);
        const errorMessage = getActionErrorMessage('load-dashboard', err);
        setError(errorMessage);

        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          await logout();
        }
      }
    },
    [username, logout],
  );

  const refreshBalance = useCallback(
    async (signal?: AbortSignal) => {
      const storedUsername = apiClient.getStoredUsername();
      if (!storedUsername) {
        gameContextLogger.debug('⏭️ Skipping ThinkLink balance refresh: no active session detected');
        return;
      }

      try {
        const data = await apiClient.tlGetBalance(signal);
        const normalizedPlayer: TLPlayer = {
          ...player,
          wallet: data.tl_wallet,
          vault: data.tl_vault,
          tl_wallet: data.tl_wallet,
          tl_vault: data.tl_vault,
          username: player?.username ?? storedUsername,
        };
        setPlayer(normalizedPlayer);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') {
          return;
        }

        gameContextLogger.error('❌ ThinkLink balance refresh failed:', err);
        const errorMessage = getActionErrorMessage('refresh-balance', err);
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          setError(errorMessage);
          await logout();
        }
      }
    },
    [logout, player],
  );

  const refreshRoundAvailability = useCallback(
    async (signal?: AbortSignal) => {
      const storedUsername = apiClient.getStoredUsername();
      if (!storedUsername) {
        gameContextLogger.debug('⏭️ Skipping ThinkLink round availability check: no active session detected');
        return;
      }

      try {
        const availability = await apiClient.tlCheckRoundAvailability(signal);
        setRoundAvailability(availability);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') {
          return;
        }
        gameContextLogger.error('❌ Failed to load ThinkLink round availability:', err);
      }
    },
    [],
  );

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const setGlobalError = useCallback((message: string) => {
    setError(message);
  }, []);

  const navigateAfterDelay = useCallback(
    (path: string, delay: number = 1500) => {
      setTimeout(() => navigate(path), delay);
    },
    [navigate],
  );

  const abandonRound = useCallback(
    async (roundId: string): Promise<TLAbandonRoundResponse> => {
      gameContextLogger.debug('🛑 GameContext abandonRound called', { roundId });
      const response = await apiClient.tlAbandonRound(roundId);
      await refreshBalance();
      await refreshDashboard();
      return response;
    },
    [refreshBalance, refreshDashboard],
  );

  const updateActiveRound = useCallback((roundData: ActiveRound) => {
    setActiveRound(roundData);
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      stopPoll('dashboard');
      stopPoll('balance');
      return;
    }

    startPoll(PollConfigs.DASHBOARD, async () => {
      await refreshDashboard();
    });

    startPoll(PollConfigs.BALANCE_REFRESH, async () => {
      await refreshBalance();
    });

    return () => {
      stopPoll('dashboard');
      stopPoll('balance');
    };
  }, [isAuthenticated, startPoll, stopPoll, refreshDashboard, refreshBalance]);

  useEffect(() => {
    if (!isAuthenticated || hasInitialLoadRef.current) {
      return;
    }

    hasInitialLoadRef.current = true;
    const abortController = new AbortController();

    const loadInitialData = async () => {
      try {
        await Promise.all([
          refreshDashboard(abortController.signal),
          refreshBalance(abortController.signal),
          refreshRoundAvailability(abortController.signal),
        ]);
      } catch (err) {
        if (!abortController.signal.aborted) {
          gameContextLogger.error('❌ Failed to load initial ThinkLink dashboard data', err);
        }
      }
    };

    loadInitialData();

    return () => abortController.abort();
  }, [isAuthenticated, refreshDashboard, refreshBalance, refreshRoundAvailability]);

  const value: GameContextType = useMemo(
    () => ({
      state: {
        isAuthenticated,
        username,
        player,
        showNewUserWelcome,
        activeRound,
        pendingResults,
        phrasesetSummary,
        unclaimedResults,
        roundAvailability,
        loading,
        error,
        sessionState,
        visitorId,
      },
      actions: {
        startSession,
        dismissNewUserWelcome,
        logout,
        refreshDashboard,
        refreshBalance,
        refreshRoundAvailability,
        clearError,
        navigateAfterDelay,
        abandonRound,
        updateActiveRound,
        setGlobalError,
      },
    }),
    [
      isAuthenticated,
      username,
      player,
      showNewUserWelcome,
      activeRound,
      pendingResults,
      roundAvailability,
      loading,
      error,
      sessionState,
      visitorId,
      startSession,
      dismissNewUserWelcome,
      logout,
      refreshDashboard,
      refreshBalance,
      refreshRoundAvailability,
      clearError,
      navigateAfterDelay,
      abandonRound,
      updateActiveRound,
      setGlobalError,
    ],
  );

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
};

export const useGame = (): GameContextType => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
};
