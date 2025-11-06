import React from 'react';
import type { PhrasesetContributor } from '../api/types';

interface PhraseRecapCardProps {
  phrase: string;
  isOriginal: boolean;
  isYourChoice: boolean;
  isCorrectChoice: boolean;
  contributor?: PhrasesetContributor;
}

/**
 * Displays a single phrase card in the vote round recap screen.
 * Shows the phrase text, author attribution, and relevant badges
 * (Original and/or Your Choice).
 *
 * @param phrase - The phrase text to display
 * @param isOriginal - Whether this phrase is the original
 * @param isYourChoice - Whether the player chose this phrase
 * @param isCorrectChoice - Whether the player's choice was correct (affects badge color)
 * @param contributor - The contributor information (username and whether it's the player)
 */
export const PhraseRecapCard: React.FC<PhraseRecapCardProps> = ({
  phrase,
  isOriginal,
  isYourChoice,
  isCorrectChoice,
  contributor,
}) => {
  // Determine styling based on whether it's original
  const borderColor = isOriginal ? 'border-quip-turquoise' : 'border-quip-teal';
  const bgColor = isOriginal ? 'bg-quip-turquoise bg-opacity-5' : 'bg-white';

  return (
    <div
      className={`relative ${bgColor} border-2 ${borderColor} rounded-tile p-4 transition-all`}
    >
      {/* Phrase text */}
      <p className="text-lg font-semibold text-quip-navy mb-2">
        "{phrase}"
      </p>

      {/* Author and badges */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm text-quip-teal">
            Written by:
          </span>
          <span className={`text-sm font-semibold ${contributor?.is_you ? 'text-quip-orange' : 'text-quip-navy'}`}>
            {contributor?.username || 'Unknown'}
            {contributor?.is_you && ' (you)'}
          </span>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2">
          {isOriginal && (
            <span className="inline-flex items-center gap-1 px-3 py-1 bg-quip-turquoise text-white text-sm font-bold rounded-tile">
              ⭐ Original
            </span>
          )}
          {isYourChoice && (
            <span className={`inline-flex items-center gap-1 px-3 py-1 ${isCorrectChoice ? 'bg-quip-turquoise' : 'bg-quip-orange'} text-white text-sm font-bold rounded-tile`}>
              {isCorrectChoice ? '✓' : '✗'} Your Choice
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default PhraseRecapCard;
