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

    setHistory(prev => {
      // Don't add if it's the same as the last entry (e.g., page refresh)
      if (prev.length > 0 && prev[prev.length - 1] === currentPath) {
        return prev;
      }

      // Handle browser/manual back navigation by checking if the new path is the second-to-last
      if (prev.length > 1 && prev[prev.length - 2] === currentPath) {
        return prev.slice(0, -1); // It's a back navigation, so pop the stack
      }

      // Otherwise, it's a forward navigation
      return [...prev, currentPath];
    });
  }, [location.pathname]);

  const goBack = useCallback(() => {
    if (history.length === 0) {
      // No history, go to dashboard
      navigate('/dashboard');
      return;
    }

    // Remove the current page from history and go to the previous page
    setHistory(prev => {
      const newHistory = [...prev];
      newHistory.pop(); // Remove current page

      if (newHistory.length === 0) {
        // No more history, go to dashboard
        navigate('/dashboard');
        return [];
      }

      // Get the last page in history
      const previousPage = newHistory[newHistory.length - 1];
      newHistory.pop(); // Remove it from history since we're navigating to it

      navigate(previousPage);
      return newHistory;
    });
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
