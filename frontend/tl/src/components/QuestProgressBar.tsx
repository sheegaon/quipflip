import React from 'react';
import { QuestCategory } from '@crowdcraft/api/types.ts';

interface QuestProgressBarProps {
  current: number;
  target: number;
  category: QuestCategory;
  showLabel?: boolean;
  className?: string;
}

export const QuestProgressBar: React.FC<QuestProgressBarProps> = ({
  current,
  target,
  category,
  showLabel = true,
  className = ''
}) => {
  // Calculate percentage (capped at 100%)
  const percentage = Math.min((current / target) * 100, 100);
  const isNearComplete = percentage >= 80;

  // Get color gradient based on category
  const getCategoryGradient = (cat: QuestCategory): string => {
    switch (cat) {
      case 'streak':
        return 'bg-gradient-to-r from-orange-500 to-red-500';
      case 'quality':
        return 'bg-gradient-to-r from-purple-500 to-pink-500';
      case 'activity':
        return 'bg-gradient-to-r from-blue-500 to-cyan-500';
      case 'milestone':
        return 'bg-gradient-to-r from-yellow-500 to-amber-500';
      default:
        return 'bg-gradient-to-r from-ccl-turquoise to-teal-500';
    }
  };

  const gradient = getCategoryGradient(category);

  return (
    <div className={`w-full ${className}`}>
      {/* Progress Bar Container */}
      <div className="relative w-full h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        {/* Progress Fill */}
        <div
          className={`h-full ${gradient} transition-all duration-500 ease-out ${
            isNearComplete ? 'animate-pulse' : ''
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Progress Label */}
      {showLabel && (
        <div className="flex justify-between items-center mt-1 text-xs text-gray-600 dark:text-gray-400">
          <span className="font-medium">
            {current} / {target}
          </span>
          <span className="text-gray-500">
            {Math.round(percentage)}%
          </span>
        </div>
      )}
    </div>
  );
};
