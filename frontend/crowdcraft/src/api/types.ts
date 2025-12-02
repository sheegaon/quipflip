// Shared CrowdCraft API types used by game-specific clients
// These types are derived from the common endpoints documented in docs/API.md

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  player_id: string;
  username: string;
}

export interface WsAuthTokenResponse {
  token: string;
  expires_in: number;
  token_type: 'bearer';
}

export interface SuggestUsernameResponse {
  suggested_username: string;
}

export interface ApiError {
  detail: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  redis: string;
}

export interface ApiInfo {
  message: string;
  version: string;
  environment: string;
  docs: string;
}

export interface GameStatus {
  version: string;
  environment: string;
  phrase_validation: {
    mode: 'local' | 'remote';
    healthy: boolean | null;
  };
}
