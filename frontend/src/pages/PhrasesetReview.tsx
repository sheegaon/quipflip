import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PromptRoundReview } from '../components/PhrasesetReview/PromptRoundReview';
import { CopyRoundReview } from '../components/PhrasesetReview/CopyRoundReview';
import type { PhrasesetDetails } from '../api/types';

type ReviewStage = 'prompt' | 'copy';

export const PhrasesetReview: React.FC = () => {
  const { phrasesetId } = useParams<{ phrasesetId: string }>();
  const navigate = useNavigate();
  const [phrasesetData, setPhrasesetData] = useState<PhrasesetDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewStage, setReviewStage] = useState<ReviewStage>('prompt');

  useEffect(() => {
    const controller = new AbortController();

    const fetchPhrasesetData = async () => {
      if (!phrasesetId) {
        setError('No phraseset ID provided');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getPhrasesetDetails(phrasesetId, controller.signal);
        setPhrasesetData(data);
      } catch (err: any) {
        if (err.name !== 'CanceledError' && err.code !== 'ERR_CANCELED') {
          setError(err.detail || err.message || 'Failed to load phraseset details');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchPhrasesetData();

    return () => {
      controller.abort();
    };
  }, [phrasesetId]);

  const handlePromptSubmit = () => {
    // Move to copy round review
    setReviewStage('copy');
  };

  const handleBackToCompleted = () => {
    navigate('/completed');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading={true} message="Loading phraseset..." />
      </div>
    );
  }

  if (error || !phrasesetData) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
        <div className="tile-card max-w-md w-full p-8 text-center">
          <div className="text-red-600 mb-4">
            <svg className="w-16 h-16 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-xl font-display font-bold text-quip-navy mb-2">Error Loading Phraseset</h2>
            <p className="text-quip-teal">{error || 'Failed to load phraseset details'}</p>
          </div>
          <button
            onClick={handleBackToCompleted}
            className="bg-quip-navy hover:bg-quip-teal text-white font-bold py-3 px-6 rounded-tile transition-all"
          >
            Back to Completed Rounds
          </button>
        </div>
      </div>
    );
  }

  // Find the player who played the prompt round
  const promptContributor = phrasesetData.contributors.find(c => c.round_id === phrasesetData.prompt_round_id);

  if (reviewStage === 'prompt') {
    return (
      <PromptRoundReview
        promptText={phrasesetData.prompt_text}
        originalPhrase={phrasesetData.original_phrase || ''}
        playerUsername={promptContributor?.username || 'Unknown'}
        onSubmit={handlePromptSubmit}
        onBack={handleBackToCompleted}
      />
    );
  }

  // Copy round stage
  return (
    <CopyRoundReview
      originalPhrase={phrasesetData.original_phrase || ''}
      onBack={handleBackToCompleted}
    />
  );
};

export default PhrasesetReview;
