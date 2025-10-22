import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import apiClient, { extractErrorMessage } from '../api/client';
import type {
  Player,
  ActiveRound,
  PendingResult,
  RoundAvailability,
  PhrasesetDashboardSummary,
  UnclaimedResult,
  AuthTokenResponse,
} from '../api/types';

interface GameContextType {
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

  startSession: (username: string, tokens: AuthTokenResponse) => void;
  logout: () => Promise<void>;
  refreshDashboard: () => Promise<void>;
  refreshBalance: () => Promise<void>;
  claimBonus: () => Promise<void>;
  clearError: () => void;
}

const GameContext = createContext<GameContextType | undefined>(undefined);

export const GameProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
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

  useEffect(() => {
    const initializeSession = async () => {
      const storedUsername = apiClient.getStoredUsername();
      if (storedUsername) {
        setUsername(storedUsername);
      }
      const token = await apiClient.ensureAccessToken();
      setIsAuthenticated(Boolean(token));
    };
    initializeSession();
  }, []);

  const startSession = useCallback((nextUsername: string, tokens: AuthTokenResponse) => {
    apiClient.setSession(nextUsername, tokens);
    setUsername(nextUsername);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiClient.logout();
    } catch (err) {
      // Swallow logout errors to ensure UI state is cleared
      console.warn('Failed to logout cleanly', err);
    } finally {
      apiClient.clearSession();
      setIsAuthenticated(false);
      setUsername(null);
      setPlayer(null);
      setActiveRound(null);
      setPendingResults([]);
      setPhrasesetSummary(null);
      setUnclaimedResults([]);
      setRoundAvailability(null);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const handleAuthError = useCallback(
    (message: string | null | undefined) => {
      if (!message) return;
      const normalized = message.toLowerCase();
      if (
        normalized.includes('unauthorized') ||
        normalized.includes('token') ||
        normalized.includes('credentials')
      ) {
        logout();
      }
    },
    [logout],
  );

  const refreshDashboard = useCallback(
    async (signal?: AbortSignal) => {
      if (!isAuthenticated) return;
      try {
        const data = await apiClient.getDashboardData(signal);

        // Update all dashboard state at once
        setPlayer(data.player);
        if (data.player.username && data.player.username !== username) {
          apiClient.setSession(data.player.username);
          setUsername(data.player.username);
        }
        setActiveRound(data.current_round);
        setPendingResults(data.pending_results);
        setPhrasesetSummary(data.phraseset_summary);
        setUnclaimedResults(data.unclaimed_results);
        setRoundAvailability(data.round_availability);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;
        const errorMessage = extractErrorMessage(err);
        setError(errorMessage || 'Unable to load dashboard data. Please refresh the page.');
        handleAuthError(errorMessage);
      }
    },
    [handleAuthError, isAuthenticated, username],
  );

  const refreshBalance = useCallback(
    async (signal?: AbortSignal) => {
      if (!isAuthenticated) return;
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
        const errorMessage = extractErrorMessage(err);
        setError(errorMessage || 'Unable to update your balance. Please refresh the page.');
        handleAuthError(errorMessage);
      }
    },
    [handleAuthError, isAuthenticated, username],
  );

  const claimBonus = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      setLoading(true);
      await apiClient.claimDailyBonus();
      await refreshBalance();
      setError(null);
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to claim your daily bonus right now. You may have already claimed it today, or there may be a temporary issue.';
      setError(message);
      handleAuthError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [handleAuthError, isAuthenticated, refreshBalance]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const controller = new AbortController();
    refreshDashboard(controller.signal);

    return () => controller.abort();
  }, [isAuthenticated, refreshDashboard]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const dashboardInterval = setInterval(async () => {
      try {
        // Get fresh data
        const newData = await apiClient.getDashboardData();

        // Compare key fields to see if an update is needed
        const hasPlayerChanged = !player || 
          player.balance !== newData.player.balance ||
          player.daily_bonus_available !== newData.player.daily_bonus_available;

        const hasActiveRoundChanged = (!activeRound && newData.current_round) ||
          (activeRound && !newData.current_round) ||
          (activeRound?.round_id !== newData.current_round?.round_id) ||
          (activeRound?.expires_at !== newData.current_round?.expires_at);

        const hasPendingResultsChanged = pendingResults.length !== newData.pending_results.length ||
          pendingResults.some((result, index) => 
            newData.pending_results[index]?.phraseset_id !== result.phraseset_id
          );

        const hasPhrasesetSummaryChanged = !phrasesetSummary ||
          phrasesetSummary.in_progress.prompts !== newData.phraseset_summary.in_progress.prompts ||
          phrasesetSummary.in_progress.copies !== newData.phraseset_summary.in_progress.copies ||
          phrasesetSummary.finalized.prompts !== newData.phraseset_summary.finalized.prompts ||
          phrasesetSummary.finalized.copies !== newData.phraseset_summary.finalized.copies ||
          phrasesetSummary.total_unclaimed_amount !== newData.phraseset_summary.total_unclaimed_amount;

        const hasUnclaimedResultsChanged = unclaimedResults.length !== newData.unclaimed_results.length ||
          unclaimedResults.some((result, index) => 
            newData.unclaimed_results[index]?.phraseset_id !== result.phraseset_id
          );

        const hasRoundAvailabilityChanged = !roundAvailability ||
          roundAvailability.can_prompt !== newData.round_availability.can_prompt ||
          roundAvailability.can_copy !== newData.round_availability.can_copy ||
          roundAvailability.can_vote !== newData.round_availability.can_vote;

        // Only update state if something actually changed
        if (hasPlayerChanged || hasActiveRoundChanged || hasPendingResultsChanged || 
            hasPhrasesetSummaryChanged || hasUnclaimedResultsChanged || hasRoundAvailabilityChanged) {
          
          // Update all dashboard state at once
          setPlayer(newData.player);
          if (newData.player.username && newData.player.username !== username) {
            apiClient.setSession(newData.player.username);
            setUsername(newData.player.username);
          }
          setActiveRound(newData.current_round);
          setPendingResults(newData.pending_results);
          setPhrasesetSummary(newData.phraseset_summary);
          setUnclaimedResults(newData.unclaimed_results);
          setRoundAvailability(newData.round_availability);
          setError(null);
        }
      } catch (err) {
        // Don't update error state on polling failures to avoid UI flickering
        console.warn('Failed to poll dashboard data:', err);
      }
    }, 60_000);

    return () => {
      clearInterval(dashboardInterval);
    };
  }, [isAuthenticated, player, activeRound, pendingResults, phrasesetSummary, unclaimedResults, roundAvailability, username]);

  const value: GameContextType = {
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
    startSession,
    logout,
    refreshDashboard,
    refreshBalance,
    claimBonus,
    clearError,
  };

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
};

export const useGame = (): GameContextType => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
};
