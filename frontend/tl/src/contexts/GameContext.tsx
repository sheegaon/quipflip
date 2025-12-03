/**
 * Minimal ThinkLink GameContext
 * Simplified for TL's single game type (semantic matching rounds)
 */
import React, { createContext, useContext, useState, useEffect } from 'react';
import apiClient from '@/api/client';
import { detectUserSession } from '@crowdcraft/services/sessionDetection';
import { SessionState } from '@crowdcraft/types/session.ts';
import type { BalanceResponse, RoundAvailability } from '@/api/types';

interface TLPlayer {
  player_id: string;
  username: string;
  email?: string;
  is_guest?: boolean;
  is_admin?: boolean;
  tl_wallet: number;
  tl_vault: number;
  wallet?: number;
  vault?: number;
  tl_tutorial_completed: boolean;
  tl_tutorial_progress: string;
  created_at: string;
  daily_bonus_available?: boolean;
  daily_bonus_amount?: number;
  last_login_date?: string;
}

interface GameState {
  isAuthenticated: boolean;
  username: string | null;
  player: TLPlayer | null;
  showNewUserWelcome: boolean;
  balance: BalanceResponse | null;
  roundAvailability: RoundAvailability | null;
  loading: boolean;
  error: string | null;
  sessionState: SessionState;
  visitorId: string | null;
  phrasesetSummary?: any;
  pendingResults: any[];
}

interface GameActions {
  logout: () => Promise<void>;
  refreshDashboard: (signal?: AbortSignal) => Promise<void>;
  refreshBalance: (signal?: AbortSignal) => Promise<void>;
  clearError: () => void;
  abandonRound: (roundId: string) => Promise<any>;
  startSession: (username?: string, options?: any) => Promise<void>;
  claimBonus?: () => Promise<void>;
  dismissNewUserWelcome?: () => void;
}

interface GameContextType {
  state: GameState;
  actions: GameActions;
}

const GameContext = createContext<GameContextType | undefined>(undefined);

export const GameProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [player, setPlayer] = useState<TLPlayer | null>(null);
  const [showNewUserWelcome] = useState(false);
  const [balance, setBalance] = useState<BalanceResponse | null>(null);
  const [roundAvailability] = useState<RoundAvailability | null>(null);
  const [loading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionState, setSessionState] = useState<SessionState>(SessionState.CHECKING);
  const [visitorId, setVisitorId] = useState<string | null>(null);

  // Initialize session
  useEffect(() => {
    const initializeSession = async () => {
      try {
        const result = await detectUserSession();
        setSessionState(result.state);
        setVisitorId(result.visitorId);
        setIsAuthenticated(result.isAuthenticated);
        if (result.isAuthenticated && result.username) {
          setUsername(result.username);
        }
      } catch (err) {
        console.error('Session detection failed:', err);
        setSessionState(SessionState.RETURNING_VISITOR);
      }
    };

    initializeSession();
  }, []);

  const logout = async () => {
    try {
      await apiClient.logout();
      setIsAuthenticated(false);
      setUsername(null);
      setPlayer(null);
      setBalance(null);
    } catch (err) {
      console.error('Logout failed:', err);
      throw err;
    }
  };

  const refreshDashboard = async (signal?: AbortSignal) => {
    try {
      const dashboard = await apiClient.getDashboard(signal);
      const playerData: TLPlayer = {
        player_id: dashboard.player_id,
        username: dashboard.username,
        tl_wallet: dashboard.tl_wallet,
        tl_vault: dashboard.tl_vault,
        wallet: dashboard.tl_wallet,
        vault: dashboard.tl_vault,
        tl_tutorial_completed: dashboard.tl_tutorial_completed,
        tl_tutorial_progress: dashboard.tl_tutorial_progress,
        created_at: dashboard.created_at,
      };
      setPlayer(playerData);
      setIsAuthenticated(true);
      setError(null);
    } catch (err) {
      console.error('Failed to refresh dashboard:', err);
      if (!signal?.aborted) {
        setError('Failed to load dashboard');
      }
    }
  };

  const refreshBalance = async (signal?: AbortSignal) => {
    try {
      const balanceData = await apiClient.getBalance(signal);
      setBalance(balanceData);
    } catch (err) {
      console.error('Failed to refresh balance:', err);
    }
  };

  const clearError = () => setError(null);

  const abandonRound = async (roundId: string) => {
    try {
      return await apiClient.abandonRound(roundId);
    } catch (err) {
      console.error('Failed to abandon round:', err);
      throw err;
    }
  };

  const startSession = async (username?: string, options?: any) => {
    // TL doesn't have party/social features like MM/QF
    // Mark session as started and authenticate user
    if (username) {
      apiClient.setSession(username);
      setUsername(username);
      setIsAuthenticated(true);
      setSessionState(SessionState.RETURNING_USER);

      console.log('Session started', { username, options, authenticated: true });
    }
  };

  const state: GameState = {
    isAuthenticated,
    username,
    player,
    showNewUserWelcome,
    balance,
    roundAvailability,
    loading,
    error,
    sessionState,
    visitorId,
    pendingResults: [],
  };

  const actions: GameActions = {
    logout,
    refreshDashboard,
    refreshBalance,
    clearError,
    abandonRound,
    startSession,
  };

  return (
    <GameContext.Provider value={{ state, actions }}>
      {children}
    </GameContext.Provider>
  );
};

export const useGame = (): GameContextType => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
};

export default GameContext;
