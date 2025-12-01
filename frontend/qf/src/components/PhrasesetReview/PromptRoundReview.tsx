import React, { useState } from 'react';
import { FrozenTimer } from './FrozenTimer';
import { ThumbFeedbackButton } from '../ThumbFeedbackButton';
import { ReviewBackButton } from './ReviewBackButton';
import { BotIcon } from '../icons/EngagementIcons';
import { TrackingIcon } from '../icons/NavigationIcons';

interface PromptRoundReviewProps {
  promptText: string;
  originalPhrase: string;
  playerUsername: string;
  isAiPlayer?: boolean;
  onSubmit: () => void;
  onBack: () => void;
  isPractice?: boolean;
}

export const PromptRoundReview: React.FC<PromptRoundReviewProps> = ({
  promptText,
  originalPhrase,
  playerUsername,
  isAiPlayer = false,
  onSubmit,
  onBack,
  isPractice = false,
}) => {
  const [isRevealed, setIsRevealed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleReveal = () => {
    setIsRevealed(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!isRevealed) return;

    setIsSubmitting(true);
    onSubmit();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-ccl-navy to-ccl-teal flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <TrackingIcon className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-ccl-navy">Prompt Round</h1>
          </div>
          <p className="text-ccl-teal">Write a quip for the prompt</p>
        </div>

        {/* Timer - frozen */}
        <div className="flex justify-center mb-6">
          <FrozenTimer displayTime="3:00" />
        </div>

        {/* Instructions */}
        <div className="bg-ccl-orange bg-opacity-10 border-2 border-ccl-orange rounded-tile p-4 mb-6">
          <p className="text-sm text-ccl-navy">
            <strong>💡 Tip:</strong> Type a short phrase that completes the sentence.
          </p>
        </div>

        {/* Prompt */}
        <div className="bg-ccl-navy bg-opacity-5 border-2 border-ccl-navy rounded-tile p-6 py-8 mb-6 relative min-h-[120px] flex items-center">
          <p className="text-xl md:text-2xl text-center font-display font-semibold text-ccl-navy flex-1 pr-12">
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
              className={`relative w-full px-4 py-3 text-lg border-2 border-ccl-teal rounded-tile ${
                !isRevealed
                  ? 'cursor-pointer hover:border-ccl-turquoise hover:bg-ccl-turquoise hover:bg-opacity-5 transition-all'
                  : ''
              }`}
              title={!isRevealed ? 'Click to reveal the submitted phrase' : undefined}
            >
              {!isRevealed ? (
                <div className="flex items-center justify-center py-1">
                  <span className="text-ccl-teal font-semibold">Click to reveal phrase</span>
                </div>
              ) : (
                <span className="text-ccl-navy">{originalPhrase}</span>
              )}
              {!isRevealed && (
                <div className="absolute inset-0 bg-ccl-navy bg-opacity-5 rounded-tile pointer-events-none backdrop-blur-[2px]" />
              )}
            </div>
            <p className="text-sm text-ccl-teal mt-1">
              2-5 words (4-100 characters), A-Z and spaces only, must not repeat prompt, no proper nouns
            </p>
          </div>

          <button
            type="submit"
            disabled={!isRevealed || isSubmitting}
            className="w-full bg-ccl-navy hover:bg-ccl-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
          >
            {isSubmitting ? 'Submitting...' : isPractice ? 'Submit' : 'Continue to Copy Round'}
          </button>
        </form>

        {/* Back Button with Eye Icon */}
        <ReviewBackButton onClick={onBack} disabled={isSubmitting} />

        {/* Player Info */}
        <div className="mt-6 p-4 bg-ccl-navy bg-opacity-5 rounded-tile">
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
