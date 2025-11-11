import React from 'react';
import { useNavigate } from 'react-router-dom';
import { PromptRoundReview } from '../components/PhrasesetReview/PromptRoundReview';
import { usePracticePhraseset } from '../hooks/usePracticePhraseset';

const PracticePrompt: React.FC = () => {
  const navigate = useNavigate();
  const { phraseset, loading, error } = usePracticePhraseset();

  const handleContinue = () => {
    navigate('/dashboard');
  };

  const handleBack = () => {
    navigate('/dashboard');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-navy to-quip-teal flex items-center justify-center p-4">
        <div className="text-xl text-white">Loading practice round...</div>
      </div>
    );
  }

  if (error || !phraseset) {
    const isNoPhrasesets = error?.includes('No phrasesets available');
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-navy to-quip-teal flex items-center justify-center p-4">
        <div className="tile-card p-8 text-center max-w-md">
          <h2 className="text-2xl font-bold text-quip-navy mb-4">
            {isNoPhrasesets ? 'No Practice Rounds Available' : 'Error'}
          </h2>
          <p className="text-quip-teal mb-6">
            {isNoPhrasesets
              ? 'There are no available practice rounds at the moment. Try playing some live rounds first, then come back to practice!'
              : error || 'Failed to load practice round'}
          </p>
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-quip-navy hover:bg-quip-teal text-white font-bold py-2 px-6 rounded-tile"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <PromptRoundReview
      promptText={phraseset.prompt_text}
      originalPhrase={phraseset.original_phrase}
      playerUsername={phraseset.prompt_player}
      onSubmit={handleContinue}
      onBack={handleBack}
      isPractice={true}
    />
  );
};

export default PracticePrompt;
