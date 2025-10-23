import React, { useEffect } from 'react';
import { useGameStructured } from '../contexts/GameContext';

export const ErrorNotification: React.FC = () => {
  const { state, actions } = useGameStructured();
  const { error } = state;
  const { clearError } = actions;

  useEffect(() => {
    if (error) {
      // Auto-clear error after 5 seconds
      const timeout = setTimeout(() => {
        clearError();
      }, 5000);

      return () => clearTimeout(timeout);
    }
  }, [error, clearError]);

  if (!error) return null;

  return (
    <div className="fixed top-4 right-4 z-50 max-w-md">
      <div className="bg-red-500 text-white px-6 py-4 rounded-lg shadow-lg flex items-start">
        <div className="flex-1">
          <p className="font-semibold mb-1">Error</p>
          <p className="text-sm">{error}</p>
        </div>
        <button
          onClick={clearError}
          className="ml-4 text-white hover:text-gray-200 font-bold text-xl"
        >
          ×
        </button>
      </div>
    </div>
  );
};
