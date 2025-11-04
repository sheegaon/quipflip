import { useMemo } from 'react';

const lettersAndSpacesPattern = /^[A-Za-z ]+$/;

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

    return (
      lettersAndSpacesPattern.test(trimmedPhrase) &&
      phraseWords.length >= 2 &&
      phraseWords.length <= 5
    );
  }, [trimmedPhrase, phraseWords]);

  return { isPhraseValid, trimmedPhrase };
};
