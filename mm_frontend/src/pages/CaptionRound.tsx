import React, { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { extractErrorMessage } from '../api/client';
import type {
  VoteRoundState,
  VoteResult,
  Caption,
} from '../api/types';
import { CurrencyDisplay } from '../components/CurrencyDisplay';

interface CaptionLocationState {
  round?: VoteRoundState;
  voteResult?: VoteResult | null;
}

export const CaptionRound: React.FC = () => {
  const navigate = useNavigate();
  const locationState = (useLocation().state as CaptionLocationState) || {};
  const { actions, state } = useGame();
  
  // Get round from location state or from GameContext current vote round
  const round = locationState.round || state.currentVoteRound;

  const [captionText, setCaptionText] = useState('');
  const [captionType, setCaptionType] = useState<'original' | 'riff'>('original');
  const [parentCaptionId, setParentCaptionId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Get caption cost from round availability
  const freeCaptionAvailable = (state.roundAvailability?.free_captions_remaining ?? 0) > 0;
  const captionCost = freeCaptionAvailable ? 0 : (state.roundAvailability?.caption_submission_cost ?? 10);

  if (!round) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
        <div className="tile-card p-6 max-w-lg text-center">
          <p className="text-lg text-quip-navy font-display mb-4">No active caption round.</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-quip-orange hover:bg-quip-orange-deep text-white font-semibold px-4 py-2 rounded-tile"
          >
            Return to dashboard
          </button>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!captionText.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);
    
    try {
      const payload = {
        text: captionText.trim(),
        parent_caption_id: captionType === 'riff' ? parentCaptionId : undefined,
      };
      
      await actions.submitCaption(payload);
      setSuccessMessage('Caption submitted!');
      
      // Navigate to results or dashboard
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to submit caption right now.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
      <div className="max-w-5xl w-full tile-card p-6 md:p-10">
        <div className="flex flex-col md:flex-row gap-6 md:items-start">
          <img
            src={round.image_url}
            alt={round.attribution_text || 'Meme image'}
            className="w-full md:w-1/2 rounded-tile border-2 border-quip-navy max-h-96 object-contain bg-white"
          />
          <div className="flex-1 space-y-4">
            <div>
              <p className="text-sm text-quip-teal uppercase tracking-wide">Create a caption</p>
              <h1 className="text-3xl font-display font-bold text-quip-navy">Add your own spin</h1>
            </div>

            {error && (
              <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded">{error}</div>
            )}
            {successMessage && (
              <div className="p-3 bg-green-100 border border-green-400 text-green-800 rounded">{successMessage}</div>
            )}

            <div>
              <label className="block text-sm text-quip-teal mb-2" htmlFor="caption-input">
                Caption (240 characters max)
              </label>
              <textarea
                id="caption-input"
                maxLength={240}
                value={captionText}
                onChange={(e) => setCaptionText(e.target.value)}
                className="w-full border-2 border-quip-navy rounded-tile p-3 focus:outline-none focus:ring-2 focus:ring-quip-teal"
                rows={4}
                placeholder="Share your original idea or riff on an existing caption"
              />
              <div className="text-right text-sm text-quip-teal mt-1">{captionText.length}/240</div>
            </div>

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="caption-type"
                  checked={captionType === 'original'}
                  onChange={() => setCaptionType('original')}
                />
                <span>Original</span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="caption-type"
                  checked={captionType === 'riff'}
                  onChange={() => setCaptionType('riff')}
                />
                <span>Riff on existing</span>
              </label>
            </div>

            {captionType === 'riff' && (
              <div>
                <label className="block text-sm text-quip-teal mb-2" htmlFor="parent-select">
                  Choose a caption to riff on
                </label>
                <select
                  id="parent-select"
                  value={parentCaptionId ?? ''}
                  onChange={(e) => setParentCaptionId(e.target.value || null)}
                  className="w-full border-2 border-quip-navy rounded-tile p-3"
                >
                  <option value="">Select a caption</option>
                  {round.captions.map((caption: Caption) => (
                    <option key={caption.caption_id} value={caption.caption_id}>
                      {caption.text}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex items-center justify-between">
              <div className="text-sm text-quip-teal flex items-center gap-2">
                <span>Cost</span>
                <CurrencyDisplay amount={captionCost} />
                {freeCaptionAvailable && <span className="text-quip-teal font-semibold">Free caption available</span>}
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => navigate('/dashboard')}
                  className="border-2 border-quip-navy text-quip-navy font-semibold px-4 py-2 rounded-tile"
                >
                  Skip
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={isSubmitting || !captionText.trim() || (captionType === 'riff' && !parentCaptionId)}
                  className="bg-quip-orange hover:bg-quip-orange-deep text-white font-semibold px-4 py-2 rounded-tile disabled:opacity-60"
                >
                  {isSubmitting ? 'Submitting...' : 'Submit Caption'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CaptionRound;
