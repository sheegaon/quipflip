/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate, type Location } from 'react-router-dom';

interface NavigationHistoryContextType {
  canGoBack: boolean;
  goBack: () => void;
  clearHistory: () => void;
}

const NavigationHistoryContext = createContext<NavigationHistoryContextType | undefined>(undefined);

export const NavigationHistoryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [history, setHistory] = useState<Pick<Location, 'pathname' | 'search' | 'hash' | 'state'>[]>([]);

  const isSameLocation = useCallback(
    (
      a: Pick<Location, 'pathname' | 'search' | 'hash' | 'state'>,
      b: Pick<Location, 'pathname' | 'search' | 'hash' | 'state'>,
    ) => {
      const stateA = a.state === undefined ? null : a.state;
      const stateB = b.state === undefined ? null : b.state;

      return (
        a.pathname === b.pathname &&
        a.search === b.search &&
        a.hash === b.hash &&
        JSON.stringify(stateA) === JSON.stringify(stateB)
      );
    },
    [],
  );

  useEffect(() => {
    const currentLocation = {
      pathname: location.pathname,
      search: location.search,
      hash: location.hash,
      state: location.state,
    };

    // If we're on the dashboard, clear the history
    if (currentLocation.pathname === '/dashboard') {
      setHistory([]);
      return;
    }

    setHistory(prev => {
      // Don't add if it's the same as the last entry (e.g., page refresh)
      if (prev.length > 0 && isSameLocation(prev[prev.length - 1], currentLocation)) {
        return prev;
      }

      // Handle browser/manual back navigation by checking if the new path is the second-to-last
      if (prev.length > 1 && isSameLocation(prev[prev.length - 2], currentLocation)) {
        return prev.slice(0, -1); // It's a back navigation, so pop the stack
      }

      // Otherwise, it's a forward navigation
      return [...prev, currentLocation];
    });
  }, [isSameLocation, location.hash, location.pathname, location.search, location.state]);

  const goBack = useCallback(() => {
    // The robust useEffect ensures the history is a reliable stack.
    // history is [..., previousPage, currentPage]. We navigate to previousPage.
    if (history.length > 1) {
      const previousLocation = history[history.length - 2];
      navigate(
        {
          pathname: previousLocation.pathname,
          search: previousLocation.search,
          hash: previousLocation.hash,
        },
        { state: previousLocation.state },
      );
    } else {
      // If there's no real history, fall back to the dashboard.
      navigate('/dashboard');
    }
  }, [history, navigate]);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  const canGoBack = history.length > 0 || location.pathname !== '/dashboard';

  return (
    <NavigationHistoryContext.Provider value={{ canGoBack, goBack, clearHistory }}>
      {children}
    </NavigationHistoryContext.Provider>
  );
};

export const useNavigationHistory = () => {
  const context = useContext(NavigationHistoryContext);
  if (context === undefined) {
    throw new Error('useNavigationHistory must be used within a NavigationHistoryProvider');
  }
  return context;
};
