import React, { useState } from 'react';
import { extractErrorMessage } from '../api/client';

interface EditableConfigFieldProps {
  label: string;
  value: number | string;
  configKey: string;
  unit?: string;
  description?: string;
  min?: number;
  max?: number;
  type: 'number' | 'text' | 'select';
  options?: string[];
  onSave: (key: string, value: number | string) => Promise<void>;
  disabled?: boolean;
}

export const EditableConfigField: React.FC<EditableConfigFieldProps> = ({
  label,
  value,
  configKey,
  unit,
  description,
  min,
  max,
  type,
  options,
  onSave,
  disabled = false,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState<string>(String(value));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEdit = () => {
    if (disabled) return;
    setIsEditing(true);
    setEditValue(String(value));
    setError(null);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditValue(String(value));
    setError(null);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      // Validate and parse value
      let parsedValue: number | string;
      if (type === 'number') {
        parsedValue = parseInt(editValue, 10);
        if (isNaN(parsedValue)) {
          setError('Invalid number');
          return;
        }
        if (min !== undefined && parsedValue < min) {
          setError(`Value must be at least ${min}`);
          return;
        }
        if (max !== undefined && parsedValue > max) {
          setError(`Value must be at most ${max}`);
          return;
        }
      } else {
        parsedValue = editValue;
      }

      // Call the onSave callback
      await onSave(configKey, parsedValue);

      setIsEditing(false);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  };

  return (
    <div className="border-b border-gray-200 last:border-b-0 py-3">
      <div className="flex justify-between items-start">
        <div className="flex-1">
          <label className="block text-sm font-semibold text-quip-navy mb-1">{label}</label>
          {description && <p className="text-xs text-quip-teal">{description}</p>}
          {min !== undefined && max !== undefined && (
            <p className="text-xs text-gray-500 mt-1">Valid range: {min} - {max}</p>
          )}
          {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
        </div>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <>
              {type === 'select' && options ? (
                <select
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="border-2 border-quip-orange rounded px-3 py-1 font-bold text-quip-navy focus:outline-none focus:ring-2 focus:ring-quip-orange"
                  autoFocus
                >
                  {options.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={type === 'number' ? 'number' : 'text'}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="border-2 border-quip-orange rounded px-3 py-1 min-w-[100px] text-right font-bold text-quip-navy focus:outline-none focus:ring-2 focus:ring-quip-orange"
                  min={min}
                  max={max}
                  autoFocus
                  disabled={saving}
                />
              )}
              <button
                onClick={handleSave}
                disabled={saving}
                className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded transition-colors disabled:opacity-50"
                title="Save"
              >
                {saving ? (
                  <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-solid border-white border-r-transparent"></div>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
              <button
                onClick={handleCancel}
                disabled={saving}
                className="bg-gray-500 hover:bg-gray-600 text-white px-3 py-1 rounded transition-colors disabled:opacity-50"
                title="Cancel"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </>
          ) : (
            <>
              <div
                className={`bg-white border-2 border-quip-navy border-opacity-20 rounded px-3 py-1 min-w-[100px] text-right ${!disabled && 'cursor-pointer hover:border-quip-orange hover:border-opacity-50 transition-colors'}`}
                onClick={handleEdit}
              >
                <span className="font-bold text-quip-navy">{value}</span>
                {unit && <span className="text-sm text-quip-teal ml-1">{unit}</span>}
              </div>
              {!disabled && (
                <button
                  onClick={handleEdit}
                  className="text-quip-navy hover:text-quip-orange transition-colors p-1"
                  title="Edit"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z" />
                  </svg>
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
