const GAME_PREFIX = /\/(qf|mm|ir|tl)(\/)?$/;

export const resolveApiRoot = (
  configuredUrl: string | undefined,
  browserOrigin: string,
): string => {
  const configured = configuredUrl?.trim();
  return (configured || browserOrigin).replace(/\/$/, '').replace(GAME_PREFIX, '');
};

export const resolveGameApiUrl = (
  game: 'qf' | 'mm' | 'ir' | 'tl',
  configuredUrl: string | undefined,
  browserOrigin: string,
): string => {
  const configured = configuredUrl?.trim().replace(/\/$/, '');
  if (configured && new RegExp(`/${game}($|/)`).test(configured)) {
    return configured;
  }
  return `${resolveApiRoot(configuredUrl, browserOrigin)}/${game}`;
};

export const resolveWebSocketUrl = (
  path: string,
  configuredApiUrl: string | undefined,
  browserOrigin: string,
): URL => {
  const root = resolveApiRoot(configuredApiUrl, browserOrigin);
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  const url = new URL(cleanPath, `${root}/`);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url;
};
