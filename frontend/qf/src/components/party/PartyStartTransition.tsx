import React, { useEffect, useRef, useState } from 'react';
import { playSound } from '@crowdcraft/utils/sound.ts';

interface PartyStartTransitionProps {
  /** Number of players entering the game, shown in the subtitle. */
  playerCount: number;
  /** Called once the brief countdown finishes. */
  onComplete: () => void;
}

const COUNTDOWN_START = 3;
const STEP_MS = 650;
const FINALE_MS = 700;
const TILES = ['Q', 'U', 'I', 'P'] as const;

const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Brief, celebratory full-screen hand-off from the lobby to the game. Flips the
 * QuipFlip tiles in, counts down 3-2-1, then calls onComplete so the lobby can
 * navigate into the round. Honours prefers-reduced-motion by skipping the
 * animated countdown and finishing almost immediately.
 */
export const PartyStartTransition: React.FC<PartyStartTransitionProps> = ({
  playerCount,
  onComplete,
}) => {
  const [count, setCount] = useState(COUNTDOWN_START);
  const reduced = useRef(prefersReducedMotion());
  const completedRef = useRef(false);
  const onCompleteRef = useRef(onComplete);

  // Play the celebratory cue once on mount.
  useEffect(() => {
    playSound('start');
  }, []);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    const finish = () => {
      if (completedRef.current) return;
      completedRef.current = true;
      onCompleteRef.current();
    };

    if (reduced.current) {
      const timeout = window.setTimeout(finish, 600);
      return () => window.clearTimeout(timeout);
    }

    const timers: number[] = [];
    for (let n = COUNTDOWN_START - 1; n >= 0; n -= 1) {
      const step = COUNTDOWN_START - n;
      timers.push(window.setTimeout(() => setCount(n), step * STEP_MS));
    }
    timers.push(window.setTimeout(finish, COUNTDOWN_START * STEP_MS + FINALE_MS));

    return () => timers.forEach((id) => window.clearTimeout(id));
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-gradient-to-br from-ccl-orange to-ccl-turquoise bg-pattern party-transition-overlay"
      role="status"
      aria-live="assertive"
    >
      <div className="flex flex-col items-center text-center px-6">
        <div className="flex gap-2 sm:gap-3 mb-8">
          {TILES.map((letter, index) => (
            <span
              key={letter}
              className="party-transition-tile flex items-center justify-center w-14 h-14 sm:w-16 sm:h-16 rounded-tile bg-white text-ccl-orange-deep font-display font-bold text-3xl sm:text-4xl shadow-tile"
              style={{ animationDelay: `${index * 110}ms` }}
            >
              {letter}
            </span>
          ))}
        </div>

        <h1 className="text-4xl sm:text-5xl font-display font-bold text-white drop-shadow-md mb-3">
          Get ready!
        </h1>

        <div className="h-20 flex items-center justify-center" aria-hidden="true">
          <span
            key={count}
            className="party-transition-count font-display font-bold text-white drop-shadow-lg"
          >
            {count > 0 ? count : 'Go!'}
          </span>
        </div>

        <p className="text-white/90 font-semibold text-lg mt-2">
          Starting with {playerCount} player{playerCount === 1 ? '' : 's'}
        </p>
      </div>
    </div>
  );
};

export default PartyStartTransition;
