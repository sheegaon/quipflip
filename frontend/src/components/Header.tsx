import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { BalanceFlipper } from './BalanceFlipper';
import { TreasureChestIcon } from './TreasureChestIcon';

export const Header: React.FC = () => {
  const { player, username, logout, claimBonus, phrasesetSummary } = useGame();
  const navigate = useNavigate();
  const location = useLocation();
  const [isClaiming, setIsClaiming] = useState(false);

  // Show back arrow on Statistics, Tracking, and Results pages
  const showBackArrow = location.pathname === '/statistics' || location.pathname === '/tracking' || location.pathname === '/results';

  if (!player) {
    return null;
  }

  const inProgressPrompts = phrasesetSummary?.in_progress.prompts ?? 0;
  const inProgressCopies = phrasesetSummary?.in_progress.copies ?? 0;
  const showInProgressIndicator = inProgressPrompts + inProgressCopies > 0;
  const inProgressLabelParts: string[] = [];
  if (inProgressPrompts > 0) {
    inProgressLabelParts.push(`${inProgressPrompts} prompt${inProgressPrompts === 1 ? '' : 's'}`);
  }
  if (inProgressCopies > 0) {
    inProgressLabelParts.push(`${inProgressCopies} ${inProgressCopies === 1 ? 'copy' : 'copies'}`);
  }
  const inProgressLabel = inProgressLabelParts.length
    ? `In-progress rounds: ${inProgressLabelParts.join(' and ')}`
    : 'View your in-progress rounds';

  const handleClaimBonus = async () => {
    if (isClaiming) return;
    setIsClaiming(true);
    try {
      await claimBonus();
    } catch (err) {
      // Error is already handled in context
    } finally {
      setIsClaiming(false);
    }
  };

  return (
    <div className="bg-white shadow-tile-sm">
      <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-3">
        <div className="flex justify-between items-center">
          {/* Left: Logo + Back Arrow (on certain pages) */}
          <div className="flex items-center gap-1 md:gap-3">
            <button
              onClick={showBackArrow ? () => navigate('/dashboard') : undefined}
              className={`flex items-center gap-0 md:gap-2 ${showBackArrow ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}`}
              disabled={!showBackArrow}
              title={showBackArrow ? "Back to Dashboard" : undefined}
            >
              {showBackArrow && (
                <img
                  src="/icon_back_arrow.svg"
                  alt=""
                  className="w-4 h-4 md:w-6 md:h-6"
                  aria-hidden="true"
                />
              )}
              <img src="/large_icon.png" alt="Quipflip" className="h-10 w-auto" />
            </button>
            {showInProgressIndicator && (
              <button
                type="button"
                onClick={() => navigate('/tracking')}
                className="flex items-center gap-3 rounded-full bg-quip-cream px-3 py-1 text-xs font-semibold text-quip-navy transition-colors hover:bg-quip-teal-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-teal"
                title={inProgressLabel}
                aria-label={inProgressLabel}
              >
                {inProgressPrompts > 0 && (
                  <span className="flex items-center gap-1">
                    <span>{inProgressPrompts}</span>
                    <img
                      src="/icon_prompt.svg"
                      alt="Prompt rounds in progress"
                      className="h-5 w-5 md:h-7 md:w-7"
                    />
                  </span>
                )}
                {inProgressCopies > 0 && (
                  <span className="flex items-center gap-1">
                    <span>{inProgressCopies}</span>
                    <img
                      src="/icon_copy.svg"
                      alt="Copy rounds in progress"
                      className="h-5 w-5 md:h-7 md:w-7"
                    />
                  </span>
                )}
              </button>
            )}
          </div>

          {/* Center: Username (clickable to stats) */}
          <div className="flex-1 text-center">
            <button
              onClick={() => navigate('/statistics')}
              className="inline-flex items-center gap-0.5 md:gap-1.5 text-xs md:text-2xl text-quip-turquoise font-semibold hover:text-quip-teal transition-colors"
              title="View your statistics"
            >
              <span>{player.username || username}</span>
              <img
                src="/icon_stats.svg"
                alt=""
                className="w-4 h-4 md:h-7 md:w-7"
                aria-hidden="true"
              />
            </button>
          </div>

          {/* Right: Daily Bonus + Flipcoins + Logout */}
          <div className="flex items-center gap-1 md:gap-4">
            {/* Daily Bonus Treasure Chest */}
            {player.daily_bonus_available && (
              <button
                onClick={handleClaimBonus}
                disabled={isClaiming}
                className="relative group"
                title={`Claim your $${player.daily_bonus_amount} daily bonus!`}
              >
                <TreasureChestIcon
                  className="w-7 h-7 md:w-10 md:h-10 transition-transform group-hover:scale-110"
                  isAvailable={true}
                />
              </button>
            )}
              {/* Flipcoin Balance */}
              <div className="flex items-center gap-2 tutorial-balance">
              <img src="/flipcoin.png" alt="Flipcoin" className="w-6 h-6 md:w-10 md:h-10" />
              <BalanceFlipper
                value={player.balance}
                className="text-xl md:text-4xl font-display font-bold text-quip-turquoise"
              />
            </div>
              {/* Logout Button */}
            <button onClick={logout} className="text-quip-teal hover:text-quip-turquoise" title="Logout">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 md:h-9 w-6 md:w-9" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
