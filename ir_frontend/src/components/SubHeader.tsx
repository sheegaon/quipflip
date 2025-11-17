import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import { ResultsIcon } from './icons/EngagementIcons';
import { SettingsIcon } from './icons/NavigationIcons';
import { TreasureChestIcon } from './TreasureChestIcon';

const SubHeader: React.FC = () => {
  const navigate = useNavigate();
  const { player, pendingResults } = useIRGame();

  if (!player) {
    return null;
  }

  const hasPendingResults = pendingResults && pendingResults.length > 0;
  const pendingCount = pendingResults?.length || 0;

  return (
    <div className="bg-ir-warm-ivory shadow-tile-sm relative z-40">
      <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-1.5">
        <div className="flex justify-evenly items-center">
          {/* Pending Results Indicator */}
          {hasPendingResults && (
            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className={`flex items-center gap-1 rounded-full px-1 md:px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 ${
                pendingCount > 0
                  ? 'bg-ir-orange bg-opacity-10 text-ir-orange hover:bg-ir-orange hover:bg-opacity-20 focus-visible:ring-ir-orange'
                  : 'bg-gray-200 text-black hover:bg-gray-300 focus-visible:ring-gray-400'
              }`}
              title={`${pendingCount} pending result${pendingCount !== 1 ? 's' : ''}`}
              aria-label={`${pendingCount} pending result${pendingCount !== 1 ? 's' : ''}`}
            >
              <span>{pendingCount}</span>
              <ResultsIcon
                className={`h-5 w-5 md:h-7 md:w-7 ${pendingCount > 0 ? 'trophy-pulse' : ''}`}
                variant={pendingCount > 0 ? 'orange' : 'teal'}
              />
            </button>
          )}

          {/* Daily Bonus Indicator */}
          {player.daily_bonus_available && (
            <button
              onClick={() => navigate('/dashboard')}
              className="relative group"
              title="Daily bonus available!"
              aria-label="Daily bonus available!"
            >
              <TreasureChestIcon
                className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110"
                isAvailable={player.daily_bonus_available}
              />
            </button>
          )}

          {/* Settings Icon - Only shown for guest players */}
          {player.is_guest && (
            <button
              onClick={() => navigate('/dashboard')}
              className="group"
              title="Account settings"
              aria-label="Account settings"
            >
              <SettingsIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default SubHeader;
