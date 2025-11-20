import React, { useState } from 'react';
import { FrozenTimer } from './FrozenTimer';
import { ReviewBackButton } from './ReviewBackButton';
import { BotIcon } from '../icons/EngagementIcons';
import { isAiPlayer } from '../../utils/ai';
import { VoteRoundIcon } from '../icons/RoundIcons';
import type { PhrasesetVoteDetail } from '../../api/types';

interface VoteRoundReviewProps {
  promptText: string;
  originalPhrase: string;
  copyPhrase1: string;
  copyPhrase2: string;
  votes: PhrasesetVoteDetail[];
  onBack: () => void;
  promptPlayer?: string;
  copy1Player?: string;
  copy2Player?: string;
  promptPlayerIsAi?: boolean;
  copy1PlayerIsAi?: boolean;
  copy2PlayerIsAi?: boolean;
  isPractice?: boolean;
}

export const VoteRoundReview: React.FC<VoteRoundReviewProps> = ({
  promptText,
  originalPhrase,
  copyPhrase1,
  copyPhrase2,
  votes,
  onBack,
  promptPlayer,
  copy1Player,
  copy2Player,
  promptPlayerIsAi = false,
  copy1PlayerIsAi = false,
  copy2PlayerIsAi = false,
  isPractice = false,
}) => {
  const [isRevealed, setIsRevealed] = useState(false);

  const phrases = [originalPhrase, copyPhrase1, copyPhrase2];
  const phraseAuthors = [promptPlayer, copy1Player, copy2Player];
  const phraseAuthorsIsAi = [promptPlayerIsAi, copy1PlayerIsAi, copy2PlayerIsAi];

  const handleReveal = () => {
    setIsRevealed(true);
  };

  // Get votes for a specific phrase
  const getVotesForPhrase = (phrase: string) => {
    return votes.filter(v => v.voted_phrase === phrase);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-orange-deep flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <VoteRoundIcon className="w-8 h-8" aria-hidden="true" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Vote Round</h1>
          </div>
          <p className="text-quip-teal">Identify the original phrase</p>
        </div>

        {/* Timer - frozen */}
        <div className="flex justify-center mb-6">
          <FrozenTimer displayTime="3:00" />
        </div>

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4 mb-6">
          <p className="text-sm text-quip-navy">
            <strong>❓ Question:</strong> Which phrase is the original? Click any phrase to reveal how players voted once you're
            done reviewing.
          </p>
        </div>

        {/* Prompt */}
        <div className="bg-quip-orange bg-opacity-5 border-2 border-quip-orange rounded-tile p-6 mb-6">
          <p className="text-sm text-quip-teal mb-2 text-center font-medium">Prompt:</p>
          <p className="text-2xl text-center font-display font-semibold text-quip-orange-deep">
            {promptText}
          </p>
        </div>

        {/* Phrase Choices with Vote Information */}
        <div className="space-y-4 mb-6">
          <p className="text-center text-quip-navy font-display font-semibold mb-1 text-lg">
            Which phrase is the original?
          </p>
          <p className="text-center text-quip-teal mb-4 text-sm">
            {!isRevealed
              ? isPractice
                ? 'Click any phrase to reveal how players voted after you decide.'
                : 'Click any phrase to reveal how players voted.'
              : 'Voting Results'}
          </p>
          {phrases.map((phrase, idx) => {
            const phraseVotes = getVotesForPhrase(phrase);
            const isOriginal = phrase === originalPhrase;
            const author = phraseAuthors[idx];
            const authorIsAi = phraseAuthorsIsAi[idx];

            return (
              <div
                key={phrase}
                onClick={!isRevealed ? handleReveal : undefined}
                className={`w-full p-4 rounded-tile transition-all shuffle-enter ${
                  !isRevealed
                    ? 'bg-quip-orange cursor-pointer hover:bg-quip-orange-deep text-white'
                    : isOriginal
                    ? 'bg-quip-turquoise bg-opacity-20 border-2 border-quip-turquoise'
                    : 'bg-gray-100 border-2 border-gray-300'
                }`}
                style={{ animationDelay: `${idx * 0.1}s` }}
              >
                <div className="text-center mb-2">
                  <p className={`font-bold text-xl ${!isRevealed ? 'text-white' : 'text-quip-navy'}`}>
                    {phrase}
                  </p>
                  {isRevealed && author && (
                    <p className="text-sm text-quip-teal mt-1 flex items-center justify-center gap-1">
                      <span>by {author}</span>
                      {authorIsAi && <BotIcon className="h-3.5 w-3.5" />}
                    </p>
                  )}
                </div>

                {/* Show vote details when revealed */}
                {isRevealed && (
                  <div className="mt-3 pt-3 border-t-2 border-quip-navy border-opacity-10">
                    {isOriginal && (
                      <div className="text-center mb-2">
                        <span className="inline-block bg-quip-turquoise text-white px-3 py-1 rounded-tile text-sm font-semibold">
                          ✓ Original Phrase
                        </span>
                      </div>
                    )}

                    {phraseVotes.length > 0 ? (
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-quip-navy mb-2">
                          Voted for by:
                        </p>
                        {phraseVotes.map((vote) => (
                          <div
                            key={vote.vote_id}
                            className={`flex items-center justify-between p-2 rounded text-sm ${
                              vote.correct ? 'bg-quip-turquoise bg-opacity-10' : 'bg-quip-orange bg-opacity-10'
                            }`}
                          >
                            <span className="font-semibold text-quip-navy flex items-center gap-1">
                              {vote.voter_username}
                              {isAiPlayer(vote) && <BotIcon className="h-3.5 w-3.5" />}
                            </span>
                            <span className={`text-xs font-semibold ${vote.correct ? 'text-quip-turquoise' : 'text-quip-orange'}`}>
                              {vote.correct ? '✓ Correct' : '✗ Incorrect'}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-quip-teal text-center italic">
                        No votes for this phrase
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Back Button with Eye Icon */}
        <ReviewBackButton onClick={onBack} />

        {/* Info */}
        <div className="mt-6 p-4 bg-quip-orange bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal text-center">
            <strong className="text-quip-navy">Review Mode:</strong> Click on the phrases above to see who voted for each one.
          </p>
        </div>
      </div>
    </div>
  );
};
