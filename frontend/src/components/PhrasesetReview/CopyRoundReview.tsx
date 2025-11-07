import React from 'react';
import { Timer } from '../Timer';
import { ReviewBackButton } from './ReviewBackButton';
import { createFrozenTimerDate } from '../../utils/reviewHelpers';

interface CopyRoundReviewProps {
  originalPhrase: string;
  onBack: () => void;
}

export const CopyRoundReview: React.FC<CopyRoundReviewProps> = ({
  originalPhrase,
  onBack,
}) => {
  const frozenTimerDate = createFrozenTimerDate();

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
          <Timer expiresAt={frozenTimerDate} />
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

        {/* Input placeholder (disabled in review mode) */}
        <div className="space-y-4 mb-4">
          <div>
            <div className="w-full px-4 py-3 text-lg border-2 border-gray-300 rounded-tile bg-gray-50 text-gray-400 flex items-center justify-center">
              <span>Review mode - input disabled</span>
            </div>
            <p className="text-sm text-quip-teal mt-1">
              2-5 words (4-100 characters), A-Z and spaces only, must be different from the original
            </p>
          </div>

          <button
            disabled
            className="w-full bg-gray-400 text-white font-bold py-3 px-4 rounded-tile text-lg cursor-not-allowed"
          >
            Submit Phrase
          </button>
        </div>

        {/* Back Button with Eye Icon */}
        <ReviewBackButton onClick={onBack} />

        {/* Info */}
        <div className="mt-6 p-4 bg-quip-turquoise bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal">
            <strong className="text-quip-navy">Review Mode:</strong> This is a completed round. The original phrase is shown above.
          </p>
        </div>
      </div>
    </div>
  );
};
