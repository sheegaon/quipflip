import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';

const SubHeader: React.FC = () => {
  const navigate = useNavigate();
  const { player, pendingResults } = useIRGame();

  if (!player) {
    return null;
  }

  const hasPendingResults = pendingResults && pendingResults.length > 0;
  const pendingCount = pendingResults?.length || 0;

  return (
    <div className="bg-gradient-to-r from-purple-500 to-indigo-500 shadow-md relative z-40">
      <div className="max-w-6xl mx-auto px-2 py-2 md:px-4 md:py-2">
        <div className="flex justify-evenly items-center gap-2">
          {/* Pending Results Indicator */}
          {hasPendingResults && (
            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 rounded-full bg-yellow-400 bg-opacity-90 px-3 py-1.5 text-xs font-bold text-gray-900 transition-all hover:bg-yellow-300 hover:scale-105 shadow-md"
              title={`${pendingCount} pending result${pendingCount !== 1 ? 's' : ''}`}
              aria-label={`${pendingCount} pending result${pendingCount !== 1 ? 's' : ''}`}
            >
              <span className="text-sm">{pendingCount}</span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
                />
              </svg>
            </button>
          )}

          {/* Upgrade Account - For guests */}
          {player.is_guest && (
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 rounded-full bg-white bg-opacity-20 backdrop-blur-sm px-3 py-1.5 text-xs font-semibold text-white transition-all hover:bg-opacity-30 border border-white/30"
              title="Upgrade to save your progress"
              aria-label="Upgrade to save your progress"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z"
                />
              </svg>
              <span className="hidden sm:inline">Upgrade</span>
            </button>
          )}

          {/* Daily Bonus Indicator */}
          {player.daily_bonus_available && (
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 rounded-full bg-green-400 bg-opacity-90 px-3 py-1.5 text-xs font-bold text-gray-900 transition-all hover:bg-green-300 hover:scale-105 shadow-md animate-pulse"
              title="Daily bonus available!"
              aria-label="Daily bonus available!"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span className="hidden sm:inline">Bonus!</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default SubHeader;
