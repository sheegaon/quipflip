import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient from '@crowdcraft/api/client.ts';
import type { QFBetaSurveyStatusResponse } from '@crowdcraft/api/types.ts';
import { hasDismissedSurvey, markSurveyDismissed, hasCompletedSurvey } from '@crowdcraft/utils/betaSurvey.ts';
import { getErrorMessage } from '@crowdcraft/types/errors.ts';
import { dashboardLogger } from '@crowdcraft/utils/logger.ts';

interface BetaSurveyModalProps {
  isVisible: boolean;
  onDismiss: () => void;
}

export const BetaSurveyModal: React.FC<BetaSurveyModalProps> = ({ isVisible, onDismiss }) => {
  const { state } = useGame();
  const { player, isAuthenticated } = state;
  const navigate = useNavigate();
  const [surveyStatus, setSurveyStatus] = useState<QFBetaSurveyStatusResponse | null>(null);

  // Beta survey status with proper cleanup
  // NOTE: In development, React StrictMode will cause this effect to run twice,
  // leading to duplicate API calls. This is intentional React behavior to help catch bugs.
  // In production, this won't happen. We use AbortController to cancel pending requests
  // when the component unmounts/remounts.
  useEffect(() => {
    const playerId = player?.player_id;

    if (!playerId || !isAuthenticated) {
      setSurveyStatus(null);
      return;
    }

    const controller = new AbortController();

    const fetchStatus = async () => {
      try {
        // Cache key for this player's survey status
        const cacheKey = `beta_survey_status_${playerId}`;
        const now = Date.now();
        
        // Check if we have cached data less than 5 minutes old
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          try {
            const { data, timestamp } = JSON.parse(cached);
            if (now - timestamp < 300000) { // 5 minutes = 300000ms
              const dismissed = hasDismissedSurvey(playerId);
              const completedLocal = hasCompletedSurvey(playerId);
              const shouldShow = data.eligible && !data.has_submitted && !dismissed && !completedLocal;

              setSurveyStatus(data);

              if (shouldShow) {
                dashboardLogger.info('[Beta Survey] ✨ SHOWING SURVEY PROMPT ✨ (from cache)');
              }
              return; // Use cached data
            }
          } catch {
            // Invalid cache, continue to fetch
          }
        }

        const status = await apiClient.getBetaSurveyStatus(controller.signal);
        
        // Cache the result for 5 minutes
        localStorage.setItem(cacheKey, JSON.stringify({
          data: status,
          timestamp: now
        }));

        const dismissed = hasDismissedSurvey(playerId);
        const completedLocal = hasCompletedSurvey(playerId);
        const shouldShow = status.eligible && !status.has_submitted && !dismissed && !completedLocal;

        setSurveyStatus(status);

        if (shouldShow) {
          dashboardLogger.info('[Beta Survey] ✨ SHOWING SURVEY PROMPT ✨');
        }
      } catch (error: unknown) {
        if (controller.signal.aborted) {
          return;
        }
        // Only log non-auth errors - 401 is expected when not authenticated
        // Check if error is an axios error with response status
        const status =
          typeof error === 'object' &&
          error !== null &&
          'response' in error &&
          typeof (error as { response?: { status?: number } }).response?.status === 'number'
            ? (error as { response?: { status?: number } }).response?.status
            : undefined;

        const isAuthError = status === 401;

        if (!isAuthError) {
          dashboardLogger.warn('[Beta Survey] Failed to fetch survey status', getErrorMessage(error));
        }
      }
    };

    fetchStatus();

    return () => {
      controller.abort();
    };
  }, [player?.player_id, isAuthenticated]);

  const handleSurveyStart = useCallback(() => {
    onDismiss();
    navigate('/survey/beta');
  }, [navigate, onDismiss]);

  const handleSurveyDismiss = useCallback(() => {
    if (player?.player_id) {
      markSurveyDismissed(player.player_id);
    }
    onDismiss();
  }, [player?.player_id, onDismiss]);

  if (!isVisible) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
      <div className="tile-card w-full max-w-lg space-y-4 p-6">
        <h2 className="text-2xl font-display font-bold text-ccl-navy">
          Share your beta feedback
        </h2>
        <p className="text-ccl-navy">
          We&apos;d love to hear how MemeMint feels after ten rounds. Take a short survey to help us tune the beta experience.
        </p>
        {surveyStatus && (
          <p className="text-sm text-ccl-teal">
            You&apos;ve completed <span className="font-semibold">{surveyStatus.total_rounds}</span> rounds so far — perfect!
          </p>
        )}
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={handleSurveyDismiss}
            className="rounded-tile border border-ccl-navy/20 px-5 py-2 font-semibold text-ccl-navy transition hover:border-ccl-teal hover:text-ccl-teal"
          >
            Maybe later
          </button>
          <button
            type="button"
            onClick={handleSurveyStart}
            className="rounded-tile bg-ccl-navy px-6 py-2 font-semibold text-white shadow-tile-sm transition hover:bg-ccl-teal"
          >
            Take the survey
          </button>
        </div>
      </div>
    </div>
  );
};

export default BetaSurveyModal;