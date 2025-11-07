import React from 'react';
import { EyeIcon } from '../icons/EyeIcon';

interface CopyRoundReviewProps {
  originalPhrase: string;
  copyPhrase1: string;
  copyPhrase2: string;
  onBack: () => void;
}

export const CopyRoundReview: React.FC<CopyRoundReviewProps> = ({
  originalPhrase,
  copyPhrase1,
  copyPhrase2,
  onBack,
}) => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-turquoise to-quip-teal flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <img src="/icon_copy.svg" alt="Copy round icon" className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Copy Round Review</h1>
          </div>
          <p className="text-quip-teal">Review the original phrase from the phraseset</p>
        </div>

        {/* Timer - frozen */}
        <div className="flex justify-center mb-6">
          <div className="bg-quip-cream rounded-tile px-6 py-3 shadow-tile-sm">
            <div className="text-center">
              <span className="text-3xl font-display font-bold text-quip-navy">3:00</span>
            </div>
          </div>
        </div>

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4 mb-6">
          <p className="text-sm text-quip-navy">
            <strong>👁 Review Mode:</strong> This shows the original phrase that was submitted in the prompt round, which players tried to copy.
          </p>
        </div>

        {/* Original Phrase Display */}
        <div className="bg-quip-turquoise bg-opacity-5 border-2 border-quip-turquoise rounded-tile p-6 mb-6">
          <p className="text-sm text-quip-teal mb-2 text-center font-medium">Original Phrase:</p>
          <p className="text-3xl text-center font-display font-bold text-quip-turquoise">
            {originalPhrase}
          </p>
        </div>

        {/* Copy Phrases Display */}
        {(copyPhrase1 || copyPhrase2) && (
          <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-6 mb-6">
            <p className="text-sm text-quip-teal mb-3 text-center font-medium">Copy Phrases Submitted:</p>
            <div className="space-y-3">
              {copyPhrase1 && (
                <div className="bg-white rounded-tile p-3 border border-quip-teal">
                  <p className="text-xs text-quip-teal mb-1">Copy 1:</p>
                  <p className="text-lg font-semibold text-quip-navy">{copyPhrase1}</p>
                </div>
              )}
              {copyPhrase2 && (
                <div className="bg-white rounded-tile p-3 border border-quip-teal">
                  <p className="text-xs text-quip-teal mb-1">Copy 2:</p>
                  <p className="text-lg font-semibold text-quip-navy">{copyPhrase2}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Back Button with Eye Icon */}
        <button
          onClick={onBack}
          className="w-full flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise py-3 font-medium transition-colors bg-white rounded-tile border-2 border-quip-teal hover:border-quip-turquoise"
        >
          <EyeIcon />
          <span>Back to Completed Rounds</span>
        </button>

        {/* Info */}
        <div className="mt-6 p-4 bg-quip-turquoise bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal text-center">
            <strong className="text-quip-navy">Review complete!</strong> You've seen how this phraseset was created.
          </p>
        </div>
      </div>
    </div>
  );
};
