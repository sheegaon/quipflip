import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { Header } from '../components/Header';

export const Quests: React.FC = () => {
  const { state, actions } = useGame();
  const { player } = state;
  const { claimBonus } = actions;
  const navigate = useNavigate();
  const [isClaiming, setIsClaiming] = useState(false);

  if (!player) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl">Loading...</div>
      </div>
    );
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
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-6 flex justify-between items-center">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Rewards & Quests</h1>
          <button
            onClick={() => navigate('/dashboard')}
            className="text-quip-teal hover:text-quip-turquoise font-medium inline-flex items-center gap-2 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            Back to Dashboard
          </button>
        </div>

        {/* Daily Bonus Section */}
        <div className="tile-card p-6 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <img src="/flipcoin.png" alt="Daily Bonus" className="w-12 h-12" />
            <div>
              <h2 className="text-2xl font-display font-bold text-quip-turquoise">Daily Bonus</h2>
              <p className="text-quip-teal">Claim your daily reward!</p>
            </div>
          </div>

          {player.daily_bonus_available ? (
            <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <p className="text-lg font-semibold text-quip-turquoise mb-1">
                    Your daily bonus is ready!
                  </p>
                  <p className="text-quip-teal">
                    Claim ${player.daily_bonus_amount} Flipcoins
                  </p>
                </div>
                <button
                  onClick={handleClaimBonus}
                  disabled={isClaiming}
                  className="bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
                >
                  {isClaiming ? 'Claiming...' : 'Claim Bonus'}
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-gray-100 border-2 border-gray-300 rounded-tile p-4">
              <div className="text-center">
                <p className="text-gray-600 mb-2">Daily bonus already claimed today</p>
                <p className="text-sm text-gray-500">Come back tomorrow for your next bonus!</p>
              </div>
            </div>
          )}
        </div>

        {/* Quests Section - Placeholder for future implementation */}
        <div className="tile-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 bg-quip-orange rounded-tile flex items-center justify-center">
              <span className="text-2xl">🎯</span>
            </div>
            <div>
              <h2 className="text-2xl font-display font-bold text-quip-orange-deep">Quests</h2>
              <p className="text-quip-teal">Complete challenges to earn extra rewards</p>
            </div>
          </div>

          <div className="text-center py-12">
            <div className="text-6xl mb-4">🚧</div>
            <h3 className="text-xl font-display font-bold text-quip-navy mb-2">Coming Soon!</h3>
            <p className="text-quip-teal">
              Exciting quest challenges are being prepared. Check back soon for new ways to earn rewards!
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};