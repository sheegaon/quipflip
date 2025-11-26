import React, { useMemo, useState } from 'react';
import apiClient, { extractErrorMessage } from '../api/client';
import type {
  MemeCaptionOption,
  MemeCaptionSubmission,
  MemeVoteRound,
} from '../api/types';
import { CurrencyDisplay } from './CurrencyDisplay';

interface CaptionSubmissionModalProps {
  isOpen: boolean;
  onClose: () => void;
  round: MemeVoteRound;
  freeCaptionsRemaining?: number;
}

export const CaptionSubmissionModal: React.FC<CaptionSubmissionModalProps> = ({
  isOpen,
  onClose,
  round,
  freeCaptionsRemaining = 0,
}) => {
  const [captionText, setCaptionText] = useState('');
  const [captionType, setCaptionType] = useState<'original' | 'riff'>('original');
  const [parentCaptionId, setParentCaptionId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const freeCaptionAvailable = useMemo(() => {
    return freeCaptionsRemaining > 0;
  }, [freeCaptionsRemaining]);

  const captionCost = freeCaptionAvailable ? 0 : 10;

  const selectedParentCaption = useMemo(() => {
    if (captionType === 'riff' && parentCaptionId) {
      return round.captions.find((c: MemeCaptionOption) => c.caption_id === parentCaptionId);
    }
    return null;
  }, [captionType, parentCaptionId, round.captions]);

  const validationError = useMemo(() => {
    if (!captionText.trim()) {
      return null; // Don't show error for empty until they try to submit
    }
    if (captionText.length > 240) {
      return 'Caption must be 240 characters or less';
    }
    if (captionType === 'riff' && !parentCaptionId) {
      return 'Please select a caption to riff on';
    }
    return null;
  }, [captionText, captionType, parentCaptionId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!captionText.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const request: MemeCaptionSubmission = {
        round_id: round.round_id,
        text: captionText.trim(),
        kind: captionType,
        parent_caption_id: parentCaptionId || null,
      };

      await apiClient.submitMemeCaption(request);
      // Close modal and reset form
      setCaptionText('');
      setCaptionType('original');
      setParentCaptionId(null);
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
          <h2 className="text-2xl font-display font-bold text-quip-navy">Add your caption</h2>
          <button
            onClick={onClose}
            className="text-quip-teal hover:text-quip-turquoise text-2xl font-bold"
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
              className="w-full rounded-tile border-2 border-quip-navy max-h-64 object-contain"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded">{error}</div>
          )}

          {/* Caption Type Toggle */}
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="caption-type"
                checked={captionType === 'original'}
                onChange={() => {
                  setCaptionType('original');
                  setParentCaptionId(null);
                }}
                className="cursor-pointer"
              />
              <span className="font-semibold">Original</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="caption-type"
                checked={captionType === 'riff'}
                onChange={() => setCaptionType('riff')}
                className="cursor-pointer"
              />
              <span className="font-semibold">Riff on existing</span>
            </label>
          </div>

          {/* Parent Caption Selector for Riffs */}
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
                {round.captions.map((caption: MemeCaptionOption) => (
                  <option key={caption.caption_id} value={caption.caption_id}>
                    {caption.text}
                  </option>
                ))}
              </select>
              {selectedParentCaption && (
                <div className="mt-2 p-3 bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile">
                  <p className="text-xs text-quip-teal mb-1">Riffing on:</p>
                  <p className="text-sm text-quip-navy font-medium">{selectedParentCaption.text}</p>
                </div>
              )}
            </div>
          )}

          {/* Caption Input */}
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
              placeholder={
                captionType === 'riff'
                  ? 'Write your variation...'
                  : 'Share your original caption idea...'
              }
            />
            <div className="flex justify-between items-center mt-1">
              <span className="text-sm text-quip-teal">{captionText.length}/240</span>
              {validationError && (
                <span className="text-sm text-red-600">{validationError}</span>
              )}
            </div>
          </div>

          {/* Cost and Actions */}
          <div className="flex items-center justify-between pt-2">
            <div className="text-sm text-quip-teal flex items-center gap-2">
              <span>Cost:</span>
              <CurrencyDisplay amount={captionCost} />
              {freeCaptionAvailable && (
                <span className="text-quip-teal font-semibold">(Free caption available)</span>
              )}
            </div>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="border-2 border-quip-navy text-quip-navy font-semibold px-4 py-2 rounded-tile hover:bg-quip-navy hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={
                  isSubmitting ||
                  !captionText.trim() ||
                  (captionType === 'riff' && !parentCaptionId) ||
                  !!validationError
                }
                className="bg-quip-orange hover:bg-quip-orange-deep text-white font-semibold px-4 py-2 rounded-tile disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
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
