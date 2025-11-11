import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CopyRoundReview } from '../components/PhrasesetReview/CopyRoundReview';
import { usePracticePhrasesetSession } from '../hooks/usePracticePhrasesetSession';

const PracticeCopy: React.FC = () => {
  const navigate = useNavigate();
  const { phraseset, loading, error, clearSession } = usePracticePhrasesetSession();

  const handleContinue = () => {
    // Don't clear session - continue to copy2 with same phraseset
    navigate('/practice/copy2');
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
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-turquoise to-quip-teal flex items-center justify-center p-4">
        <div className="tile-card p-8 text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-quip-navy mb-6">{error || 'Failed to load practice round'}</p>
          <button
            onClick={() => navigate('/dashboard')}
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
      copyPhrase={phraseset.copy1_phrase}
      playerUsername={phraseset.copy1_player}
      copyNumber={1}
      roundId={phraseset.phraseset_id}
      existingHints={phraseset.hints}
      onSubmit={handleContinue}
      onBack={handleBack}
      isPractice={true}
    />
  );
};

export default PracticeCopy;
