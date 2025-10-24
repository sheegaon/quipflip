import React, { useState } from 'react';
import { Quest, QuestCategory, QuestStatus } from '../api/types';
import { QuestProgressBar } from './QuestProgressBar';

interface QuestCardProps {
  quest: Quest;
  onClaim?: (questId: string) => Promise<void>;
  className?: string;
}

export const QuestCard: React.FC<QuestCardProps> = ({
  quest,
  onClaim,
  className = ''
}) => {
  const [isClaiming, setIsClaiming] = useState(false);

  const handleClaim = async () => {
    if (!onClaim || isClaiming) return;

    setIsClaiming(true);
    try {
      await onClaim(quest.quest_id);
    } catch (error) {
      console.error('Failed to claim quest:', error);
    } finally {
      setIsClaiming(false);
    }
  };

  // Get category icon and color
  const getCategoryInfo = (category: QuestCategory) => {
    switch (category) {
      case 'streak':
        return { icon: '🔥', color: 'text-orange-600', bgColor: 'bg-orange-100 dark:bg-orange-900/20' };
      case 'quality':
        return { icon: '⭐', color: 'text-purple-600', bgColor: 'bg-purple-100 dark:bg-purple-900/20' };
      case 'activity':
        return { icon: '⚡', color: 'text-blue-600', bgColor: 'bg-blue-100 dark:bg-blue-900/20' };
      case 'milestone':
        return { icon: '🏆', color: 'text-yellow-600', bgColor: 'bg-yellow-100 dark:bg-yellow-900/20' };
      default:
        return { icon: '🎯', color: 'text-gray-600', bgColor: 'bg-gray-100 dark:bg-gray-900/20' };
    }
  };

  // Get status badge
  const getStatusBadge = (status: QuestStatus) => {
    switch (status) {
      case 'active':
        return (
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200">
            Active
          </span>
        );
      case 'completed':
        return (
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200">
            Completed
          </span>
        );
      case 'claimed':
        return (
          <span className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 dark:bg-gray-900/30 text-gray-600 dark:text-gray-400">
            Claimed
          </span>
        );
    }
  };

  // Extract tier from quest type (e.g., "hot_streak_5" -> "I", "hot_streak_10" -> "II")
  const getTier = (questType: string): string | null => {
    if (questType.includes('_5') || questType.includes('_10_')) return 'I';
    if (questType.includes('_10') && !questType.includes('_10_')) return 'II';
    if (questType.includes('_20') || questType.includes('_50')) return 'III';
    return null;
  };

  const categoryInfo = getCategoryInfo(quest.category);
  const tier = getTier(quest.quest_type);

  return (
    <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-md border border-gray-200 dark:border-gray-700 p-4 transition-all hover:shadow-lg ${className}`}>
      {/* Header: Icon, Name, Reward */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-start gap-2 flex-1">
          <div className={`text-2xl ${categoryInfo.color}`}>
            {categoryInfo.icon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-bold text-base text-gray-900 dark:text-white">
                {quest.name}
              </h3>
              {tier && (
                <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700">
                  Tier {tier}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              {quest.description}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 ml-2">
          <span className="font-bold text-lg text-quip-turquoise whitespace-nowrap">
            ${quest.reward_amount}
          </span>
          {getStatusBadge(quest.status)}
        </div>
      </div>

      {/* Progress Bar (only for active/completed quests) */}
      {quest.status !== 'claimed' && (
        <div className="mb-3">
          <QuestProgressBar
            current={quest.progress_current}
            target={quest.progress_target}
            category={quest.category}
            showLabel={true}
          />
        </div>
      )}

      {/* Category Badge and Claim Button */}
      <div className="flex items-center justify-between gap-2">
        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${categoryInfo.bgColor} ${categoryInfo.color}`}>
          {categoryInfo.icon}
          <span className="capitalize">{quest.category}</span>
        </span>

        {/* Claim Button (only for completed quests) */}
        {quest.status === 'completed' && onClaim && (
          <button
            onClick={handleClaim}
            disabled={isClaiming}
            className="px-4 py-2 bg-gradient-to-r from-quip-turquoise to-teal-500 text-white font-semibold text-sm rounded-lg hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isClaiming ? 'Claiming...' : 'Claim Reward'}
          </button>
        )}

        {/* Claimed indicator */}
        {quest.status === 'claimed' && quest.claimed_at && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Claimed {new Date(quest.claimed_at).toLocaleDateString()}
          </span>
        )}
      </div>
    </div>
  );
};
