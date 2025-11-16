// Game state management keys for localStorage and session tracking

export const GAME_STORAGE_KEYS = {
  ACTIVE_SET_ID: 'ir_active_set_id',
  PLAYER_ID: 'ir_player_id',
  IS_AUTHENTICATED: 'ir_is_authenticated',
  LAST_BONUS_CLAIM: 'ir_last_bonus_claim',
} as const;

export const clearGameStorage = () => {
  Object.values(GAME_STORAGE_KEYS).forEach((key) => {
    localStorage.removeItem(key);
  });
};

export const getActiveSetId = (): string | null => {
  return localStorage.getItem(GAME_STORAGE_KEYS.ACTIVE_SET_ID);
};

export const setActiveSetId = (setId: string | null) => {
  if (setId) {
    localStorage.setItem(GAME_STORAGE_KEYS.ACTIVE_SET_ID, setId);
  } else {
    localStorage.removeItem(GAME_STORAGE_KEYS.ACTIVE_SET_ID);
  }
};

export const getPlayerId = (): string | null => {
  return localStorage.getItem(GAME_STORAGE_KEYS.PLAYER_ID);
};

export const setPlayerId = (playerId: string | null) => {
  if (playerId) {
    localStorage.setItem(GAME_STORAGE_KEYS.PLAYER_ID, playerId);
  } else {
    localStorage.removeItem(GAME_STORAGE_KEYS.PLAYER_ID);
  }
};
