export const PHRASE_VALIDATION_LIMITS = {
  minWordsDefault: 2,
  maxWordsDefault: 5,
  minLengthDefault: 4,
  maxLengthDefault: 100,
};

export const PHRASE_VALIDATION_BOUNDS = {
  minWords: { min: 1, max: 5 },
  maxWords: { min: 3, max: 10 },
  maxLength: { min: 50, max: 200 },
  minCharsPerWord: { min: 1, max: 5 },
  maxCharsPerWord: { min: 10, max: 30 },
};
