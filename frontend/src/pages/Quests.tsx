import React, { useEffect, useState } from 'react';
import { useGame } from '../contexts/GameContext';
import { useQuests } from '../contexts/QuestContext';
import { Header } from '../components/Header';
import { QuestCard } from '../components/QuestCard';
import { SuccessNotification } from '../components/SuccessNotification';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import type { Quest } from '../api/types';
import { questsLogger } from '../utils/logger';

// Quest categories for filtering
const QUEST_CATEGORIES = ['all', 'streak', 'quality', 'activity', 'milestone'] as const;
type QuestCategory = typeof QUEST_CATEGORIES[number];

export const Quests: React.FC = () => {
  const { state: gameState, actions: gameActions } = useGame();
  const { player } = gameState;
  const { claimBonus } = gameActions;
  const [isClaiming, setIsClaiming] = useState(false);

  const { state: questState, actions: questActions } = useQuests();
  const {
    quests,
    activeQuests,
    claimableQuests,
    loading: questsLoading,
    error: questError,
  } = questState;
  const { refreshQuests, claimQuest } = questActions;

  const [selectedCategory, setSelectedCategory] = useState<QuestCategory>('all');
  const [successMessage, setSuccessMessage] = useState<string>('');

  useEffect(() => {
    questsLogger.debug('Quests page mounted', {
      totalQuests: quests.length,
      activeQuests: activeQuests.length,
      claimableQuests: claimableQuests.length,
    });
  }, [quests.length, activeQuests.length, claimableQuests.length]);

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
      questsLogger.info('Claiming daily bonus');
      await claimBonus();
      setSuccessMessage(`Daily bonus claimed! +${player.daily_bonus_amount}f`);
      await refreshQuests();
      questsLogger.info('Daily bonus claimed successfully');
    } catch (err) {
      questsLogger.error('Claim bonus failed', err);
    } finally {
      setIsClaiming(false);
      questsLogger.debug('Claim bonus flow completed');
    }
  };

  const handleClaimQuest = async (questId: string) => {
    try {
      questsLogger.info('Claiming quest reward', { questId });
      const result = await claimQuest(questId);
      setSuccessMessage(`Quest reward claimed! +${result.reward_amount}f`);
      questsLogger.info('Quest reward claimed successfully', {
        questId,
        reward: result.reward_amount,
      });
    } catch (err) {
      questsLogger.error('Failed to claim quest', err);
    }
  };

  const handleCategoryChange = (category: QuestCategory) => {
    questsLogger.debug('Quest category changed', { category });
    setSelectedCategory(category);
  };

  const filteredQuests = selectedCategory === 'all'
    ? quests
    : quests.filter((q: Quest) => q.category === selectedCategory);

  const filteredActiveQuests = selectedCategory === 'all'
    ? activeQuests
    : activeQuests.filter((q: Quest) => q.category === selectedCategory);

  const filteredClaimableQuests = selectedCategory === 'all'
    ? claimableQuests
    : claimableQuests.filter((q: Quest) => q.category === selectedCategory);

  const claimedQuests = filteredQuests.filter((q: Quest) => q.status === 'claimed');

  const categoryStats = {
    all: quests.length,
    streak: quests.filter((q: Quest) => q.category === 'streak').length,
    quality: quests.filter((q: Quest) => q.category === 'quality').length,
    activity: quests.filter((q: Quest) => q.category === 'activity').length,
    milestone: quests.filter((q: Quest) => q.category === 'milestone').length,
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Rewards & Quests</h1>
        </div>

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

        {successMessage && (
          <SuccessNotification
            message={successMessage}
            onDismiss={() => setSuccessMessage('')}
          />
        )}

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

          <div className="flex flex-wrap gap-2 mb-6 pb-4 border-b border-gray-200 dark:border-gray-700">
            {QUEST_CATEGORIES.map((category) => (
              <button
                key={category}
                onClick={() => handleCategoryChange(category)}
                className={`px-4 py-2 rounded-lg font-medium transition-all ${
                  selectedCategory === category
                    ? 'bg-quip-turquoise text-white'
                    : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                {category.charAt(0).toUpperCase() + category.slice(1)} ({categoryStats[category]})
              </button>
            ))}
          </div>

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

          {!questError && questsLoading && (
            <div className="text-center py-12">
              <div className="text-4xl mb-4">⏳</div>
              <p className="text-gray-600 dark:text-gray-400">Loading quests...</p>
            </div>
          )}

          {!questError && !questsLoading && quests.length === 0 && (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">🎯</div>
              <h3 className="text-xl font-display font-bold text-quip-navy mb-2">No Quests Available</h3>
              <p className="text-quip-teal">
                Complete some rounds to unlock quest challenges!
              </p>
            </div>
          )}

          {!questsLoading && filteredClaimableQuests.length > 0 && (
            <div className="mb-8">
              <h3 className="text-xl font-bold text-green-600 dark:text-green-400 mb-4 flex items-center gap-2">
                🎉 Claimable Quests ({filteredClaimableQuests.length})
              </h3>
              <div className="space-y-4">
                {filteredClaimableQuests.map((quest: Quest) => (
                  <QuestCard
                    key={quest.quest_id}
                    quest={quest}
                    onClaim={handleClaimQuest}
                  />
                ))}
              </div>
            </div>
          )}

          {!questsLoading && filteredActiveQuests.length > 0 && (
            <div className="mb-8">
              <h3 className="text-xl font-bold text-blue-600 dark:text-blue-400 mb-4">
                Active Quests ({filteredActiveQuests.length})
              </h3>
              <div className="space-y-4">
                {filteredActiveQuests.map((quest: Quest) => (
                  <QuestCard
                    key={quest.quest_id}
                    quest={quest}
                  />
                ))}
              </div>
            </div>
          )}

          {!questsLoading && claimedQuests.length > 0 && (
            <div>
              <h3 className="text-xl font-bold text-gray-600 dark:text-gray-400 mb-4">
                Claimed Quests ({claimedQuests.length})
              </h3>
              <div className="space-y-4">
                {claimedQuests.map((quest: Quest) => (
                  <QuestCard
                    key={quest.quest_id}
                    quest={quest}
                  />
                ))}
              </div>
            </div>
          )}

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