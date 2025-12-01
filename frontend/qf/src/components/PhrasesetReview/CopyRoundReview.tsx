import React, { useState } from 'react';
import { FrozenTimer } from './FrozenTimer';
import { ReviewBackButton } from './ReviewBackButton';
import { BotIcon } from '@crowdcraft/components/icons/EngagementIcons.tsx';
import { CopyRoundIcon } from '@crowdcraft/components/icons/RoundIcons.tsx';

interface CopyRoundReviewProps {
  originalPhrase: string;
  copyPhrase: string;
  playerUsername: string;
  isAiPlayer?: boolean;
  copyNumber: 1 | 2;
  roundId?: string;
  existingHints?: string[] | null; // Pass hints from parent if they exist
  onSubmit: () => void;
  onBack: () => void;
  isPractice?: boolean;
}

export const CopyRoundReview: React.FC<CopyRoundReviewProps> = ({
  originalPhrase,
  copyPhrase,
  playerUsername,
  isAiPlayer = false,
  copyNumber,
  roundId,
  existingHints = null,
  onSubmit,
  onBack,
  isPractice = false,
}) => {
  const [isRevealed, setIsRevealed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showHints, setShowHints] = useState(false);

  const handleReveal = () => {
    setIsRevealed(true);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    onSubmit();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-ccl-turquoise to-ccl-teal flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <CopyRoundIcon className="w-8 h-8" aria-hidden="true" />
            <h1 className="text-3xl font-display font-bold text-ccl-navy">Copy Round</h1>
          </div>
          <p className="text-ccl-teal">Submit a similar phrase</p>
        </div>

        {/* Timer - frozen */}
        <div className="flex justify-center mb-6">
          <FrozenTimer displayTime="3:00" />
        </div>

        {/* Instructions */}
        <div className="bg-ccl-orange bg-opacity-10 border-2 border-ccl-orange rounded-tile p-4 mb-6">
          <p className="text-sm text-ccl-navy">
            <strong>💡 Your goal:</strong> You don't know the prompt! Write a phrase that <em>could have been the original</em> and might trick voters. Do NOT submit your best guess of the prompt.
          </p>
        </div>

        {/* Original Phrase */}
        <div className="bg-ccl-turquoise bg-opacity-5 border-2 border-ccl-turquoise rounded-tile p-6 mb-6 relative">
          <p className="text-sm text-ccl-teal mb-2 text-center font-medium">Original Phrase:</p>
          <p className="text-3xl text-center font-display font-bold text-ccl-turquoise">
            {originalPhrase}
          </p>
        </div>

        {/* AI Hints - Show existing hints or indicate they weren't generated */}
        {roundId && (
          <div className="mb-4 rounded-tile border border-ccl-turquoise/30 bg-white/80 p-4 shadow-tile-xs">
            {existingHints && existingHints.length > 0 ? (
              <>
                <button
                  type="button"
                  onClick={() => setShowHints((prev) => !prev)}
                  className="flex w-full items-center justify-between rounded-tile border border-ccl-turquoise/40 bg-ccl-turquoise/10 px-3 py-2 font-semibold text-ccl-teal transition hover:bg-ccl-turquoise/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ccl-turquoise"
                >
                  <span>{showHints ? 'Hide AI Hints' : 'Show AI Hints'}</span>
                  <span className="text-sm text-ccl-navy">{existingHints.length} suggestions</span>
                </button>
                {showHints && (
                  <div className="mt-3 space-y-3">
                    <p className="text-xs uppercase tracking-wide text-ccl-teal/80">
                      Mix and modify - make it your own!
                    </p>
                    <ul className="space-y-2">
                      {existingHints.map((hint, index) => (
                        <li
                          key={`${hint}-${index}`}
                          className="flex items-start gap-2 rounded-tile border border-ccl-turquoise/30 bg-white px-3 py-2 text-ccl-navy shadow-inner"
                        >
                          <span className="font-semibold text-ccl-turquoise">Hint {index + 1}:</span>
                          <span>{hint}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center">
                <div className="rounded-tile border border-gray-300 bg-gray-50 px-4 py-3 text-ccl-navy">
                  <p className="font-semibold">Hints were not generated for this prompt</p>
                  <p className="mt-1 text-sm text-ccl-teal">
                    AI hints were not requested during the original copy round.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Copy Phrase Input - Click to reveal */}
        <div className="space-y-4 mb-4">
          <div>
            <div
              onClick={!isRevealed ? handleReveal : undefined}
              className={`w-full px-4 py-3 text-lg border-2 rounded-tile relative ${
                !isRevealed
                  ? 'border-ccl-teal bg-ccl-teal bg-opacity-5 cursor-pointer hover:bg-opacity-10 transition-all'
                  : 'border-ccl-turquoise bg-white'
              }`}
              title={!isRevealed ? 'Click to reveal the submitted phrase' : undefined}
            >
              {!isRevealed ? (
                <div className="flex items-center justify-center py-1">
                  <span className="text-ccl-teal font-semibold">Click to reveal phrase</span>
                </div>
              ) : (
                <span className="text-ccl-navy">{copyPhrase}</span>
              )}
              {!isRevealed && (
                <div className="absolute inset-0 bg-ccl-navy bg-opacity-5 rounded-tile pointer-events-none backdrop-blur-[2px]" />
              )}
            </div>
            <p className="text-sm text-ccl-teal mt-1">
              2-5 words (4-100 characters), A-Z and spaces only, must be different from the original, no proper nouns
            </p>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!isRevealed || isSubmitting}
            className="w-full bg-ccl-turquoise hover:bg-ccl-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all text-lg disabled:cursor-not-allowed"
          >
            {isSubmitting
              ? 'Submitting...'
              : isPractice && copyNumber === 2
                ? 'Submit'
                : copyNumber === 1
                  ? 'Continue to Second Copy'
                  : 'Continue to Vote Round'}
          </button>
        </div>

        {/* Back Button with Eye Icon */}
        <ReviewBackButton onClick={onBack} disabled={isSubmitting} />

        {/* Player info */}
        <div className="mt-6 p-4 bg-ccl-turquoise bg-opacity-5 rounded-tile text-center">
          <p className="text-sm text-ccl-teal flex items-center justify-center gap-1.5">
            <strong className="text-ccl-navy">Round played by:</strong>
            <span className="flex items-center gap-1">
              {playerUsername}
              {isAiPlayer && <BotIcon className="h-4 w-4" />}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
};
