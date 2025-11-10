import React, { useState } from 'react';
import { FrozenTimer } from './FrozenTimer';
import { ReviewBackButton } from './ReviewBackButton';
import apiClient, { extractErrorMessage } from '../../api/client';

interface CopyRoundReviewProps {
  originalPhrase: string;
  copyPhrase: string;
  playerUsername: string;
  copyNumber: 1 | 2;
  roundId?: string;
  onSubmit: () => void;
  onBack: () => void;
}

export const CopyRoundReview: React.FC<CopyRoundReviewProps> = ({
  originalPhrase,
  copyPhrase,
  playerUsername,
  copyNumber,
  roundId,
  onSubmit,
  onBack,
}) => {
  const [isRevealed, setIsRevealed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // null = not fetched yet, empty array = fetched but no hints, array with items = hints available
  const [copyRoundHints, setCopyRoundHints] = useState<string[] | null>(null);
  const [isFetchingHints, setIsFetchingHints] = useState(false);
  const [hintError, setHintError] = useState<string | null>(null);
  const [showHints, setShowHints] = useState(false);

  const handleReveal = () => {
    setIsRevealed(true);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    onSubmit();
  };

  const handleFetchHints = async () => {
    if (!roundId || isFetchingHints) {
      return;
    }

    setIsFetchingHints(true);
    setHintError(null);

    try {
      // Call API directly (not through GameContext) to avoid polluting shared state
      const response = await apiClient.getCopyHints(roundId);
      // Set hints (could be empty array if no hints available)
      setCopyRoundHints(response.hints || []);
      // Only auto-show hints if there are any
      if (response.hints && response.hints.length > 0) {
        setShowHints(true);
      }
    } catch (err: any) {
      // The hints API only works for active rounds, not completed rounds
      const errorMessage = extractErrorMessage(err);
      if (errorMessage.includes('active') || errorMessage.includes('not found')) {
        setHintError('AI hints are only available during active rounds, not for completed round reviews.');
      } else {
        setHintError(errorMessage || 'Unable to fetch AI hints.');
      }
    } finally {
      setIsFetchingHints(false);
    }
  };
  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-turquoise to-quip-teal flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <img src="/icon_copy.svg" alt="Copy round icon" className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Copy Round</h1>
          </div>
          <p className="text-quip-teal">Submit a similar phrase</p>
        </div>

        {/* Timer - frozen */}
        <div className="flex justify-center mb-6">
          <FrozenTimer displayTime="3:00" />
        </div>

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4 mb-6">
          <p className="text-sm text-quip-navy">
            <strong>💡 Tip:</strong> You don't know the prompt! Submit a phrase that could be <em>similar or related</em> to the phrase shown below. Do NOT submit your best guess of the prompt.
          </p>
        </div>

        {/* Original Phrase */}
        <div className="bg-quip-turquoise bg-opacity-5 border-2 border-quip-turquoise rounded-tile p-6 mb-6 relative">
          <p className="text-sm text-quip-teal mb-2 text-center font-medium">Original Phrase:</p>
          <p className="text-3xl text-center font-display font-bold text-quip-turquoise">
            {originalPhrase}
          </p>
        </div>

        {/* AI Hints */}
        {roundId && (
          <div className="mb-4 rounded-tile border border-quip-turquoise/30 bg-white/80 p-4 shadow-tile-xs">
            {copyRoundHints && copyRoundHints.length > 0 ? (
              // Case 1: Hints fetched and available
              <>
                <button
                  type="button"
                  onClick={() => setShowHints((prev) => !prev)}
                  className="flex w-full items-center justify-between rounded-tile border border-quip-turquoise/40 bg-quip-turquoise/10 px-3 py-2 font-semibold text-quip-teal transition hover:bg-quip-turquoise/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-turquoise"
                >
                  <span>{showHints ? 'Hide AI Hints' : 'Show AI Hints'}</span>
                  <span className="text-sm text-quip-navy">{copyRoundHints.length} suggestions</span>
                </button>
                {showHints && (
                  <div className="mt-3 space-y-3">
                    <p className="text-xs uppercase tracking-wide text-quip-teal/80">
                      Mix and modify - make it your own!
                    </p>
                    <ul className="space-y-2">
                      {copyRoundHints.map((hint, index) => (
                        <li
                          key={index}
                          className="flex items-start gap-2 rounded-tile border border-quip-turquoise/30 bg-white px-3 py-2 text-quip-navy shadow-inner"
                        >
                          <span className="font-semibold text-quip-turquoise">Hint {index + 1}:</span>
                          <span>{hint}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : copyRoundHints !== null && copyRoundHints.length === 0 ? (
              // Case 2: Hints fetched but none available
              <div className="text-center py-2">
                <p className="text-sm text-quip-teal">
                  No AI hints are available for this round.
                </p>
              </div>
            ) : (
              // Case 3: Not yet fetched
              <>
                <button
                  type="button"
                  onClick={handleFetchHints}
                  disabled={isFetchingHints || isSubmitting}
                  className="w-full rounded-tile border border-quip-turquoise bg-white px-4 py-2 font-semibold text-quip-turquoise transition hover:bg-quip-turquoise hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isFetchingHints ? 'Contacting AI...' : 'Get AI Hints'}
                </button>
                {hintError && <p className="mt-2 text-sm text-red-600">{hintError}</p>}
                <p className="mt-2 text-xs text-quip-teal">
                  You will get three ideas that passed quick AI checks. Use them as inspiration and tweak them to match your style. Hints may take up to one minute to generate.
                </p>
              </>
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
                  ? 'border-quip-teal bg-quip-teal bg-opacity-5 cursor-pointer hover:bg-opacity-10 transition-all'
                  : 'border-quip-turquoise bg-white'
              }`}
              title={!isRevealed ? 'Click to reveal the submitted phrase' : undefined}
            >
              {!isRevealed ? (
                <div className="flex items-center justify-center py-1">
                  <span className="text-quip-teal font-semibold">Click to reveal phrase</span>
                </div>
              ) : (
                <span className="text-quip-navy">{copyPhrase}</span>
              )}
              {!isRevealed && (
                <div className="absolute inset-0 bg-quip-navy bg-opacity-5 rounded-tile pointer-events-none backdrop-blur-[2px]" />
              )}
            </div>
            <p className="text-sm text-quip-teal mt-1">
              2-5 words (4-100 characters), A-Z and spaces only, must be different from the original
            </p>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!isRevealed || isSubmitting}
            className="w-full bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all text-lg disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Continuing...' : copyNumber === 1 ? 'Continue to Second Copy' : 'Continue to Vote Round'}
          </button>
        </div>

        {/* Back Button with Eye Icon */}
        <ReviewBackButton onClick={onBack} disabled={isSubmitting} />

        {/* Player info */}
        <div className="mt-6 p-4 bg-quip-turquoise bg-opacity-5 rounded-tile text-center">
          <p className="text-sm text-quip-teal">
            <strong className="text-quip-navy">Round played by:</strong> {playerUsername}
          </p>
        </div>
      </div>
    </div>
  );
};
