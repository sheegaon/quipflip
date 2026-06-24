import React, { useEffect, useState } from 'react';
import { useResults } from '@crowdcraft';
import { useGame } from '../contexts/GameContext';
import MagicLinkPanel from '@crowdcraft/components/MagicLinkPanel.tsx';

interface UpgradeGuestAccountProps {
  className?: string;
}

export const UpgradeGuestAccount: React.FC<UpgradeGuestAccountProps> = ({ className = '' }) => {
  const { state } = useGame();
  const { state: resultsState, actions: resultsActions } = useResults();
  const [showPrompt, setShowPrompt] = useState(false);
  const [checkingHistory, setCheckingHistory] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const evaluateHistory = async () => {
      if (!state.player?.is_guest) {
        if (!cancelled) {
          setShowPrompt(false);
          setCheckingHistory(false);
        }
        return;
      }

      if (resultsState.statistics) {
        if (!cancelled) {
          setShowPrompt(resultsState.statistics.totalRounds > 0);
          setCheckingHistory(false);
        }
        return;
      }

      try {
        const statistics = await resultsActions.getStatistics();
        if (cancelled) {
          return;
        }

        const totalRounds =
          statistics.prompt_stats.total_rounds +
          statistics.copy_stats.total_rounds +
          statistics.voter_stats.total_rounds;
        setShowPrompt(totalRounds > 0);
      } catch {
        if (!cancelled) {
          setShowPrompt(false);
        }
      } finally {
        if (!cancelled) {
          setCheckingHistory(false);
        }
      }
    };

    void evaluateHistory();

    return () => {
      cancelled = true;
    };
  }, [state.player?.is_guest, resultsState.statistics, resultsActions]);

  if (!state.player?.is_guest || checkingHistory || !showPrompt) {
    return null;
  }

  return (
    <div className={className}>
      <MagicLinkPanel
        mode="save"
        title="Keep your stats"
        description="Save your name, wins, awards, and history across devices."
        ctaLabel="Save my account"
        guestPlayerId={state.player.player_id}
      />
    </div>
  );
};

export default UpgradeGuestAccount;
