import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PromptRoundReview } from '../components/PhrasesetReview/PromptRoundReview';
import { CopyRoundReview } from '../components/PhrasesetReview/CopyRoundReview';
import { VoteRoundReview } from '../components/PhrasesetReview/VoteRoundReview';
import type { PhrasesetDetails } from '../api/types';

const isCanceledRequest = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const maybeError = error as { name?: string; code?: string };
  return maybeError.name === 'CanceledError' || maybeError.code === 'ERR_CANCELED';
};

const getErrorDetail = (error: unknown): string | undefined => {
  if (!error || typeof error !== 'object') {
    return undefined;
  }

  const withDetail = error as { detail?: string; message?: string };
  return withDetail.detail ?? withDetail.message;
};

type ReviewStage = 'prompt' | 'copy1' | 'copy2' | 'vote';

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
        // Use public endpoint for completed phrasesets
        const data = await apiClient.getPublicPhrasesetDetails(phrasesetId, controller.signal);
        setPhrasesetData(data);
      } catch (err: unknown) {
        if (!isCanceledRequest(err)) {
          setError(getErrorDetail(err) || 'Failed to load phraseset details');
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
    setReviewStage('copy1');
  };

  const handleCopy1Submit = () => {
    setReviewStage('copy2');
  };

  const handleCopy2Submit = () => {
    setReviewStage('vote');
  };

  const handleBackToCompleted = () => {
    navigate('/completed');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading={true} message="Loading phraseset..." />
      </div>
    );
  }

  if (error || !phrasesetData) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center p-4">
        <div className="tile-card max-w-md w-full p-8 text-center">
          <div className="text-red-600 mb-4">
            <svg className="w-16 h-16 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-xl font-display font-bold text-ccl-navy mb-2">Error Loading Phraseset</h2>
            <p className="text-ccl-teal">{error || 'Failed to load phraseset details'}</p>
          </div>
          <button
            onClick={handleBackToCompleted}
            className="bg-ccl-navy hover:bg-ccl-teal text-white font-bold py-3 px-6 rounded-tile transition-all"
          >
            Completed Rounds
          </button>
        </div>
      </div>
    );
  }

  // Find the player who played the prompt round
  const promptContributor = phrasesetData.contributors.find(c => c.round_id === phrasesetData.prompt_round_id);

  // Find contributors for copy rounds using direct round IDs (now provided by backend)
  const copy1Contributor = phrasesetData.copy_round_1_id 
    ? phrasesetData.contributors.find(c => c.round_id === phrasesetData.copy_round_1_id)
    : null;
  
  const copy2Contributor = phrasesetData.copy_round_2_id
    ? phrasesetData.contributors.find(c => c.round_id === phrasesetData.copy_round_2_id)  
    : null;

  if (reviewStage === 'prompt') {
    return (
      <PromptRoundReview
        promptText={phrasesetData.prompt_text}
        originalPhrase={phrasesetData.original_phrase || ''}
        playerUsername={promptContributor?.username || 'Unknown'}
        isAiPlayer={promptContributor?.is_ai || false}
        onSubmit={handlePromptSubmit}
        onBack={handleBackToCompleted}
      />
    );
  }

  if (reviewStage === 'copy1') {
    return (
      <CopyRoundReview
        key="copy1"
        originalPhrase={phrasesetData.original_phrase || ''}
        copyPhrase={phrasesetData.copy_phrase_1 || ''}
        playerUsername={copy1Contributor?.username || 'Unknown'}
        isAiPlayer={copy1Contributor?.is_ai || false}
        copyNumber={1}
        roundId={copy1Contributor?.round_id}
        existingHints={null} // Hints not stored in phraseset data for reviews
        onSubmit={handleCopy1Submit}
        onBack={handleBackToCompleted}
      />
    );
  }

  if (reviewStage === 'copy2') {
    return (
      <CopyRoundReview
        key="copy2"
        originalPhrase={phrasesetData.original_phrase || ''}
        copyPhrase={phrasesetData.copy_phrase_2 || ''}
        playerUsername={copy2Contributor?.username || 'Unknown'}
        isAiPlayer={copy2Contributor?.is_ai || false}
        copyNumber={2}
        roundId={copy2Contributor?.round_id}
        existingHints={null} // Hints not stored in phraseset data for reviews
        onSubmit={handleCopy2Submit}
        onBack={handleBackToCompleted}
      />
    );
  }

  // Vote round stage
  return (
    <VoteRoundReview
      promptText={phrasesetData.prompt_text}
      originalPhrase={phrasesetData.original_phrase || ''}
      copyPhrase1={phrasesetData.copy_phrase_1 || ''}
      copyPhrase2={phrasesetData.copy_phrase_2 || ''}
      votes={phrasesetData.votes}
      onBack={handleBackToCompleted}
      promptPlayer={promptContributor?.username}
      copy1Player={copy1Contributor?.username}
      copy2Player={copy2Contributor?.username}
      promptPlayerIsAi={promptContributor?.is_ai || false}
      copy1PlayerIsAi={copy1Contributor?.is_ai || false}
      copy2PlayerIsAi={copy2Contributor?.is_ai || false}
    />
  );
};

export default PhrasesetReview;
