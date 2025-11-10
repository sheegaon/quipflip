import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CopyRoundReview } from '../components/PhrasesetReview/CopyRoundReview';
import apiClient from '../api/client';
import type { PracticePhraseset } from '../api/types';

const PracticeCopy: React.FC = () => {
  const navigate = useNavigate();
  const [phraseset, setPhraseset] = useState<PracticePhraseset | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPracticeData = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getRandomPracticePhraseset();
        setPhraseset(data);
      } catch (err) {
        console.error('Failed to fetch practice phraseset:', err);
        setError('Unable to load practice round. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchPracticeData();
  }, []);

  const handleContinue = () => {
    navigate('/dashboard');
  };

  const handleBack = () => {
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
      onSubmit={handleContinue}
      onBack={handleBack}
    />
  );
};

export default PracticeCopy;
