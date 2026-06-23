import { useSyncExternalStore } from 'react';
import {
  isSoundMuted,
  setSoundMuted,
  subscribeSoundMuted,
  toggleSoundMuted,
} from '../utils/sound.ts';

export interface SoundSettings {
  muted: boolean;
  setMuted: (next: boolean) => void;
  toggleMuted: () => void;
}

/**
 * Subscribe to the shared sound mute preference. Backed by localStorage so the
 * choice persists per device and stays in sync across every component / tab
 * that reads it.
 */
export function useSoundSettings(): SoundSettings {
  const muted = useSyncExternalStore(subscribeSoundMuted, isSoundMuted, isSoundMuted);
  return {
    muted,
    setMuted: setSoundMuted,
    toggleMuted: toggleSoundMuted,
  };
}

export default useSoundSettings;
