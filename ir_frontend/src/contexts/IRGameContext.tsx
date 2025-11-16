import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type {
  IRPlayer,
  BackronymSet,
  PendingResult,
  DashboardData,
  StartSessionResponse,
  SubmitBackronymRequest,
  SubmitVoteRequest,
} from '../api/types';
import { authAPI, playerAPI, gameAPI } from '../api/client';
import { setActiveSetId, setPlayerId, clearGameStorage } from '../utils/gameKeys';

interface IRGameState {
  isAuthenticated: boolean;
  player: IRPlayer | null;
  activeSet: BackronymSet | null;
  pendingResults: PendingResult[];
  loading: boolean;
  error: string | null;
  hasSubmittedEntry: boolean;
  hasVoted: boolean;
}

interface IRGameContextType extends IRGameState {
  // Authentication
  loginAsGuest: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  upgradeGuest: (email: string, password: string) => Promise<void>;

  // Game actions
  startBackronymBattle: () => Promise<StartSessionResponse>;
  submitBackronym: (setId: string, words: string[]) => Promise<void>;
  submitVote: (setId: string, entryId: string) => Promise<void>;
  claimDailyBonus: () => Promise<void>;

  // Data fetching
  refreshDashboard: () => Promise<void>;
  checkSetStatus: (setId: string) => Promise<void>;

  // Utilities
  clearError: () => void;
}

const IRGameContext = createContext<IRGameContextType | undefined>(undefined);

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
  });

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
      }));
      setPlayerId(response.player.player_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create guest account');
      setLoading(false);
      throw err;
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await authAPI.login({ email, password });
      setState((prev) => ({
        ...prev,
        isAuthenticated: true,
        player: response.player,
        loading: false,
      }));
      setPlayerId(response.player.player_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed');
      setLoading(false);
      throw err;
    }
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await authAPI.register({ email, password });
      setState((prev) => ({
        ...prev,
        isAuthenticated: true,
        player: response.player,
        loading: false,
      }));
      setPlayerId(response.player.player_id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed');
      setLoading(false);
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await authAPI.logout();
    } catch (err) {
      // Ignore logout errors
    } finally {
      setState({
        isAuthenticated: false,
        player: null,
        activeSet: null,
        pendingResults: [],
        loading: false,
        error: null,
        hasSubmittedEntry: false,
        hasVoted: false,
      });
      clearGameStorage();
    }
  }, []);

  const upgradeGuest = useCallback(async (email: string, password: string) => {
    try {
      setLoading(true);
      setError(null);
      const response = await authAPI.upgradeGuest({ email, password });
      setState((prev) => ({
        ...prev,
        player: response.player,
        loading: false,
      }));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upgrade account');
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
      setState((prev) => ({
        ...prev,
        activeSet: {
          set_id: response.set_id,
          word: response.word,
          mode: response.mode as 'standard' | 'rapid',
          status: response.status as 'open' | 'voting' | 'finalized',
          entry_count: 0,
          vote_count: 0,
          non_participant_vote_count: 0,
          total_pool: 0,
          creator_final_pool: 0,
          created_at: new Date().toISOString(),
          transitions_to_voting_at: null,
          voting_finalized_at: null,
        },
        hasSubmittedEntry: false,
        hasVoted: false,
        loading: false,
      }));
      setActiveSetId(response.set_id);
      return response;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start battle');
      setLoading(false);
      throw err;
    }
  }, []);

  const submitBackronym = useCallback(async (setId: string, words: string[]) => {
    try {
      setLoading(true);
      setError(null);
      const data: SubmitBackronymRequest = { backronym_text: words };
      await gameAPI.submitBackronym(setId, data);
      setState((prev) => ({
        ...prev,
        hasSubmittedEntry: true,
        loading: false,
      }));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit backronym');
      setLoading(false);
      throw err;
    }
  }, []);

  const submitVote = useCallback(async (setId: string, entryId: string) => {
    try {
      setLoading(true);
      setError(null);
      const data: SubmitVoteRequest = { chosen_entry_id: entryId };
      await gameAPI.submitVote(setId, data);
      setState((prev) => ({
        ...prev,
        hasVoted: true,
        loading: false,
      }));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit vote');
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
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to claim daily bonus');
      setLoading(false);
      throw err;
    }
  }, []);

  const refreshDashboard = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const dashboard: DashboardData = await playerAPI.getDashboard();
      setState((prev) => ({
        ...prev,
        player: dashboard.player,
        pendingResults: dashboard.pending_results,
        activeSet: dashboard.active_session
          ? {
              set_id: dashboard.active_session.set_id,
              word: dashboard.active_session.word,
              mode: 'rapid',
              status: dashboard.active_session.status as 'open' | 'voting' | 'finalized',
              entry_count: 0,
              vote_count: 0,
              non_participant_vote_count: 0,
              total_pool: 0,
              creator_final_pool: 0,
              created_at: new Date().toISOString(),
              transitions_to_voting_at: null,
              voting_finalized_at: null,
            }
          : null,
        hasSubmittedEntry: dashboard.active_session?.has_submitted_entry || false,
        hasVoted: dashboard.active_session?.has_voted || false,
        loading: false,
      }));
      if (dashboard.active_session) {
        setActiveSetId(dashboard.active_session.set_id);
      } else {
        setActiveSetId(null);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to refresh dashboard');
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
    } catch (err: any) {
      console.error('Failed to check set status:', err);
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
    submitVote,
    claimDailyBonus,
    refreshDashboard,
    checkSetStatus,
    clearError,
  };

  return <IRGameContext.Provider value={contextValue}>{children}</IRGameContext.Provider>;
};
