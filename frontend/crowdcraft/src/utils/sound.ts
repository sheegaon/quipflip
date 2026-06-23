/**
 * Lightweight Web Audio sound engine for party / lobby cues.
 *
 * Sounds are synthesized at runtime from short oscillator envelopes, so they
 * add zero network weight and can be tuned directly in code. A single shared
 * AudioContext is created lazily on first use and resumed on demand because
 * browsers require a user gesture before audio may start.
 *
 * Mute state is persisted to localStorage and exposed through a tiny
 * subscribe / getSnapshot store so React components can mirror it with
 * useSyncExternalStore (see useSoundSettings).
 */
import { SOUND_MUTED_KEY } from './storageKeys';

export type SoundName = 'join' | 'leave' | 'ready' | 'ping' | 'start';

interface Note {
  /** Frequency in Hz. */
  freq: number;
  /** Offset from playback start, in seconds. */
  start: number;
  /** Note length in seconds. */
  duration: number;
  type?: OscillatorType;
  /** Peak gain (0–1). Kept modest so cues are noticeable but never jarring. */
  gain?: number;
}

// Note frequencies (Hz) used by the recipes below.
const C5 = 523.25;
const E5 = 659.25;
const G5 = 783.99;
const A5 = 880.0;
const B5 = 987.77;
const C6 = 1046.5;
const D6 = 1174.66;

const SOUND_RECIPES: Record<SoundName, Note[]> = {
  // Cheerful rising two-note "bloop" when someone arrives.
  join: [
    { freq: E5, start: 0, duration: 0.12, type: 'triangle', gain: 0.16 },
    { freq: B5, start: 0.1, duration: 0.16, type: 'triangle', gain: 0.16 },
  ],
  // Softer falling two-note when someone leaves.
  leave: [
    { freq: G5, start: 0, duration: 0.12, type: 'triangle', gain: 0.12 },
    { freq: C5, start: 0.1, duration: 0.18, type: 'triangle', gain: 0.11 },
  ],
  // Subtle single blip when a player marks ready.
  ready: [{ freq: C6, start: 0, duration: 0.1, type: 'sine', gain: 0.12 }],
  // Insistent attention cue for a host ping.
  ping: [
    { freq: A5, start: 0, duration: 0.09, type: 'triangle', gain: 0.22 },
    { freq: A5, start: 0.15, duration: 0.09, type: 'triangle', gain: 0.22 },
    { freq: D6, start: 0.3, duration: 0.18, type: 'triangle', gain: 0.22 },
  ],
  // Celebratory arpeggio when the game is about to start.
  start: [
    { freq: C5, start: 0, duration: 0.12, type: 'triangle', gain: 0.18 },
    { freq: E5, start: 0.1, duration: 0.12, type: 'triangle', gain: 0.18 },
    { freq: G5, start: 0.2, duration: 0.12, type: 'triangle', gain: 0.18 },
    { freq: C6, start: 0.3, duration: 0.3, type: 'triangle', gain: 0.2 },
  ],
};

// --- Mute store -----------------------------------------------------------

let muted = readInitialMuted();
const listeners = new Set<() => void>();

function readInitialMuted(): boolean {
  try {
    return localStorage.getItem(SOUND_MUTED_KEY) === 'true';
  } catch {
    return false;
  }
}

export function isSoundMuted(): boolean {
  return muted;
}

export function setSoundMuted(next: boolean): void {
  if (muted === next) return;
  muted = next;
  try {
    localStorage.setItem(SOUND_MUTED_KEY, String(next));
  } catch {
    // Ignore storage failures (private mode, quota); state still lives in memory.
  }
  listeners.forEach((listener) => listener());
}

export function toggleSoundMuted(): void {
  setSoundMuted(!muted);
}

export function subscribeSoundMuted(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

// --- Audio playback -------------------------------------------------------

type AudioContextCtor = typeof AudioContext;

let audioContext: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  const Ctor: AudioContextCtor | undefined =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: AudioContextCtor }).webkitAudioContext;
  if (!Ctor) return null;
  if (!audioContext) {
    try {
      audioContext = new Ctor();
    } catch {
      return null;
    }
  }
  return audioContext;
}

/**
 * Resume the audio context in response to a user gesture. Browsers start the
 * context "suspended" until the page has been interacted with, so call this
 * from a click / keydown handler to make the first cue audible.
 */
export function primeAudio(): void {
  const ctx = getContext();
  if (ctx && ctx.state === 'suspended') {
    void ctx.resume();
  }
}

export function playSound(name: SoundName): void {
  if (muted) return;
  const ctx = getContext();
  if (!ctx) return;
  if (ctx.state === 'suspended') {
    void ctx.resume();
  }

  const recipe = SOUND_RECIPES[name];
  const now = ctx.currentTime;

  for (const note of recipe) {
    const osc = ctx.createOscillator();
    const gainNode = ctx.createGain();
    osc.type = note.type ?? 'sine';
    osc.frequency.value = note.freq;

    const peak = note.gain ?? 0.16;
    const startAt = now + note.start;
    const endAt = startAt + note.duration;

    // Quick attack, exponential release for a soft, click-free envelope.
    gainNode.gain.setValueAtTime(0.0001, startAt);
    gainNode.gain.exponentialRampToValueAtTime(peak, startAt + 0.012);
    gainNode.gain.exponentialRampToValueAtTime(0.0001, endAt);

    osc.connect(gainNode).connect(ctx.destination);
    osc.start(startAt);
    osc.stop(endAt + 0.03);
  }
}
