import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CopyRoundReview } from '../components/PhrasesetReview/CopyRoundReview';
import { usePracticePhrasesetSession } from '../hooks/usePracticePhrasesetSession';

const PracticeCopy2: React.FC = () => {
  const navigate = useNavigate();
  const { phraseset, loading, error, clearSession } = usePracticePhrasesetSession();

  const handleContinue = () => {
    clearSession();
    navigate('/dashboard');
  };

  const handleBack = () => {
    clearSession();
    navigate('/dashboard');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-turquoise to-quip-teal flex items-center justify-center p-4">
        <div className="text-xl text-white">Loading practice round...</div>
      </div>
    );
  }

  if (error || !phraseset) {
    const isNoPhrasesets = error?.includes('No phrasesets available');
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-turquoise to-quip-teal flex items-center justify-center p-4">
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
            onClick={() => {
              clearSession();
              navigate('/dashboard');
            }}
            className="bg-quip-turquoise hover:bg-quip-teal text-white font-bold py-2 px-6 rounded-tile"
          >
            Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <CopyRoundReview
      originalPhrase={phraseset.original_phrase}
      copyPhrase={phraseset.copy2_phrase}
      playerUsername={phraseset.copy2_player}
      copyNumber={2}
      roundId={phraseset.phraseset_id}
      existingHints={phraseset.hints}
      onSubmit={handleContinue}
      onBack={handleBack}
      isPractice={true}
    />
  );
};

export default PracticeCopy2;
