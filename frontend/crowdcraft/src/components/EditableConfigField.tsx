import React, { useState } from 'react';

export interface EditableConfigFieldProps {
  label: string;
  value: string | number;
  onSave: (key: string, value: string | number) => Promise<void>;
  inputType?: 'text' | 'number';
  description?: string;
  configKey?: string;
  unit?: string;
  type?: string;
  options?: string[];
  min?: number;
  max?: number;
  disabled?: boolean;
}

const EditableConfigField: React.FC<EditableConfigFieldProps> = ({
  label,
  value,
  onSave,
  inputType = 'text',
  description,
  configKey,
  min,
  max,
  disabled,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(value.toString());
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    try {
      setIsSaving(true);
      const parsedValue = inputType === 'number' ? Number(inputValue) : inputValue;
      await onSave(configKey ?? label, parsedValue);
      setIsEditing(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      void handleSave();
    }

    if (event.key === 'Escape') {
      setIsEditing(false);
      setInputValue(value.toString());
      setError(null);
    }
  };

  return (
    <div className="tile-card p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <label className="block text-sm font-medium text-gray-700">{label}</label>
          {description && <p className="text-sm text-gray-500">{description}</p>}
        </div>
        {!isEditing && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setIsEditing(true)}
            disabled={disabled}
          >
            Edit
          </button>
        )}
      </div>

      {isEditing ? (
        <div className="space-y-3">
          <input
            type={inputType}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="input input-bordered w-full"
            min={min}
            max={max}
            disabled={disabled}
          />

          <div className="flex gap-2">
            <button
              className="btn btn-primary"
              onClick={() => void handleSave()}
              disabled={isSaving || disabled}
            >
              {isSaving ? 'Saving...' : 'Save'}
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => {
                setIsEditing(false);
                setInputValue(value.toString());
                setError(null);
              }}
              disabled={isSaving || disabled}
            >
              Cancel
            </button>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
      ) : (
        <p className="text-lg font-semibold">{value}</p>
      )}
    </div>
  );
};

export default EditableConfigField;
