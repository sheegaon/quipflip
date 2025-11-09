import React, { useState } from 'react';
import { FrozenTimer } from './FrozenTimer';
import { ReviewBackButton } from './ReviewBackButton';
import { getRandomMessage } from '../../utils/brandedMessages';

interface CopyRoundReviewProps {
  originalPhrase: string;
  copyPhrase: string;
  playerUsername: string;
  copyNumber: 1 | 2;
  onSubmit: () => void;
  onBack: () => void;
}

export const CopyRoundReview: React.FC<CopyRoundReviewProps> = ({
  originalPhrase,
  copyPhrase,
  playerUsername,
  copyNumber,
  onSubmit,
  onBack,
}) => {
  const [isRevealed, setIsRevealed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const handleReveal = () => {
    setIsRevealed(true);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setShowSuccess(true);

    // Show success message before transitioning
    setTimeout(() => {
      setShowSuccess(false);
      setIsSubmitting(false);
      onSubmit();
    }, 1500);
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

        {/* Success Message */}
        {showSuccess && (
          <div className="mb-6 p-6 bg-quip-turquoise bg-opacity-20 border-2 border-quip-turquoise rounded-tile text-center success-message">
            <p className="text-2xl font-display font-bold text-quip-turquoise mb-2">
              {getRandomMessage('copySubmitted')}
            </p>
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
