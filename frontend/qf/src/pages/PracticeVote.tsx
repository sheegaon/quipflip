import React from 'react';
import { useNavigate } from 'react-router-dom';
import { VoteRoundReview } from '../components/PhrasesetReview/VoteRoundReview';
import { usePracticePhraseset } from '@crowdcraft/hooks/usePracticePhraseset.ts';

const PracticeVote: React.FC = () => {
  const navigate = useNavigate();
  const { phraseset, loading, error } = usePracticePhraseset();

  const handleBack = () => {
    navigate('/dashboard');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-ccl-orange to-ccl-orange-deep flex items-center justify-center p-4">
        <div className="text-xl text-white">Loading practice round...</div>
      </div>
    );
  }

  if (error || !phraseset) {
    const isNoPhrasesets = error?.includes('No phrasesets available');
    return (
      <div className="min-h-screen bg-gradient-to-br from-ccl-orange to-ccl-orange-deep flex items-center justify-center p-4">
        <div className="tile-card p-8 text-center max-w-md">
          <h2 className="text-2xl font-bold text-ccl-navy mb-4">
            {isNoPhrasesets ? 'No Practice Rounds Available' : 'Error'}
          </h2>
          <p className="text-ccl-teal mb-6">
            {isNoPhrasesets
              ? 'There are no available practice rounds at the moment. Try playing some live rounds first, then come back to practice!'
              : error || 'Failed to load practice round'}
          </p>
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-ccl-orange hover:bg-ccl-orange-deep text-white font-bold py-2 px-6 rounded-tile"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <VoteRoundReview
      promptText={phraseset.prompt_text}
      originalPhrase={phraseset.original_phrase}
      copyPhrase1={phraseset.copy_phrase_1}
      copyPhrase2={phraseset.copy_phrase_2}
      votes={phraseset.votes || []}
      onBack={handleBack}
      promptPlayer={phraseset.prompt_player}
      copy1Player={phraseset.copy1_player}
      copy2Player={phraseset.copy2_player}
      promptPlayerIsAi={phraseset.prompt_player_is_ai}
      copy1PlayerIsAi={phraseset.copy1_player_is_ai}
      copy2PlayerIsAi={phraseset.copy2_player_is_ai}
      isPractice={true}
    />
  );
};

export default PracticeVote;
