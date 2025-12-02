import React, { useState } from 'react';

export interface EditableConfigFieldProps {
  label: string;
  value: string | number;
  onSave: (value: string) => Promise<void>;
  inputType?: 'text' | 'number';
  description?: string;
}

const EditableConfigField: React.FC<EditableConfigFieldProps> = ({
  label,
  value,
  onSave,
  inputType = 'text',
  description,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(value.toString());
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    try {
      setIsSaving(true);
      await onSave(inputValue);
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
          />

          <div className="flex gap-2">
            <button
              className="btn btn-primary"
              onClick={() => void handleSave()}
              disabled={isSaving}
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
              disabled={isSaving}
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
