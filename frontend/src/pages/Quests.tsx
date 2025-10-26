import React, { useState, useEffect } from 'react';
import { useGame } from '../contexts/GameContext';
import { useQuests } from '../contexts/QuestContext';
import { Header } from '../components/Header';
import { QuestCard } from '../components/QuestCard';
import { SuccessNotification } from '../components/SuccessNotification';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { QuestCategory } from '../api/types';

export const Quests: React.FC = () => {
  const { state, actions } = useGame();
  const { player } = state;
  const { claimBonus } = actions;
  const [isClaiming, setIsClaiming] = useState(false);

  // Quest context
  const {
    quests,
    activeQuests,
    claimableQuests,
    loading: questsLoading,
    error: questError,
    refreshQuests,
    claimQuest
  } = useQuests();

  // Filter and notification state
  const [selectedCategory, setSelectedCategory] = useState<QuestCategory | 'all'>('all');
  const [successMessage, setSuccessMessage] = useState<string>('');

  // Load quests on mount
  useEffect(() => {
    refreshQuests();
  }, [refreshQuests]);

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
      setSuccessMessage(`Daily bonus claimed! +${player.daily_bonus_amount}f`);
      // Refresh quests after claiming daily bonus (might unlock daily quests)
      await refreshQuests();
    } catch (err) {
      console.error('❌ Claim bonus failed:', err);
      // Error is already handled in context
    } finally {
      setIsClaiming(false);
      console.log('🔄 Claim process finished, resetting state');
    }
  };

  const handleClaimQuest = async (questId: string) => {
    try {
      const result = await claimQuest(questId);
      setSuccessMessage(`Quest reward claimed! +${result.reward_amount}f`);
      // refreshQuests is already called in claimQuest
    } catch (err) {
      console.error('Failed to claim quest:', err);
      // Error is already handled in context
    }
  };

  // Filter quests by category
  const filteredQuests = selectedCategory === 'all'
    ? quests
    : quests.filter(q => q.category === selectedCategory);

  const filteredActiveQuests = selectedCategory === 'all'
    ? activeQuests
    : activeQuests.filter(q => q.category === selectedCategory);

  const filteredClaimableQuests = selectedCategory === 'all'
    ? claimableQuests
    : claimableQuests.filter(q => q.category === selectedCategory);

  const claimedQuests = filteredQuests.filter(q => q.status === 'claimed');

  // Get category counts
  const getCategoryCounts = () => {
    return {
      all: quests.length,
      streak: quests.filter(q => q.category === 'streak').length,
      quality: quests.filter(q => q.category === 'quality').length,
      activity: quests.filter(q => q.category === 'activity').length,
      milestone: quests.filter(q => q.category === 'milestone').length,
    };
  };

  const categoryCounts = getCategoryCounts();

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
                    Claim <CurrencyDisplay amount={player.daily_bonus_amount} iconClassName="w-4 h-4" textClassName="text-base" /> Flipcoins
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

        {/* Success Notification */}
        {successMessage && (
          <SuccessNotification
            message={successMessage}
            onDismiss={() => setSuccessMessage('')}
          />
        )}

        {/* Quests Section */}
        <div className="tile-card p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-quip-orange rounded-tile flex items-center justify-center">
              <span className="text-2xl">🎯</span>
            </div>
            <div>
              <h2 className="text-2xl font-display font-bold text-quip-orange-deep">Quests</h2>
              <p className="text-quip-teal">Complete challenges to earn extra rewards</p>
            </div>
          </div>

          {/* Summary Stats */}
          {!questsLoading && quests.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
              <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4 border-2 border-green-200 dark:border-green-700">
                <p className="text-sm text-gray-600 dark:text-gray-400">Claimable Rewards</p>
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">{claimableQuests.length}</p>
              </div>
              <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 border-2 border-blue-200 dark:border-blue-700">
                <p className="text-sm text-gray-600 dark:text-gray-400">Active Quests</p>
                <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{activeQuests.length}</p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-900/20 rounded-lg p-4 border-2 border-gray-200 dark:border-gray-700">
                <p className="text-sm text-gray-600 dark:text-gray-400">Total Quests</p>
                <p className="text-2xl font-bold text-gray-600 dark:text-gray-400">{quests.length}</p>
              </div>
            </div>
          )}

          {/* Category Filter Tabs */}
          <div className="flex flex-wrap gap-2 mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
            <button
              onClick={() => setSelectedCategory('all')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                selectedCategory === 'all'
                  ? 'bg-quip-turquoise text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              All ({categoryCounts.all})
            </button>
            <button
              onClick={() => setSelectedCategory('streak')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                selectedCategory === 'streak'
                  ? 'bg-orange-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              🔥 Streaks ({categoryCounts.streak})
            </button>
            <button
              onClick={() => setSelectedCategory('quality')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                selectedCategory === 'quality'
                  ? 'bg-purple-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              ⭐ Quality ({categoryCounts.quality})
            </button>
            <button
              onClick={() => setSelectedCategory('activity')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                selectedCategory === 'activity'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              ⚡ Activity ({categoryCounts.activity})
            </button>
            <button
              onClick={() => setSelectedCategory('milestone')}
              className={`px-4 py-2 rounded-lg font-medium transition-all ${
                selectedCategory === 'milestone'
                  ? 'bg-yellow-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              🏆 Milestones ({categoryCounts.milestone})
            </button>
          </div>

          {/* Error State */}
          {questError && (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">⚠️</div>
              <h3 className="text-xl font-display font-bold text-red-600 mb-2">Failed to Load Quests</h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">{questError}</p>
              <button
                onClick={() => refreshQuests()}
                className="bg-quip-turquoise hover:bg-quip-teal text-white font-bold py-2 px-6 rounded-lg transition-all"
              >
                Retry
              </button>
            </div>
          )}

          {/* Loading State */}
          {!questError && questsLoading && (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">⏳</div>
              <p className="text-gray-600 dark:text-gray-400">Loading quests...</p>
            </div>
          )}

          {/* Empty State */}
          {!questError && !questsLoading && quests.length === 0 && (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🎯</div>
              <h3 className="text-xl font-display font-bold text-quip-navy mb-2">No Quests Available</h3>
              <p className="text-quip-teal">
                Complete some rounds to unlock quest challenges!
              </p>
            </div>
          )}

          {/* Claimable Quests */}
          {!questsLoading && filteredClaimableQuests.length > 0 && (
            <div className="mb-8">
              <h3 className="text-xl font-bold text-green-600 dark:text-green-400 mb-4 flex items-center gap-2">
                🎉 Claimable Quests ({filteredClaimableQuests.length})
              </h3>
              <div className="space-y-4">
                {filteredClaimableQuests.map((quest) => (
                  <QuestCard
                    key={quest.quest_id}
                    quest={quest}
                    onClaim={handleClaimQuest}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Active Quests */}
          {!questsLoading && filteredActiveQuests.length > 0 && (
            <div className="mb-8">
              <h3 className="text-xl font-bold text-blue-600 dark:text-blue-400 mb-4">
                Active Quests ({filteredActiveQuests.length})
              </h3>
              <div className="space-y-4">
                {filteredActiveQuests.map((quest) => (
                  <QuestCard
                    key={quest.quest_id}
                    quest={quest}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Claimed Quests */}
          {!questsLoading && claimedQuests.length > 0 && (
            <div>
              <h3 className="text-xl font-bold text-gray-600 dark:text-gray-400 mb-4">
                Claimed Quests ({claimedQuests.length})
              </h3>
              <div className="space-y-4">
                {claimedQuests.map((quest) => (
                  <QuestCard
                    key={quest.quest_id}
                    quest={quest}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Empty Filter State */}
          {!questsLoading && quests.length > 0 && filteredQuests.length === 0 && (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">🔍</div>
              <p className="text-gray-600 dark:text-gray-400">
                No quests in this category
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};