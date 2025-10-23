import React, { useState } from 'react';
import { useGame } from '../contexts/GameContext';
import { Header } from '../components/Header';

export const Quests: React.FC = () => {
  const { state, actions } = useGame();
  const { player } = state;
  const { claimBonus } = actions;
  const [isClaiming, setIsClaiming] = useState(false);

  if (!player) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl">Loading...</div>
      </div>
    );
  }

  const handleClaimBonus = async () => {
    console.log('🎁 Claim bonus button clicked');
    console.log('🔍 claimBonus function:', claimBonus);
    console.log('🔍 claimBonus function type:', typeof claimBonus);
    
    if (isClaiming) {
      console.log('❌ Already claiming, ignoring click');
      return;
    }
    
    console.log('✅ Starting claim process...');
    setIsClaiming(true);
    try {
      console.log('📞 Calling claimBonus action...');
      await claimBonus();
      console.log('✅ Claim bonus completed successfully');
    } catch (err) {
      console.error('❌ Claim bonus failed:', err);
      // Error is already handled in context
    } finally {
      setIsClaiming(false);
      console.log('🔄 Claim process finished, resetting state');
    }
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Rewards & Quests</h1>
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