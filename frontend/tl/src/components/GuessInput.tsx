import React, { useRef, useEffect } from 'react';

interface GuessInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isSubmitting: boolean;
  error?: string | null;
  maxLength?: number;
  placeholder?: string;
  disabled?: boolean;
  autoFocus?: boolean;
}

export const GuessInput: React.FC<GuessInputProps> = ({
  value,
  onChange,
  onSubmit,
  isSubmitting,
  error,
  maxLength = 200,
  placeholder = 'Type an answer...',
  disabled = false,
  autoFocus = true,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus input on mount
  useEffect(() => {
    if (autoFocus) {
      inputRef.current?.focus();
    }
  }, [autoFocus]);

  // Re-focus input after submission
  useEffect(() => {
    if (!isSubmitting) {
      inputRef.current?.focus();
    }
  }, [isSubmitting]);

  const wordCount = value.trim().split(/\s+/).filter(w => w.length > 0).length;
  const characterCount = value.length;
  const isSubmitDisabled = isSubmitting || !value.trim() || disabled;

  return (
    <div className="space-y-2">
      <form onSubmit={onSubmit} className="tile-card p-6">
        <label className="block text-sm font-semibold text-ccl-teal mb-2">
          Enter your guess
        </label>
        <div className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={isSubmitting || disabled}
            maxLength={maxLength}
            className="flex-1 px-4 py-3 border-2 border-ccl-navy rounded-tile focus:outline-none focus:ring-2 focus:ring-ccl-orange disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isSubmitDisabled}
            className="bg-ccl-orange hover:bg-ccl-orange-deep text-white font-bold py-3 px-6 rounded-tile disabled:opacity-50 transition-all whitespace-nowrap"
          >
            {isSubmitting ? 'Submitting...' : 'Submit'}
          </button>
        </div>
        <div className="flex justify-between items-center mt-2">
          <p className="text-xs text-ccl-teal">
            {characterCount}/{maxLength} characters · {wordCount} {wordCount === 1 ? 'word' : 'words'}
          </p>
        </div>
      </form>

      {error && (
        <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded-tile text-sm">
          {error}
        </div>
      )}
    </div>
  );
};

export default GuessInput;
