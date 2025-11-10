import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { VoteRoundReview } from '../components/PhrasesetReview/VoteRoundReview';
import apiClient from '../api/client';
import type { PracticePhraseset } from '../api/types';

const PracticeVote: React.FC = () => {
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

  const handleBack = () => {
    navigate('/dashboard');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-orange-deep flex items-center justify-center p-4">
        <div className="text-xl text-white">Loading practice round...</div>
      </div>
    );
  }

  if (error || !phraseset) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-orange-deep flex items-center justify-center p-4">
        <div className="tile-card p-8 text-center">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-quip-navy mb-6">{error || 'Failed to load practice round'}</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-2 px-6 rounded-tile"
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
      copyPhrase1={phraseset.copy1_phrase}
      copyPhrase2={phraseset.copy2_phrase}
      votes={[]} // Practice mode doesn't show votes
      onBack={handleBack}
    />
  );
};

export default PracticeVote;
