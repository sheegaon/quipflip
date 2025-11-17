import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import Timer from '../components/Timer';
import InitCoinDisplay from '../components/InitCoinDisplay';

// Word validation state for each input
type WordStatus = 'empty' | 'typing' | 'invalid' | 'pending_validation' | 'validating' | 'valid';

interface WordInputState {
  word: string;
  status: WordStatus;
}

const BackronymCreate: React.FC = () => {
  const navigate = useNavigate();
  const { activeSet, player, submitBackronym, validateBackronym, hasSubmittedEntry, loading } = useIRGame();

  const [wordInputs, setWordInputs] = useState<WordInputState[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const validationRequestId = useRef(0);

  // Initialize word inputs when activeSet is available
  useEffect(() => {
    if (activeSet?.word) {
      const letters = activeSet.word.toUpperCase().split('');
      setWordInputs(letters.map(() => ({ word: '', status: 'empty' })));
      inputRefs.current = letters.map(() => null);
    }
  }, [activeSet?.word]);

  // Redirect if no active set
  useEffect(() => {
    if (!loading && !activeSet) {
      navigate('/dashboard');
    }
  }, [activeSet, loading, navigate]);

  // Redirect if already submitted
  useEffect(() => {
    if (hasSubmittedEntry && activeSet) {
      navigate(`/tracking/${activeSet.set_id}`);
    }
  }, [hasSubmittedEntry, activeSet, navigate]);

  if (!activeSet || !player) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-ir-navy to-ir-teal bg-pattern flex items-center justify-center p-4">
        <div className="tile-card max-w-md w-full p-6 text-center text-ir-cream">Loading...</div>
      </div>
    );
  }

  const letters = activeSet.word.toUpperCase().split('');
  const entryCost = 100; // From config

  // Validate a single word
  const validateWord = (word: string, targetLetter: string): WordStatus => {
    if (word.trim() === '') return 'empty';

    const trimmed = word.trim().toUpperCase();

    // Check if starts with correct letter
    if (!trimmed.startsWith(targetLetter)) {
      return 'invalid';
    }

    // Check if valid format (2-15 chars, A-Z only)
    if (trimmed.length < 2 || trimmed.length > 15) {
      return 'typing';
    }

    if (!/^[A-Z]+$/.test(trimmed)) {
      return 'invalid';
    }

    return 'pending_validation';
  };

  // Handle word input change
  const handleWordChange = (index: number, value: string) => {
    const newInputs = [...wordInputs];
    const status = validateWord(value, letters[index]);
    newInputs[index] = { word: value, status };
    setWordInputs(newInputs);
    setError(null);
  };

  // Handle space key to move to next input
  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === ' ' || e.key === 'Tab') && wordInputs[index].word.trim() !== '') {
      if (!['typing', 'invalid'].includes(wordInputs[index].status)) {
        triggerBackendValidation();
      }
    }

    if (e.key === ' ' && wordInputs[index].word.trim() !== '') {
      e.preventDefault();
      if (index < letters.length - 1) {
        inputRefs.current[index + 1]?.focus();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  // Handle paste event to auto-fill all inputs
  const handlePaste = (index: number, e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const pastedText = e.clipboardData.getData('text');
    const words = pastedText.trim().split(/\s+/);

    if (words.length > 0) {
      const newInputs = [...wordInputs];
      words.forEach((word, i) => {
        const targetIndex = index + i;
        if (targetIndex < letters.length) {
          const status = validateWord(word, letters[targetIndex]);
          newInputs[targetIndex] = { word, status };
        }
      });
      setWordInputs(newInputs);
    }
  };

  const triggerBackendValidation = async () => {
    const hasPendingWords = wordInputs.some(
      (input) => input.status === 'pending_validation'
    );

    if (!hasPendingWords || isValidating) {
      return;
    }

    const wordsToValidate = wordInputs.map((input) => input.word.trim().toUpperCase());
    validationRequestId.current += 1;
    const requestId = validationRequestId.current;

    setIsValidating(true);
    setWordInputs((prev) =>
      prev.map((input) =>
        input.status === 'pending_validation' ? { ...input, status: 'validating' } : input
      )
    );

    try {
      const response = await validateBackronym(activeSet.set_id, wordsToValidate);

      if (validationRequestId.current !== requestId) {
        return;
      }

      if (response.is_valid) {
        setWordInputs((prev) =>
          prev.map((input) =>
            input.status === 'validating' || input.status === 'pending_validation'
              ? { ...input, status: 'valid' }
              : input
          )
        );
        setError(null);
      } else {
        setWordInputs((prev) =>
          prev.map((input) =>
            input.status === 'validating' || input.status === 'pending_validation'
              ? { ...input, status: 'invalid' }
              : input
          )
        );
        setError(
          response.error || 'One or more words are invalid. Please adjust and try again.'
        );
      }
    } catch (err: unknown) {
      if (validationRequestId.current !== requestId) {
        return;
      }

      setWordInputs((prev) =>
        prev.map((input) =>
          input.status === 'validating' ? { ...input, status: 'invalid' } : input
        )
      );

      const errorMessage =
        typeof err === 'object' && err !== null && 'message' in err
          ? (err.message as string)
          : 'Unable to validate words. Please try again.';
      setError(errorMessage);
    } finally {
      if (validationRequestId.current === requestId) {
        setIsValidating(false);
      }
    }
  };

  // Get tile color based on status
  const getTileColor = (status: WordStatus): string => {
    switch (status) {
      case 'empty':
        return 'bg-ir-cream border-ir-teal border-opacity-30';
      case 'typing':
        return 'bg-yellow-100 border-yellow-400';
      case 'pending_validation':
      case 'validating':
        return 'bg-yellow-100 border-yellow-400';
      case 'invalid':
        return 'bg-ir-orange bg-opacity-20 border-ir-orange';
      case 'valid':
        return 'bg-ir-teal-light border-ir-turquoise';
      default:
        return 'bg-ir-cream border-ir-teal border-opacity-30';
    }
  };

  // Check if all words are valid
  const allWordsValid = wordInputs.length === letters.length &&
                        wordInputs.every(input => input.status === 'valid');

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!allWordsValid || isSubmitting || isValidating) {
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);

      const backronymWords = wordInputs.map(input => input.word.trim().toUpperCase());
      await submitBackronym(activeSet.set_id, backronymWords);

      // Navigate to tracking page
      navigate(`/tracking/${activeSet.set_id}`);
    } catch (err: unknown) {
      const errorMessage = typeof err === 'object' && err !== null && 'response' in err
        ? ((err.response as any)?.data?.detail) || 'Failed to submit backronym. Please check your words and try again.'
        : typeof err === 'object' && err !== null && 'message' in err
        ? (err.message as string)
        : 'Failed to submit backronym. Please check your words and try again.';
      setError(errorMessage);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-ir-navy to-ir-teal bg-pattern flex items-center justify-center p-4">
      <div className="max-w-4xl w-full tile-card md:p-8 p-5 slide-up-enter">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6 gap-3">
            <div className="text-center sm:text-left">
              <h1 className="text-3xl font-display font-bold text-ir-navy mb-2">Create Your Backronym</h1>
              <p className="text-ir-teal">
                Create a phrase where each word starts with a letter from the target word
              </p>
            </div>

            {/* Timer - only show if we have a deadline */}
            {activeSet.transitions_to_voting_at && (
              <div className="bg-white rounded-tile px-4 py-3 border-2 border-ir-turquoise shadow-tile-sm text-center">
                <div className="text-sm text-ir-teal mb-2 font-semibold">Time remaining</div>
                <Timer
                  targetTime={activeSet.transitions_to_voting_at}
                  compact={true}
                />
              </div>
            )}
          </div>

          {/* Target Word Display */}
          <div className="mb-8">
            <p className="text-sm text-ir-teal text-center mb-3">Target Word:</p>
            <div className="flex justify-center gap-3 mb-6">
              {letters.map((letter, index) => (
                <div
                  key={index}
                  className="w-16 h-16 flex items-center justify-center bg-ir-navy text-white text-3xl font-bold rounded-tile shadow-tile-sm"
                >
                  {letter}
                </div>
              ))}
            </div>
          </div>

          {/* Instructions */}
          <div className="bg-white border-2 border-ir-turquoise rounded-tile p-4 mb-6 shadow-tile-sm">
            <p className="text-sm text-ir-teal">
              <strong className="text-ir-navy">💡 How to play:</strong> Enter one word for each letter. Each word must start with the corresponding letter.
              Words should be 2-15 characters, letters only. Press Space or Tab to move to the next word.
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-tile">
              {error}
            </div>
          )}

          {/* Word Input Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 gap-4">
              {letters.map((letter, index) => (
                <div key={index} className="flex items-center gap-3">
                  {/* Letter indicator */}
                  <div className="w-12 h-12 flex items-center justify-center bg-ir-navy text-white text-xl font-bold rounded-tile flex-shrink-0">
                    {letter}
                  </div>

                  {/* Word input */}
                  <div className="flex-1">
                    <input
                      ref={(el) => (inputRefs.current[index] = el)}
                      type="text"
                      value={wordInputs[index]?.word || ''}
                      onChange={(e) => handleWordChange(index, e.target.value)}
                      onKeyDown={(e) => handleKeyDown(index, e)}
                      onPaste={(e) => handlePaste(index, e)}
                      placeholder={`Word starting with ${letter}...`}
                      className={`w-full px-4 py-3 text-lg border-2 rounded-tile focus:outline-none focus:ring-2 focus:ring-ir-turquoise transition-colors ${getTileColor(wordInputs[index]?.status || 'empty')}`}
                      disabled={isSubmitting}
                      maxLength={15}
                      autoFocus={index === 0}
                    />

                    {/* Status indicator */}
                    <div className="mt-1 text-xs">
                      {wordInputs[index]?.status === 'invalid' && (
                        <span className="text-ir-orange-deep">
                          {wordInputs[index]?.word.trim().toUpperCase().startsWith(letter)
                            ? 'Invalid word format (2-15 letters, A-Z only)'
                            : `Must start with ${letter}`}
                        </span>
                      )}
                      {wordInputs[index]?.status === 'typing' && (
                        <span className="text-ir-orange">Typing...</span>
                      )}
                      {wordInputs[index]?.status === 'pending_validation' && (
                        <span className="text-ir-orange">Ready to validate</span>
                      )}
                      {wordInputs[index]?.status === 'validating' && (
                        <span className="text-ir-orange">Validating...</span>
                      )}
                      {wordInputs[index]?.status === 'valid' && (
                        <span className="text-ir-turquoise">✓ Valid</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Submit Button */}
            <div className="pt-4">
              <button
                type="submit"
                disabled={!allWordsValid || isSubmitting || isValidating}
                className="w-full bg-ir-navy hover:bg-ir-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-4 px-6 rounded-tile transition-colors text-lg shadow-tile-sm"
              >
                {isSubmitting
                  ? 'Submitting...'
                  : isValidating
                  ? 'Validating...'
                  : `Submit Backronym (${entryCost} IC)`}
              </button>
            </div>

            {/* Info */}
            <div className="pt-4 border-t border-ir-navy border-opacity-10">
              <div className="flex items-center justify-between text-sm text-ir-teal">
                <div>
                  <strong>Entry Cost:</strong> <InitCoinDisplay amount={entryCost} />
                </div>
                <div>
                  <strong>Your Balance:</strong> <InitCoinDisplay amount={player.wallet} />
                </div>
              </div>
            </div>
          </form>
      </div>
    </div>
  );
};

export default BackronymCreate;
