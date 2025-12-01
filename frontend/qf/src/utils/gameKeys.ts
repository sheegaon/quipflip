export interface PhrasesetListKeyParams {
  role?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export const buildPhrasesetListKey = (params: PhrasesetListKeyParams = {}): string => {
  const entries = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .sort(([a], [b]) => a.localeCompare(b));

  return JSON.stringify(Object.fromEntries(entries));
};
