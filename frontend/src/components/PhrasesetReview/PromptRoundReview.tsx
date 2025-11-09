import React, { useState } from 'react';
import { FrozenTimer } from './FrozenTimer';
import { ThumbFeedbackButton } from '../ThumbFeedbackButton';
import { ReviewBackButton } from './ReviewBackButton';
import { getRandomMessage } from '../../utils/brandedMessages';

interface PromptRoundReviewProps {
  promptText: string;
  originalPhrase: string;
  playerUsername: string;
  onSubmit: () => void;
  onBack: () => void;
}

export const PromptRoundReview: React.FC<PromptRoundReviewProps> = ({
  promptText,
  originalPhrase,
  playerUsername,
  onSubmit,
  onBack,
}) => {
  const [isRevealed, setIsRevealed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const handleReveal = () => {
    setIsRevealed(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!isRevealed) return;

    setIsSubmitting(true);
    setShowSuccess(true);

    // Show success message briefly, then move to next stage
    setTimeout(() => {
      onSubmit();
    }, 1500);
  };

  // Show success state
  if (showSuccess) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
        <div className="tile-card max-w-md w-full p-8 text-center flip-enter">
          <div className="flex justify-center mb-4">
            <img src="/icon_prompt.svg" alt="Prompt round icon" className="w-24 h-24" />
          </div>
          <h2 className="text-2xl font-display font-bold text-quip-turquoise mb-2 success-message">
            {getRandomMessage('promptSubmitted')}
          </h2>
          <p className="text-quip-teal">Moving to copy round...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-navy to-quip-teal flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <img src="/icon_prompt.svg" alt="Prompt round icon" className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Prompt Round</h1>
          </div>
          <p className="text-quip-teal">Submit a phrase for the prompt</p>
        </div>

        {/* Timer - frozen */}
        <div className="flex justify-center mb-6">
          <FrozenTimer displayTime="3:00" />
        </div>

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4 mb-6">
          <p className="text-sm text-quip-navy">
            <strong>💡 Tip:</strong> Type a short phrase that completes the sentence.
          </p>
        </div>

        {/* Prompt */}
        <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-6 py-8 mb-6 relative min-h-[120px] flex items-center">
          <p className="text-xl md:text-2xl text-center font-display font-semibold text-quip-navy flex-1 pr-12">
            {promptText}
          </p>

          {/* Disabled Feedback Icons */}
          <div className="absolute top-1 md:top-2 right-1 md:right-3 flex gap-1 md:gap-1.5">
            <ThumbFeedbackButton
              type="like"
              isActive={false}
              onClick={() => {}}
              disabled={true}
            />
            <ThumbFeedbackButton
              type="dislike"
              isActive={false}
              onClick={() => {}}
              disabled={true}
            />
          </div>
        </div>

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <div
              onClick={!isRevealed ? handleReveal : undefined}
              className={`relative w-full px-4 py-3 text-lg border-2 border-quip-teal rounded-tile ${
                !isRevealed
                  ? 'cursor-pointer hover:border-quip-turquoise hover:bg-quip-turquoise hover:bg-opacity-5 transition-all'
                  : ''
              }`}
              title={!isRevealed ? 'Click to reveal the submitted phrase' : undefined}
            >
              {!isRevealed ? (
                <div className="flex items-center justify-center py-1">
                  <span className="text-quip-teal font-semibold">Click to reveal phrase</span>
                </div>
              ) : (
                <span className="text-quip-navy">{originalPhrase}</span>
              )}
              {!isRevealed && (
                <div className="absolute inset-0 bg-quip-navy bg-opacity-5 rounded-tile pointer-events-none backdrop-blur-[2px]" />
              )}
            </div>
            <p className="text-sm text-quip-teal mt-1">
              2-5 words (4-100 characters), A-Z and spaces only
            </p>
          </div>

          <button
            type="submit"
            disabled={!isRevealed || isSubmitting}
            className="w-full bg-quip-navy hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
          >
            {isSubmitting ? 'Continuing...' : 'Submit Phrase'}
          </button>
        </form>

        {/* Back Button with Eye Icon */}
        <ReviewBackButton onClick={onBack} disabled={isSubmitting} />

        {/* Player Info */}
        <div className="mt-6 p-4 bg-quip-navy bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal">
            <strong className="text-quip-navy">Round played by:</strong> {playerUsername}
          </p>
        </div>
      </div>
    </div>
  );
};
