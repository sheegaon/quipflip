import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { extractErrorMessage } from '../api/client';
import type {
  VoteRoundState,
  VoteResult,
} from '../api/types';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { ShareIcon } from '../components/icons/EngagementIcons';

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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [isStartingRound, setIsStartingRound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [shareStatus, setShareStatus] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState(false);

  // Get caption cost from round availability
  const freeCaptionAvailable = (state.roundAvailability?.free_captions_remaining ?? 0) > 0;
  const captionCost = freeCaptionAvailable ? 0 : (state.roundAvailability?.caption_submission_cost ?? 10);
  const voteCost = state.roundAvailability?.round_entry_cost ?? 5;

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

  const handleSubmit = async () => {
    console.log('🔘 Submit button clicked', {
      captionText,
      isSubmitting,
      hasRound: !!round,
      currentVoteRound: state.currentVoteRound?.round_id
    });

    if (!captionText.trim() || isSubmitting) {
      console.log('⏭️ Submit blocked', { isEmpty: !captionText.trim(), isSubmitting });
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccessMessage(null);
    setShareStatus(null);

    try {
      const payload = {
        round_id: round.round_id,
        text: captionText.trim(),
      };

      console.log('📤 Submitting caption...', payload);
      const result = await actions.submitCaption(payload);
      console.log('✅ Caption submitted successfully', result);

      setSuccessMessage('Caption submitted!');
      setHasSubmitted(true);
    } catch (err) {
      console.error('❌ Caption submission failed:', err);
      setError(extractErrorMessage(err) || 'Unable to submit caption right now.');
    } finally {
      setIsSubmitting(false);
      console.log('🔓 isSubmitting set to false');
    }
  };

  const handleShare = async () => {
    if (!round || !captionText.trim()) {
      return;
    }

    setIsSharing(true);
    setShareStatus(null);

    try {
      const caption = captionText.trim();
      const homeUrl = `${window.location.origin}/`;

      const response = await fetch(round.image_url);
      if (!response.ok) {
        throw new Error('Unable to retrieve image for sharing');
      }
      const blob = await response.blob();
      const mimeType = blob.type || 'image/jpeg';
      const extension = mimeType.split('/')[1] || 'jpeg';
      const file = new File([blob], `mememint-caption.${extension}`, { type: mimeType });

      const shareText = [
        caption,
        '',
        round.attribution_text ? `Image: ${round.attribution_text}` : null,
        `Image link: ${round.image_url}`,
        `Play MemeMint: ${homeUrl}`,
      ]
        .filter(Boolean)
        .join('\n');

      const clipboardText = [
        caption,
        '',
        round.attribution_text ? `Image: ${round.attribution_text}` : null,
        `Image link: ${round.image_url}`,
        `Play MemeMint: ${homeUrl}`,
      ]
        .filter(Boolean)
        .join('\n');

      const shareData: ShareData = {
        title: 'My MemeMint caption',
        text: shareText,
        url: homeUrl,
      };

      const canShareFile = navigator.canShare?.({ files: [file] }) ?? false;
      if (canShareFile) {
        shareData.files = [file];
      }

      if (navigator.share) {
        await navigator.share(shareData);
        setShareStatus('Opened your sharing options.');
      } else if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(clipboardText);
        setShareStatus('Copied caption and image link for sharing.');
      } else {
        setShareStatus('Sharing not supported in this browser.');
      }
    } catch (err) {
      // Avoid showing an error when the user intentionally cancels the native share dialog
      if (err instanceof DOMException && err.name === 'AbortError') {
        console.info('Share cancelled by user');
        setShareStatus(null);
        return;
      }

      console.error('Failed to share caption', err);
      setShareStatus('Unable to share right now. Try again in a moment.');
    } finally {
      setIsSharing(false);
    }
  };

  const handlePlayAgain = async () => {
    console.log('🔄 Play again clicked');
    setError(null);
    setIsStartingRound(true);

    try {
      const newRound = await actions.startVoteRound();
      navigate('/game/vote', { state: { round: newRound } });
    } catch (err) {
      console.error('❌ Failed to start new round from caption page:', err);
      setError(extractErrorMessage(err) || 'Unable to start a new round. Please try again.');
    } finally {
      setIsStartingRound(false);
    }
  };

  const handleAbandonRound = async () => {
    if (round) {
      try {
        await actions.abandonRound(round.round_id);
      } catch (err) {
        console.warn('Failed to abandon caption round', err);
      }
    }

    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
      <div className="max-w-5xl w-full tile-card p-6 md:p-10 relative">
        <button
          type="button"
          onClick={handleAbandonRound}
          className="absolute top-4 right-4 text-quip-navy hover:opacity-80 transition transform hover:scale-105"
          aria-label="Return to dashboard"
        >
          <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.08" />
            <path d="M8 8L16 16M16 8L8 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
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
                disabled={hasSubmitted || isSubmitting}
                className="tutorial-prompt-input tutorial-copy-input w-full border-2 border-quip-navy rounded-tile p-3 focus:outline-none focus:ring-2 focus:ring-quip-teal"
                rows={4}
                placeholder="Write your caption for this image"
              />
              <div className="text-right text-sm text-quip-teal mt-1">{captionText.length}/240</div>
            </div>

            <div className="flex items-center justify-between">
              <div className="text-sm text-quip-teal flex items-center gap-2">
                {freeCaptionAvailable && <span className="text-quip-teal font-semibold">Free caption available</span>}
              </div>
              <div className="flex gap-3">
                {hasSubmitted ? (
                  <>
                    <button
                      type="button"
                      onClick={handleShare}
                      disabled={isSharing}
                      className="h-12 w-12 inline-flex items-center justify-center rounded-full bg-quip-orange text-white shadow-tile-sm transition hover:bg-quip-orange-deep focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-orange disabled:opacity-60 disabled:cursor-not-allowed"
                      aria-label="Share caption"
                    >
                      <ShareIcon className="h-6 w-6" />
                    </button>
                    <button
                      onClick={handlePlayAgain}
                      disabled={isStartingRound}
                      className="border-2 border-quip-navy text-quip-navy font-semibold px-4 py-2 rounded-tile hover:bg-quip-navy hover:text-white transition-colors flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      <span>Play again</span>
                      <CurrencyDisplay amount={voteCost} iconClassName="w-4 h-4" textClassName="font-semibold" />
                    </button>
                  </>
                ) : (
                  <button
                    onClick={handleSubmit}
                    disabled={isSubmitting || !captionText.trim()}
                    className="bg-quip-orange hover:bg-quip-orange-deep text-white font-semibold px-4 py-2 rounded-tile disabled:opacity-60 flex items-center gap-2"
                  >
                    <span>{isSubmitting ? 'Submitting...' : 'Submit Caption'}</span>
                    <CurrencyDisplay amount={captionCost} iconClassName="w-4 h-4" textClassName="font-semibold" />
                  </button>
                )}
              </div>
            </div>

            {shareStatus && (
              <div className="text-sm text-quip-teal" role="status">
                {shareStatus}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CaptionRound;
