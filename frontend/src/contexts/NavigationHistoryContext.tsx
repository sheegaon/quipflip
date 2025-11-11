import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

interface NavigationHistoryContextType {
  canGoBack: boolean;
  goBack: () => void;
  clearHistory: () => void;
}

const NavigationHistoryContext = createContext<NavigationHistoryContextType | undefined>(undefined);

export const NavigationHistoryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [history, setHistory] = useState<string[]>([]);

  useEffect(() => {
    const currentPath = location.pathname;

    // If we're on the dashboard, clear the history
    if (currentPath === '/dashboard') {
      setHistory([]);
      return;
    }

    // Add the current path to history, but avoid duplicates if the user is on the same page
    setHistory(prev => {
      // Don't add if it's the same as the last entry
      if (prev.length > 0 && prev[prev.length - 1] === currentPath) {
        return prev;
      }
      return [...prev, currentPath];
    });
  }, [location.pathname]);

  const goBack = useCallback(() => {
    // The robust useEffect ensures the history is a reliable stack.
    // history is [..., previousPage, currentPage]. We navigate to previousPage.
    if (history.length > 1) {
      navigate(history[history.length - 2]);
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
