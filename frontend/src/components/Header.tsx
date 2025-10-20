import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { BalanceFlipper } from './BalanceFlipper';
import { TreasureChestIcon } from './TreasureChestIcon';

export const Header: React.FC = () => {
  const { player, username, logout, claimBonus } = useGame();
  const navigate = useNavigate();
  const [isClaiming, setIsClaiming] = useState(false);

  if (!player) {
    return null;
  }

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
      <div className="max-w-6xl mx-auto px-4 py-3">
        <div className="flex justify-between items-center">
          {/* Left: Logo */}
          <div className="flex items-center">
            <img src="/quipflip_logo_horizontal_transparent.png" alt="Quipflip" className="h-12 w-auto" />
          </div>

          {/* Center: Username (clickable to stats) */}
          <div className="flex-1 text-center">
            <button
              onClick={() => navigate('/statistics')}
              className="text-sm md:text-lg text-quip-turquoise font-semibold hover:text-quip-teal transition-colors"
              title="View your statistics"
            >
              {player.username || username}
            </button>
          </div>

          {/* Right: Daily Bonus + Flipcoins + Logout */}
          <div className="flex items-center gap-4">
            {/* Daily Bonus Treasure Chest */}
            {player.daily_bonus_available && (
              <button
                onClick={handleClaimBonus}
                disabled={isClaiming}
                className="relative group"
                title={`Claim your $${player.daily_bonus_amount} daily bonus!`}
              >
                <TreasureChestIcon
                  className="w-10 h-10 transition-transform group-hover:scale-110"
                  isAvailable={true}
                />
              </button>
            )}

            <div className="flex items-center gap-2 tutorial-balance">
              <img src="/flipcoin.png" alt="Flipcoin" className="w-10 h-10" />
              <BalanceFlipper
                value={player.balance}
                className="text-3xl font-display font-bold text-quip-turquoise"
              />
            </div>
            <button onClick={logout} className="text-quip-teal hover:text-quip-turquoise" title="Logout">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
