import { useMemo } from 'react';
import { PHRASE_VALIDATION_LIMITS } from '@crowdcraft/config/phraseValidation.ts';

const lettersAndSpacesPattern = /^[A-Za-z ]+$/;
const {
  minLengthDefault: MIN_PHRASE_LENGTH,
  maxLengthDefault: MAX_PHRASE_LENGTH,
  minWordsDefault: MIN_WORD_COUNT,
  maxWordsDefault: MAX_WORD_COUNT,
} = PHRASE_VALIDATION_LIMITS;

type PhraseValidationResult = {
  isPhraseValid: boolean;
  trimmedPhrase: string;
};

export const usePhraseValidation = (phrase: string): PhraseValidationResult => {
  const trimmedPhrase = useMemo(() => phrase.trim(), [phrase]);

  const phraseWords = useMemo(
    () => (trimmedPhrase ? trimmedPhrase.split(/\s+/).filter(Boolean) : []),
    [trimmedPhrase],
  );

  const isPhraseValid = useMemo(() => {
    if (!trimmedPhrase) return false;

    const phraseLength = trimmedPhrase.length;
    if (phraseLength < MIN_PHRASE_LENGTH || phraseLength > MAX_PHRASE_LENGTH) {
      return false;
    }

    return (
      lettersAndSpacesPattern.test(trimmedPhrase) &&
      phraseWords.length >= MIN_WORD_COUNT &&
      phraseWords.length <= MAX_WORD_COUNT
    );
  }, [trimmedPhrase, phraseWords]);

  return { isPhraseValid, trimmedPhrase };
};
