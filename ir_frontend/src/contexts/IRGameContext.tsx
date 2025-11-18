import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import type {
  IRPlayer,
  BackronymSet,
  PendingResult,
  DashboardData,
  StartSessionResponse,
  SubmitBackronymRequest,
  SubmitVoteRequest,
  ValidateBackronymRequest,
  ValidateBackronymResponse,
} from '../api/types';
import { authAPI, playerAPI, gameAPI } from '../api/client';
import { setActiveSetId, setPlayerId, clearGameStorage } from '../utils/gameKeys';
import { getActionErrorMessage } from '../utils/errorMessages';
import {
  detectUserSession,
  associateVisitorWithPlayer,
  SessionState,
  setStoredUsername,
  clearStoredUsername
} from '../services/sessionDetection';
import { createLogger } from '../utils/logger';

const gameContextLogger = createLogger('IRGameContext');

interface IRGameState {
  isAuthenticated: boolean;
  player: IRPlayer | null;
  activeSet: BackronymSet | null;
  pendingResults: PendingResult[];
  loading: boolean;
  error: string | null;
  hasSubmittedEntry: boolean;
  hasVoted: boolean;
  sessionState: SessionState;
  visitorId: string | null;
}

interface IRGameContextType extends IRGameState {
  // Authentication
  loginAsGuest: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  upgradeGuest: (username: string, email: string, password: string) => Promise<void>;

  // Game actions
  startBackronymBattle: () => Promise<StartSessionResponse>;
  submitBackronym: (setId: string, words: string[]) => Promise<void>;
  validateBackronym: (setId: string, words: string[]) => Promise<ValidateBackronymResponse>;
  submitVote: (setId: string, entryId: string) => Promise<void>;
  claimDailyBonus: () => Promise<void>;

  // Data fetching
  refreshDashboard: () => Promise<void>;
  checkSetStatus: (setId: string) => Promise<void>;

  // Utilities
  clearError: () => void;
}

const IRGameContext = createContext<IRGameContextType | undefined>(undefined);

// eslint-disable-next-line react-refresh/only-export-components
export const useIRGame = () => {
  const context = useContext(IRGameContext);
  if (!context) {
    throw new Error('useIRGame must be used within IRGameProvider');
  }
  return context;
};

interface IRGameProviderProps {
  children: ReactNode;
}

export const IRGameProvider: React.FC<IRGameProviderProps> = ({ children }) => {
  const [state, setState] = useState<IRGameState>({
    isAuthenticated: false,
    player: null,
    activeSet: null,
    pendingResults: [],
    loading: false,
    error: null,
    hasSubmittedEntry: false,
    hasVoted: false,
    sessionState: SessionState.CHECKING,
    visitorId: null,
  });

  // Initialize session on mount using session detection
  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    const initializeSession = async () => {
      gameContextLogger.debug('🔍 Starting session detection on app load');

      try {
        const result = await detectUserSession(controller.signal);

        if (!isMounted) return;

        gameContextLogger.debug('✅ Session detection complete:', {
          state: result.state,
          isAuthenticated: result.isAuthenticated,
          username: result.username,
          visitorId: result.visitorId,
        });

        // Update state based on detection result
        setState((prev) => ({
          ...prev,
          sessionState: result.state,
          visitorId: result.visitorId,
          isAuthenticated: result.isAuthenticated,
          player: result.player ? {
            player_id: '',  // We don't have this from balance response
            username: result.username || '',
            email: null,
            wallet: result.player.wallet,
            vault: result.player.vault,
            is_guest: false,
            daily_bonus_available: result.player.daily_bonus_available,
            created_at: '',
            last_login_date: null,
          } : null,
        }));
      } catch (error: unknown) {
        if (!isMounted) return;

        // Handle non-abort errors
        const errorCode = (error as { code?: string })?.code;
        if (errorCode !== 'ERR_CANCELED') {
          gameContextLogger.error('❌ Session detection failed:', error);
          setState((prev) => ({
            ...prev,
            sessionState: SessionState.NEW,
            loading: false,
          }));
        }
      }
    };

    initializeSession();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  const setLoading = (loading: boolean) => {
    setState((prev) => ({ ...prev, loading }));
  };

  const setError = (error: string | null) => {
    setState((prev) => ({ ...prev, error }));
  };

  const clearError = () => {
    setError(null);
  };

  // Authentication methods
  const loginAsGuest = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await authAPI.createGuest();
      setState((prev) => ({
        ...prev,
        isAuthenticated: true,
        player: response.player,
        loading: false,
        sessionState: SessionState.RETURNING_USER,
      }));
      setPlayerId(response.player.player_id);
      setStoredUsername(response.player.username);

      // Associate visitor with new account
      if (state.visitorId) {
        associateVisitorWithPlayer(state.visitorId, response.player.username);
      }
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('login-guest', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, [state.visitorId]);

  const login = useCallback(async (username: string, password: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await authAPI.login({ username, password });
      setState((prev) => ({
        ...prev,
        isAuthenticated: true,
        player: response.player,
        loading: false,
        sessionState: SessionState.RETURNING_USER,
      }));
      setPlayerId(response.player.player_id);
      setStoredUsername(response.player.username);
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('login', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, []);

  const register = useCallback(async (username: string, email: string, password: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await authAPI.register({ username, email, password });
      setState((prev) => ({
        ...prev,
        isAuthenticated: true,
        player: response.player,
        loading: false,
        sessionState: SessionState.RETURNING_USER,
      }));
      setPlayerId(response.player.player_id);
      setStoredUsername(response.player.username);

      // Associate visitor with new account
      if (state.visitorId) {
        associateVisitorWithPlayer(state.visitorId, response.player.username);
      }
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('register', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, [state.visitorId]);

  const logout = useCallback(async () => {
    try {
      await authAPI.logout();
    } catch {
      // Ignore logout errors
    } finally {
      setState((prev) => ({
        isAuthenticated: false,
        player: null,
        activeSet: null,
        pendingResults: [],
        loading: false,
        error: null,
        hasSubmittedEntry: false,
        hasVoted: false,
        sessionState: SessionState.RETURNING_VISITOR,
        visitorId: prev.visitorId,  // Keep visitor ID after logout
      }));
      clearGameStorage();
      clearStoredUsername();
    }
  }, []);

  const upgradeGuest = useCallback(async (username: string, email: string, password: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await authAPI.upgradeGuest({ username, email, password });
      setState((prev) => ({
        ...prev,
        player: response.player,
        loading: false,
      }));
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('upgrade-account', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, []);

  // Game methods
  const startBackronymBattle = useCallback(async (): Promise<StartSessionResponse> => {
    try {
      setLoading(true);
      setError(null);
      const response = await gameAPI.startSession();

      // Fetch complete set details to ensure we have accurate, server-authoritative data
      let activeSet: BackronymSet | null = null;
      try {
        const setStatus = await gameAPI.getSetStatus(response.set_id);
        activeSet = setStatus.set;
      } catch (err: unknown) {
        console.warn('Failed to fetch complete set details after starting battle:', err);
        // Fallback: at least we have the basic response, but UI should handle null activeSet gracefully
      }

      setState((prev) => ({
        ...prev,
        activeSet,
        hasSubmittedEntry: false,
        hasVoted: false,
        loading: false,
      }));
      setActiveSetId(response.set_id);
      return response;
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('start-battle', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, []);

  const submitBackronym = useCallback(async (setId: string, words: string[]) => {
    try {
      setLoading(true);
      setError(null);
      const data: SubmitBackronymRequest = { words };
      await gameAPI.submitBackronym(setId, data);
      setState((prev) => ({
        ...prev,
        hasSubmittedEntry: true,
        loading: false,
      }));
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('submit-backronym', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, []);

  const validateBackronym = useCallback(async (setId: string, words: string[]) => {
    try {
      const data: ValidateBackronymRequest = { words };
      return await gameAPI.validateBackronym(setId, data);
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('validate-backronym', err);
      setError(errorMessage);
      throw err;
    }
  }, []);

  const submitVote = useCallback(async (setId: string, entryId: string) => {
    try {
      setLoading(true);
      setError(null);
      const data: SubmitVoteRequest = { entry_id: entryId };
      await gameAPI.submitVote(setId, data);
      setState((prev) => ({
        ...prev,
        hasVoted: true,
        loading: false,
      }));
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('submit-vote', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, []);

  const claimDailyBonus = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await playerAPI.claimDailyBonus();
      setState((prev) => ({
        ...prev,
        player: prev.player
          ? {
              ...prev.player,
              wallet: response.new_balance,
              daily_bonus_available: false,
            }
          : null,
        loading: false,
      }));
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('claim-bonus', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, []);

  const refreshDashboard = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const dashboard: DashboardData = await playerAPI.getDashboard();

      // If there's an active session, fetch complete set details to get accurate data
      let activeSet: BackronymSet | null = null;
      if (dashboard.active_session) {
        try {
          const setStatus = await gameAPI.getSetStatus(dashboard.active_session.set_id);
          activeSet = setStatus.set;
        } catch (err: unknown) {
          // If fetching set status fails, log the error but don't fail the entire dashboard refresh
          console.warn('Failed to fetch set status for active session:', err);
          // Continue with null activeSet - user will see they have an active session but without details
        }
      }

      setState((prev) => ({
        ...prev,
        player: dashboard.player,
        pendingResults: dashboard.pending_results,
        activeSet,
        hasSubmittedEntry: dashboard.active_session?.has_submitted_entry || false,
        hasVoted: dashboard.active_session?.has_voted || false,
        loading: false,
      }));

      if (dashboard.active_session) {
        setActiveSetId(dashboard.active_session.set_id);
      } else {
        setActiveSetId(null);
      }
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('load-dashboard', err);
      setError(errorMessage);
      setLoading(false);
      throw err;
    }
  }, []);

  const checkSetStatus = useCallback(async (setId: string) => {
    try {
      const statusResponse = await gameAPI.getSetStatus(setId);
      setState((prev) => ({
        ...prev,
        activeSet: statusResponse.set,
        hasSubmittedEntry: statusResponse.player_has_submitted,
        hasVoted: statusResponse.player_has_voted,
      }));
    } catch (err: unknown) {
      const errorMessage = getActionErrorMessage('check-set-status', err);
      console.error(errorMessage, err);
    }
  }, []);

  const contextValue: IRGameContextType = {
    ...state,
    loginAsGuest,
    login,
    register,
    logout,
    upgradeGuest,
    startBackronymBattle,
      submitBackronym,
      validateBackronym,
      submitVote,
      claimDailyBonus,
    refreshDashboard,
    checkSetStatus,
    clearError,
  };

  return <IRGameContext.Provider value={contextValue}>{children}</IRGameContext.Provider>;
};
