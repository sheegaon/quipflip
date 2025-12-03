import React, { useMemo, useState } from 'react';
import apiClient, { extractErrorMessage } from '@/api/client';
import type {
  MMMemeCaptionSubmission,
  MMMemeVoteRound,
} from '@crowdcraft/api/types.ts';
import { CurrencyDisplay } from './CurrencyDisplay';

interface CaptionSubmissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  round: MMMemeVoteRound;
  freeCaptionsRemaining?: number;
}

export const CaptionSubmissionModal: React.FC<CaptionSubmissionModalProps> = ({
  isOpen,
  onClose,
  round,
  freeCaptionsRemaining = 0,
}) => {
  const [captionText, setCaptionText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const freeCaptionAvailable = useMemo(() => {
    return freeCaptionsRemaining > 0;
  }, [freeCaptionsRemaining]);

  const captionCost = freeCaptionAvailable ? 0 : 10;

  const validationError = useMemo(() => {
    if (!captionText.trim()) {
      return null; // Don't show error for empty until they try to submit
    }
    if (captionText.length > 240) {
      return 'Caption must be 240 characters or less';
    }
    return null;
  }, [captionText]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!captionText.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const request: MMMemeCaptionSubmission = {
        round_id: round.round_id,
        text: captionText.trim(),
      };

      await apiClient.submitMemeCaption(request);
      // Close modal and reset form
      setCaptionText('');
      onClose();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to submit caption right now.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="tile-card w-full max-w-3xl p-6 md:p-8 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-display font-bold text-ccl-navy">Add your caption</h2>
          <button
            onClick={onClose}
            className="text-ccl-teal hover:text-ccl-turquoise text-2xl font-bold"
          >
            ×
          </button>
        </div>

        <div className="space-y-4">
          {/* Meme Preview */}
          <div>
            <img
              src={round.meme.image_url}
              alt={round.meme.alt_text || 'Meme image'}
              className="w-full rounded-tile border-2 border-ccl-navy max-h-64 object-contain"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded">{error}</div>
          )}

          {/* Info about algorithmic riff detection */}
          <div className="p-3 bg-ccl-turquoise bg-opacity-10 border-2 border-ccl-turquoise rounded-tile">
            <p className="text-sm text-ccl-navy">
              ✨ Our system will automatically detect if your caption is a riff or original based on similarity to the shown captions.
            </p>
          </div>

          {/* Caption Input */}
          <div>
            <label className="block text-sm text-ccl-teal mb-2" htmlFor="caption-input">
              Caption (240 characters max)
            </label>
            <textarea
              id="caption-input"
              maxLength={240}
              value={captionText}
              onChange={(e) => setCaptionText(e.target.value)}
              className="w-full border-2 border-ccl-navy rounded-tile p-3 focus:outline-none focus:ring-2 focus:ring-ccl-teal"
              rows={4}
              placeholder="Share your caption idea..."
            />
            <div className="flex justify-between items-center mt-1">
              <span className="text-sm text-ccl-teal">{captionText.length}/240</span>
              {validationError && (
                <span className="text-sm text-red-600">{validationError}</span>
              )}
            </div>
          </div>

          {/* Cost and Actions */}
          <div className="flex items-center justify-between pt-2">
            <div className="text-sm text-ccl-teal flex items-center gap-2">
              <span>Cost:</span>
              <CurrencyDisplay amount={captionCost} />
              {freeCaptionAvailable && (
                <span className="text-ccl-teal font-semibold">(Free caption available)</span>
              )}
            </div>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="border-2 border-ccl-navy text-ccl-navy font-semibold px-4 py-2 rounded-tile hover:bg-ccl-navy hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={
                  isSubmitting ||
                  !captionText.trim() ||
                  !!validationError
                }
                className="bg-ccl-orange hover:bg-ccl-orange-deep text-white font-semibold px-4 py-2 rounded-tile disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {isSubmitting ? 'Submitting...' : 'Submit Caption'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CaptionSubmissionModal;
