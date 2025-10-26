# Phrase Validator Tab - Implementation Guide

## Current Status: Backend Complete, Frontend Partial

### ✅ Completed (Backend)

The backend is **fully implemented and ready to use**:

**Endpoint:** `POST /admin/test-phrase-validation`
**Location:** `backend/routers/admin.py` lines 180-281
**Authentication:** Requires valid JWT token (any authenticated user)

#### Request Format

```typescript
interface TestPhraseValidationRequest {
  phrase: string;                      // The phrase to validate
  validation_type: 'basic' | 'prompt' | 'copy';
  prompt_text?: string | null;         // Required for 'prompt' and 'copy' types
  original_phrase?: string | null;     // Required for 'copy' type
  other_copy_phrase?: string | null;   // Optional for 'copy' type
}
```

#### Response Format

```typescript
interface TestPhraseValidationResponse {
  is_valid: boolean;                   // Overall validation result
  error_message: string | null;        // Human-readable error if invalid

  // Basic details
  word_count: number;                  // Number of words detected
  phrase_length: number;               // Total character count
  words: string[];                     // Array of individual words

  // Similarity scores (0.0 to 1.0)
  prompt_relevance_score: number | null;        // For 'prompt' type
  similarity_to_original: number | null;        // For 'copy' type
  similarity_to_other_copy: number | null;      // For 'copy' type

  // Thresholds from config
  prompt_relevance_threshold: number | null;    // Minimum required (0.05)
  similarity_threshold: number | null;          // Maximum allowed (0.80)

  // Validation checks
  format_check_passed: boolean;        // Format validation result
  dictionary_check_passed: boolean;    // Dictionary validation result
  word_conflicts: string[];            // Words that conflict with prompt/original
}
```

#### Example Usage

```bash
# Test a basic phrase
curl -X POST http://localhost:8000/admin/test-phrase-validation \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phrase": "happy birthday",
    "validation_type": "basic"
  }'

# Test a prompt phrase
curl -X POST http://localhost:8000/admin/test-phrase-validation \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phrase": "joyful celebration",
    "validation_type": "prompt",
    "prompt_text": "something you say to someone on their special day"
  }'

# Test a copy phrase
curl -X POST http://localhost:8000/admin/test-phrase-validation \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phrase": "happy occasion",
    "validation_type": "copy",
    "prompt_text": "something you say to someone on their special day",
    "original_phrase": "happy birthday",
    "other_copy_phrase": "birthday wishes"
  }'
```

---

## 🚧 TODO: Frontend Implementation

### Current Frontend State

**File:** `frontend/src/pages/Admin.tsx`

**Status:**
- State variables are declared but **commented out** (lines 59-66)
- No UI elements exist yet for the phrase validator tab
- Tab navigation doesn't include "Phrase Validator" button

### Step-by-Step Implementation Guide

#### Step 1: Uncomment State Variables

**Location:** `frontend/src/pages/Admin.tsx` lines 59-66

```typescript
// Currently commented out:
// const [validationType, setValidationType] = useState<'basic' | 'prompt' | 'copy'>('basic');
// const [testPhrase, setTestPhrase] = useState('');
// const [promptText, setPromptText] = useState('');
// const [originalPhrase, setOriginalPhrase] = useState('');
// const [otherCopyPhrase, setOtherCopyPhrase] = useState('');
// const [validationResult, setValidationResult] = useState<any | null>(null);
// const [validating, setValidating] = useState(false);

// Uncomment all and add proper type:
const [validationType, setValidationType] = useState<'basic' | 'prompt' | 'copy'>('basic');
const [testPhrase, setTestPhrase] = useState('');
const [promptText, setPromptText] = useState('');
const [originalPhrase, setOriginalPhrase] = useState('');
const [otherCopyPhrase, setOtherCopyPhrase] = useState('');
const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
const [validating, setValidating] = useState(false);
```

Also add the ValidationResult interface at the top of the file:

```typescript
interface ValidationResult {
  is_valid: boolean;
  error_message: string | null;
  word_count: number;
  phrase_length: number;
  words: string[];
  prompt_relevance_score: number | null;
  similarity_to_original: number | null;
  similarity_to_other_copy: number | null;
  prompt_relevance_threshold: number | null;
  similarity_threshold: number | null;
  format_check_passed: boolean;
  dictionary_check_passed: boolean;
  word_conflicts: string[];
}
```

---

#### Step 2: Update Active Tab Type

**Location:** Line 57

```typescript
// Change from:
const [activeTab, setActiveTab] = useState<'economics' | 'timing' | 'validation' | 'ai'>('economics');

// To:
const [activeTab, setActiveTab] = useState<'economics' | 'timing' | 'validation' | 'phrase_validator' | 'ai'>('economics');
```

---

#### Step 3: Add Tab Button to Navigation

**Location:** Around line 275 (in the Tab Navigation section)

Find this section:
```tsx
<div className="tile-card p-2 mb-6">
  <div className="flex flex-wrap gap-2">
    <button onClick={() => setActiveTab('economics')} ...>Economics</button>
    <button onClick={() => setActiveTab('timing')} ...>Timing</button>
    <button onClick={() => setActiveTab('validation')} ...>Validation</button>
    <button onClick={() => setActiveTab('ai')} ...>AI Service</button>
  </div>
</div>
```

Add the Phrase Validator button **between Validation and AI Service**:

```tsx
<button
  onClick={() => setActiveTab('phrase_validator')}
  className={`flex-1 min-w-[100px] py-3 px-4 rounded-tile font-bold transition-all ${
    activeTab === 'phrase_validator'
      ? 'bg-green-600 text-white shadow-tile-sm'
      : 'bg-white text-quip-navy hover:bg-green-600 hover:bg-opacity-10'
  }`}
>
  Phrase Tester
</button>
```

---

#### Step 4: Add Handler Function for Testing Phrases

**Location:** After the `useEffect` block, before the render return statement

```typescript
const handleTestPhrase = async () => {
  if (!testPhrase.trim()) {
    return;
  }

  try {
    setValidating(true);
    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/admin/test-phrase-validation`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('quipflip_access_token')}`,
      },
      body: JSON.stringify({
        phrase: testPhrase,
        validation_type: validationType,
        prompt_text: validationType !== 'basic' ? promptText || null : null,
        original_phrase: validationType === 'copy' ? originalPhrase || null : null,
        other_copy_phrase: validationType === 'copy' ? otherCopyPhrase || null : null,
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to validate phrase');
    }

    const data = await response.json();
    setValidationResult(data);
  } catch (err) {
    setError(extractErrorMessage(err) || 'Failed to test phrase validation');
  } finally {
    setValidating(false);
  }
};
```

---

#### Step 5: Add Phrase Validator Tab Content

**Location:** After the Validation tab content (around line 485), before the AI Service tab

Add this large section:

```tsx
{/* Phrase Validator Tab */}
{activeTab === 'phrase_validator' && (
  <div className="space-y-6">
    <div className="tile-card p-6">
      <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Phrase Validation Tester</h2>
      <p className="text-quip-teal mb-6">
        Test phrase validation as if submitting to a prompt or copy round. See similarity scores and validation details.
      </p>

      {/* Validation Type Selector */}
      <div className="mb-6">
        <label className="block text-sm font-semibold text-quip-navy mb-2">Validation Type</label>
        <div className="flex gap-3">
          <button
            onClick={() => setValidationType('basic')}
            className={`px-4 py-2 rounded-tile font-bold transition-all ${
              validationType === 'basic'
                ? 'bg-quip-navy text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Basic Format
          </button>
          <button
            onClick={() => setValidationType('prompt')}
            className={`px-4 py-2 rounded-tile font-bold transition-all ${
              validationType === 'prompt'
                ? 'bg-quip-navy text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Prompt Round
          </button>
          <button
            onClick={() => setValidationType('copy')}
            className={`px-4 py-2 rounded-tile font-bold transition-all ${
              validationType === 'copy'
                ? 'bg-quip-turquoise text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Copy Round
          </button>
        </div>
      </div>

      {/* Test Phrase Input */}
      <div className="mb-4">
        <label className="block text-sm font-semibold text-quip-navy mb-2">Test Phrase</label>
        <input
          type="text"
          value={testPhrase}
          onChange={(e) => setTestPhrase(e.target.value)}
          className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
          placeholder="Enter phrase to validate..."
        />
      </div>

      {/* Prompt Text (for prompt and copy validation) */}
      {validationType !== 'basic' && (
        <div className="mb-4">
          <label className="block text-sm font-semibold text-quip-navy mb-2">Prompt Text</label>
          <input
            type="text"
            value={promptText}
            onChange={(e) => setPromptText(e.target.value)}
            className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
            placeholder="Enter the original prompt..."
          />
        </div>
      )}

      {/* Copy-specific fields */}
      {validationType === 'copy' && (
        <>
          <div className="mb-4">
            <label className="block text-sm font-semibold text-quip-navy mb-2">Original Phrase (Required for Copy)</label>
            <input
              type="text"
              value={originalPhrase}
              onChange={(e) => setOriginalPhrase(e.target.value)}
              className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
              placeholder="Enter the original prompt phrase..."
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-semibold text-quip-navy mb-2">Other Copy Phrase (Optional)</label>
            <input
              type="text"
              value={otherCopyPhrase}
              onChange={(e) => setOtherCopyPhrase(e.target.value)}
              className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
              placeholder="Enter the other copy phrase if it exists..."
            />
          </div>
        </>
      )}

      {/* Submit Button */}
      <button
        onClick={handleTestPhrase}
        disabled={validating || !testPhrase.trim()}
        className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
      >
        {validating ? 'Validating...' : 'Test Validation'}
      </button>
    </div>

    {/* Validation Results */}
    {validationResult && (
      <div className="tile-card p-6">
        <h3 className="text-xl font-display font-bold text-quip-navy mb-4">Validation Results</h3>

        {/* Overall Status */}
        <div className={`p-4 rounded-tile mb-6 ${validationResult.is_valid ? 'bg-green-100 border-2 border-green-500' : 'bg-red-100 border-2 border-red-500'}`}>
          <div className="flex items-center gap-3">
            {validationResult.is_valid ? (
              <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : (
              <svg className="w-8 h-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
            <div className="flex-1">
              <p className={`font-bold text-lg ${validationResult.is_valid ? 'text-green-800' : 'text-red-800'}`}>
                {validationResult.is_valid ? 'Valid Phrase' : 'Invalid Phrase'}
              </p>
              {validationResult.error_message && (
                <p className="text-red-700 text-sm mt-1">{validationResult.error_message}</p>
              )}
            </div>
          </div>
        </div>

        {/* Basic Details */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-gray-50 border-2 border-gray-200 rounded-tile p-4">
            <p className="text-sm text-quip-teal mb-1">Word Count</p>
            <p className="text-2xl font-bold text-quip-navy">{validationResult.word_count}</p>
            <p className="text-xs text-quip-teal mt-1">Limit: {config.phrase_min_words}-{config.phrase_max_words}</p>
          </div>
          <div className="bg-gray-50 border-2 border-gray-200 rounded-tile p-4">
            <p className="text-sm text-quip-teal mb-1">Character Count</p>
            <p className="text-2xl font-bold text-quip-navy">{validationResult.phrase_length}</p>
            <p className="text-xs text-quip-teal mt-1">Max: {config.phrase_max_length}</p>
          </div>
        </div>

        {/* Words */}
        <div className="mb-6">
          <p className="text-sm font-semibold text-quip-navy mb-2">Words Detected</p>
          <div className="flex flex-wrap gap-2">
            {validationResult.words.map((word, idx) => (
              <span key={idx} className="bg-quip-navy bg-opacity-10 text-quip-navy px-3 py-1 rounded-full text-sm font-semibold">
                {word}
              </span>
            ))}
          </div>
        </div>

        {/* Similarity Scores */}
        {(validationResult.prompt_relevance_score !== null ||
          validationResult.similarity_to_original !== null ||
          validationResult.similarity_to_other_copy !== null) && (
          <div className="space-y-4 mb-6">
            <h4 className="text-lg font-display font-bold text-quip-navy">Similarity Scores</h4>

            {validationResult.prompt_relevance_score !== null && (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-quip-teal">Prompt Relevance</span>
                  <span className="font-bold text-quip-navy">{validationResult.prompt_relevance_score.toFixed(4)}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className={`h-4 rounded-full ${
                      validationResult.prompt_relevance_score >= (validationResult.prompt_relevance_threshold || 0.05)
                        ? 'bg-green-500'
                        : 'bg-red-500'
                    }`}
                    style={{ width: `${Math.min(validationResult.prompt_relevance_score * 100, 100)}%` }}
                  ></div>
                </div>
                <p className="text-xs text-quip-teal mt-1">
                  Threshold: {validationResult.prompt_relevance_threshold?.toFixed(2)} (minimum required)
                </p>
              </div>
            )}

            {validationResult.similarity_to_original !== null && (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-quip-teal">Similarity to Original</span>
                  <span className="font-bold text-quip-navy">{validationResult.similarity_to_original.toFixed(4)}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className={`h-4 rounded-full ${
                      validationResult.similarity_to_original < (validationResult.similarity_threshold || 0.8)
                        ? 'bg-green-500'
                        : 'bg-red-500'
                    }`}
                    style={{ width: `${validationResult.similarity_to_original * 100}%` }}
                  ></div>
                </div>
                <p className="text-xs text-quip-teal mt-1">
                  Threshold: {validationResult.similarity_threshold?.toFixed(2)} (maximum allowed)
                </p>
              </div>
            )}

            {validationResult.similarity_to_other_copy !== null && (
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-quip-teal">Similarity to Other Copy</span>
                  <span className="font-bold text-quip-navy">{validationResult.similarity_to_other_copy.toFixed(4)}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-4">
                  <div
                    className={`h-4 rounded-full ${
                      validationResult.similarity_to_other_copy < (validationResult.similarity_threshold || 0.8)
                        ? 'bg-green-500'
                        : 'bg-red-500'
                    }`}
                    style={{ width: `${validationResult.similarity_to_other_copy * 100}%` }}
                  ></div>
                </div>
                <p className="text-xs text-quip-teal mt-1">
                  Threshold: {validationResult.similarity_threshold?.toFixed(2)} (maximum allowed)
                </p>
              </div>
            )}
          </div>
        )}

        {/* Word Conflicts */}
        {validationResult.word_conflicts.length > 0 && (
          <div className="mb-6">
            <p className="text-sm font-semibold text-quip-navy mb-2">Word Conflicts</p>
            <div className="flex flex-wrap gap-2">
              {validationResult.word_conflicts.map((word, idx) => (
                <span key={idx} className="bg-red-100 text-red-700 px-3 py-1 rounded-full text-sm font-semibold border-2 border-red-300">
                  {word}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Validation Checks */}
        <div className="grid grid-cols-2 gap-4">
          <div className={`p-3 rounded-tile border-2 ${
            validationResult.format_check_passed
              ? 'bg-green-50 border-green-300'
              : 'bg-red-50 border-red-300'
          }`}>
            <p className="text-sm font-semibold">Format Check</p>
            <p className={`text-lg font-bold ${
              validationResult.format_check_passed ? 'text-green-700' : 'text-red-700'
            }`}>
              {validationResult.format_check_passed ? 'Passed' : 'Failed'}
            </p>
          </div>
          <div className={`p-3 rounded-tile border-2 ${
            validationResult.dictionary_check_passed
              ? 'bg-green-50 border-green-300'
              : 'bg-red-50 border-red-300'
          }`}>
            <p className="text-sm font-semibold">Dictionary Check</p>
            <p className={`text-lg font-bold ${
              validationResult.dictionary_check_passed ? 'text-green-700' : 'text-red-700'
            }`}>
              {validationResult.dictionary_check_passed ? 'Passed' : 'Failed'}
            </p>
          </div>
        </div>
      </div>
    )}
  </div>
)}
```

---

## Testing the Implementation

### Manual Testing Steps

1. **Login to Quipflip** as any user
2. **Navigate to Admin Panel**:
   - Click username in header → Statistics
   - Click Settings button
   - Enter admin password (SECRET_KEY from .env)
   - Click "Access Admin Panel"
3. **Click "Phrase Tester" tab**
4. **Test Basic Validation**:
   - Select "Basic Format"
   - Enter phrase: "happy birthday"
   - Click "Test Validation"
   - Should show: Valid, 2 words, all checks passed
5. **Test Invalid Phrase**:
   - Enter: "x" (too short)
   - Should show: Invalid, error message
6. **Test Prompt Round**:
   - Select "Prompt Round"
   - Enter phrase: "joyful celebration"
   - Enter prompt: "something you say to someone on their special day"
   - Should show: Valid with prompt relevance score
7. **Test Copy Round**:
   - Select "Copy Round"
   - Enter phrase: "happy occasion"
   - Enter prompt: "something you say to someone on their special day"
   - Enter original: "happy birthday"
   - Should show: Similarity scores to original

### Expected Results Display

For a valid phrase, you should see:
- ✅ Green check mark with "Valid Phrase"
- Word count and character count
- List of words detected
- Similarity scores (if applicable) with visual progress bars
- Green/red color coding for pass/fail thresholds
- Format and dictionary check status

For an invalid phrase, you should see:
- ❌ Red X mark with "Invalid Phrase"
- Specific error message (e.g., "Phrase too similar to original")
- Same stats and scores
- Word conflicts highlighted in red
- Failed checks shown in red

---

## Understanding the Validation Types

### Basic Format Validation
Tests fundamental requirements:
- Minimum 4 characters
- Maximum 100 characters
- 1-5 words
- 2-15 characters per word
- Only letters A-Z and spaces
- All words in dictionary.txt

### Prompt Round Validation
Includes basic validation plus:
- **Prompt relevance check**: Phrase must be similar enough to prompt (≥0.05 cosine similarity)
- **Word conflict check**: Can't reuse significant words (4+ chars) from prompt

### Copy Round Validation
Includes basic validation plus:
- **Similarity to original**: Must be different enough (<0.80 cosine similarity)
- **Similarity to other copy**: If exists, must be different (<0.80 cosine similarity)
- **Word conflicts**: Can't reuse significant words from original, other copy, or prompt

---

## Similarity Score Interpretation

### Cosine Similarity Scale (0.0 to 1.0)

- **0.0**: Completely different phrases (no word overlap)
- **0.2**: Somewhat related phrases
- **0.5**: Moderately similar phrases
- **0.8**: Very similar phrases (threshold for copies)
- **1.0**: Identical phrases

### Visual Indicators

The UI shows progress bars for each score:
- **Green bar**: Score is acceptable (passes threshold)
- **Red bar**: Score violates threshold (fails validation)

For prompt relevance:
- Must be **≥ 0.05** (minimum similarity required)
- Green if above threshold

For copy similarity:
- Must be **< 0.80** (maximum similarity allowed)
- Green if below threshold

---

## Common Issues and Troubleshooting

### Issue: Validation always returns "Invalid"
**Cause:** Dictionary.txt not loaded on backend
**Fix:** Run `python3 scripts/download_dictionary.py` in backend directory

### Issue: Similarity scores always 0.0
**Cause:** Sentence transformers not installed or disabled
**Fix:** Check `USE_SENTENCE_TRANSFORMERS` environment variable

### Issue: "Failed to validate phrase" error
**Cause:** Not authenticated or token expired
**Fix:** Logout and login again to refresh token

### Issue: Tab doesn't appear
**Cause:** TypeScript errors preventing build
**Fix:** Ensure all state variables are uncommented and typed correctly

---

## Files Modified

### Backend (Already Complete)
- ✅ `backend/routers/admin.py` - Validation endpoint implemented

### Frontend (To Complete)
- 🚧 `frontend/src/pages/Admin.tsx` - Add UI components (follow steps above)

### No Additional Files Needed
All functionality uses existing:
- Phrase validation service (`backend/services/phrase_validator.py`)
- Authentication system (JWT tokens)
- Existing Quipflip styling (tile-card, quip-navy colors, etc.)

---

## Estimated Time to Complete

- **Step 1**: Uncomment variables - 2 minutes
- **Step 2**: Update tab type - 1 minute
- **Step 3**: Add tab button - 5 minutes
- **Step 4**: Add handler function - 5 minutes
- **Step 5**: Add tab content - 15 minutes
- **Testing**: 10-15 minutes

**Total: 30-45 minutes**

---

## Future Enhancements

Potential improvements for v2:

1. **Saved Test Cases**: Save frequently used test scenarios
2. **Batch Testing**: Test multiple phrases at once
3. **Export Results**: Download validation results as CSV
4. **Visualization**: Show word overlap visually with highlighting
5. **Comparison Mode**: Side-by-side phrase comparison
6. **History**: View previous test results
7. **Thresholds Override**: Temporarily adjust thresholds for testing

---

## Related Documentation

- **Phrase Validation System**: See backend exploration results in this session
- **Admin Panel Plan**: `docs/ADMIN_PLAN.md`
- **Settings Plan**: `docs/SETTINGS_PLAN.md`
- **Backend Config**: `backend/config.py` lines 57-71 (validation settings)
