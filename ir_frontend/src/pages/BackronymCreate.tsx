import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import Header from '../components/Header';
import Timer from '../components/Timer';
import InitCoinDisplay from '../components/InitCoinDisplay';

// Word validation state for each input
type WordStatus = 'empty' | 'typing' | 'invalid' | 'valid';

interface WordInputState {
  word: string;
  status: WordStatus;
}

const BackronymCreate: React.FC = () => {
  const navigate = useNavigate();
  const { activeSet, player, submitBackronym, checkSetStatus, hasSubmittedEntry, loading } = useIRGame();

  const [wordInputs, setWordInputs] = useState<WordInputState[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

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
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
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

    return 'valid';
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
    if (e.key === ' ' && wordInputs[index].word.trim() !== '') {
      e.preventDefault();
      if (index < letters.length - 1) {
        inputRefs.current[index + 1]?.focus();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e as any);
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

  // Get tile color based on status
  const getTileColor = (status: WordStatus): string => {
    switch (status) {
      case 'empty':
        return 'bg-gray-200 border-gray-300';
      case 'typing':
        return 'bg-yellow-100 border-yellow-400';
      case 'invalid':
        return 'bg-red-100 border-red-400';
      case 'valid':
        return 'bg-green-100 border-green-500';
      default:
        return 'bg-gray-200 border-gray-300';
    }
  };

  // Check if all words are valid
  const allWordsValid = wordInputs.length === letters.length &&
                        wordInputs.every(input => input.status === 'valid');

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!allWordsValid || isSubmitting) {
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);

      const backronymWords = wordInputs.map(input => input.word.trim().toUpperCase());
      await submitBackronym(activeSet.set_id, backronymWords);

      // Navigate to tracking page
      navigate(`/tracking/${activeSet.set_id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to submit backronym. Please check your words and try again.');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <Header />
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Create Your Backronym</h1>
            <p className="text-gray-600 mb-4">
              Create a phrase where each word starts with a letter from the target word
            </p>

            {/* Timer - only show if we have a deadline */}
            {activeSet.transitions_to_voting_at && (
              <div className="flex justify-center mb-4">
                <Timer
                  targetTime={activeSet.transitions_to_voting_at}
                  className="text-2xl font-bold text-blue-600"
                />
              </div>
            )}
          </div>

          {/* Main Card */}
          <div className="bg-white rounded-lg shadow-lg p-8">
            {/* Target Word Display */}
            <div className="mb-8">
              <p className="text-sm text-gray-600 text-center mb-3">Target Word:</p>
              <div className="flex justify-center gap-3 mb-6">
                {letters.map((letter, index) => (
                  <div
                    key={index}
                    className="w-16 h-16 flex items-center justify-center bg-blue-600 text-white text-3xl font-bold rounded-lg shadow-md"
                  >
                    {letter}
                  </div>
                ))}
              </div>
            </div>

            {/* Instructions */}
            <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
              <p className="text-sm text-gray-700">
                <strong>💡 How to play:</strong> Enter one word for each letter. Each word must start with the corresponding letter.
                Words should be 2-15 characters, letters only. Press Space or Tab to move to the next word.
              </p>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
              </div>
            )}

            {/* Word Input Form */}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 gap-4">
                {letters.map((letter, index) => (
                  <div key={index} className="flex items-center gap-3">
                    {/* Letter indicator */}
                    <div className="w-12 h-12 flex items-center justify-center bg-blue-600 text-white text-xl font-bold rounded-lg flex-shrink-0">
                      {letter}
                    </div>

                    {/* Word input */}
                    <div className="flex-1">
                      <input
                        ref={el => inputRefs.current[index] = el}
                        type="text"
                        value={wordInputs[index]?.word || ''}
                        onChange={(e) => handleWordChange(index, e.target.value)}
                        onKeyDown={(e) => handleKeyDown(index, e)}
                        onPaste={(e) => handlePaste(index, e)}
                        placeholder={`Word starting with ${letter}...`}
                        className={`w-full px-4 py-3 text-lg border-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors ${getTileColor(wordInputs[index]?.status || 'empty')}`}
                        disabled={isSubmitting}
                        maxLength={15}
                        autoFocus={index === 0}
                      />

                      {/* Status indicator */}
                      <div className="mt-1 text-xs">
                        {wordInputs[index]?.status === 'invalid' && (
                          <span className="text-red-600">
                            {wordInputs[index]?.word.trim().toUpperCase().startsWith(letter)
                              ? 'Invalid word format (2-15 letters, A-Z only)'
                              : `Must start with ${letter}`}
                          </span>
                        )}
                        {wordInputs[index]?.status === 'typing' && (
                          <span className="text-yellow-600">Typing...</span>
                        )}
                        {wordInputs[index]?.status === 'valid' && (
                          <span className="text-green-600">✓ Valid</span>
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
                  disabled={!allWordsValid || isSubmitting}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-bold py-4 px-6 rounded-lg transition-colors text-lg shadow-md"
                >
                  {isSubmitting ? 'Submitting...' : `Submit Backronym (${entryCost} IC)`}
                </button>
              </div>

              {/* Info */}
              <div className="pt-4 border-t border-gray-200">
                <div className="flex items-center justify-between text-sm text-gray-600">
                  <div>
                    <strong>Entry Cost:</strong> <InitCoinDisplay amount={entryCost} />
                  </div>
                  <div>
                    <strong>Your Balance:</strong> <InitCoinDisplay amount={player.wallet} />
                  </div>
                </div>
              </div>
            </form>

            {/* Back Button */}
            <button
              onClick={() => navigate('/dashboard')}
              disabled={isSubmitting}
              className="w-full mt-4 flex items-center justify-center gap-2 text-gray-600 hover:text-gray-800 disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
              <span>Back to Dashboard</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BackronymCreate;
