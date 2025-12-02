import React from 'react';
import { TreasureChestIcon } from './icons/TreasureChestIcon';
import { CopyRoundIcon } from './icons/RoundIcons';
import { LeaderboardIcon, LobbyIcon, TrackingIcon } from './icons/NavigationIcons';
import { QuestionMarkIcon, ResultsIcon, ReviewIcon } from './icons/EngagementIcons';

export interface SubHeaderProps {
  showInProgressIndicator: boolean;
  inProgressPrompts: number;
  inProgressCopies: number;
  inProgressLabel: string;
  showResultsIndicator: boolean;
  resultsLabel: string;
  unviewedCount: number;
  isFirstDay: boolean;
  hasClaimableQuests: boolean;
  playerHasDailyBonus?: boolean;
  showQuestionMark: boolean;
  onTrackingClick?: () => void;
  onResultsClick: () => void | Promise<void>;
  onCompletedClick?: () => void;
  onLeaderboardClick?: () => void;
  onOnlineUsersClick: () => void;
  onTutorialClick?: () => void;
  onQuestsClick?: () => void;
}

export const SubHeader: React.FC<SubHeaderProps> = ({
  showInProgressIndicator,
  inProgressPrompts,
  inProgressCopies,
  inProgressLabel,
  showResultsIndicator,
  resultsLabel,
  unviewedCount,
  isFirstDay,
  hasClaimableQuests,
  playerHasDailyBonus,
  showQuestionMark,
  onTrackingClick,
  onResultsClick,
  onCompletedClick,
  onLeaderboardClick,
  onOnlineUsersClick,
  onTutorialClick,
  onQuestsClick,
}) => (
  <div className="bg-ccl-warm-ivory shadow-tile-sm relative z-40">
    <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-1.5">
      <div className="flex justify-center items-center gap-4 md:gap-6 flex-wrap">
        {/* In-progress indicator */}
        {showInProgressIndicator && (
          <button
            type="button"
            onClick={onTrackingClick}
            className="flex items-center gap-2 rounded-full bg-ccl-cream px-1 md:px-3 py-1 text-xs font-semibold text-ccl-navy transition-colors hover:bg-ccl-teal-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ccl-teal"
            title={inProgressLabel}
            aria-label={inProgressLabel}
          >
            {inProgressPrompts > 0 && (
              <span className="flex items-center md:gap-1 gap-0.5">
                <span>{inProgressPrompts}</span>
                <TrackingIcon className="h-5 w-5 md:h-7 md:w-7" />
              </span>
            )}
            {inProgressCopies > 0 && (
              <span className="flex items-center md:gap-1 gap-0.5">
                <span>{inProgressCopies}</span>
                <CopyRoundIcon className="h-5 w-5 md:h-7 md:w-7" aria-hidden="true" />
              </span>
            )}
          </button>
        )}

        {/* Results indicator */}
        {showResultsIndicator && (
          <button
            type="button"
            onClick={onResultsClick}
            className={`flex items-center gap-1 rounded-full px-1 md:px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 ${
              unviewedCount > 0
                ? 'bg-ccl-orange bg-opacity-10 text-ccl-orange hover:bg-ccl-orange hover:bg-opacity-20 focus-visible:ring-ccl-orange'
                : 'bg-gray-200 text-black hover:bg-gray-300 focus-visible:ring-gray-400'
            }`}
            title={resultsLabel}
            aria-label={resultsLabel}
          >
            <span>{unviewedCount}</span>
            <ResultsIcon
              className={`h-5 w-5 md:h-7 md:w-7 ${unviewedCount > 0 ? 'trophy-pulse' : ''}`}
              variant={unviewedCount > 0 ? 'orange' : 'teal'}
            />
          </button>
        )}

        {/* Completed rounds icon - Hidden on first day */}
        {!isFirstDay && onCompletedClick && (
          <button
            onClick={onCompletedClick}
            className="group tutorial-completed-icon"
            title="View completed rounds"
            aria-label="View completed rounds"
          >
            <ReviewIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
          </button>
        )}

        {/* Leaderboard icon - Hidden on first day */}
        {!isFirstDay && onLeaderboardClick && (
          <button
            onClick={onLeaderboardClick}
            className="group"
            title="View the leaderboard"
            aria-label="View the leaderboard"
          >
            <LeaderboardIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
          </button>
        )}

        {/* Online Users icon */}
        <button
          onClick={onOnlineUsersClick}
          className="group"
          title="View who's online"
          aria-label="View who's online"
        >
          <LobbyIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
        </button>

        {/* Tutorial icon - Only shown if tutorial not completed */}
        {showQuestionMark && onTutorialClick && (
          <button
            onClick={onTutorialClick}
            className="group"
            title="Start or resume tutorial"
            aria-label="Start or resume tutorial"
          >
            <QuestionMarkIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
          </button>
        )}

        {/* Treasure chest - Hidden on first day */}
        {!isFirstDay && onQuestsClick && (
          <button
            onClick={onQuestsClick}
            className="relative group"
            title={playerHasDailyBonus || hasClaimableQuests ? 'View available rewards' : 'No rewards available'}
          >
            <TreasureChestIcon
              className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110"
              isAvailable={playerHasDailyBonus || hasClaimableQuests}
            />
          </button>
        )}
      </div>
    </div>
  </div>
);

export default SubHeader;
