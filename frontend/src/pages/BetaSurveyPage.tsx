import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '../api/client';
import { Header } from '../components/Header';
import { useGame } from '../contexts/GameContext';
import type { SurveyDefinition, SurveyQuestion, CompoundSurveyQuestion } from '../types/survey';
import { BETA_SURVEY_ID, markSurveyCompleted } from '../utils/betaSurvey';
import type { BetaSurveyAnswerPayload } from '../api/types';

const betaSurveyDefinition: SurveyDefinition = {
  id: BETA_SURVEY_ID,
  title: 'Quipflip Beta Tester Survey',
  description: 'Help us polish Quipflip before launch by sharing your beta impressions.',
  requiredQuestionIds: ['q1', 'q2', 'q5', 'q6', 'q7', 'q10', 'q11'],
  sections: [
    {
      id: 'section-gameplay',
      title: '💬 Section 1 — Gameplay Experience',
      questions: [
        {
          id: 'q1',
          type: 'scale',
          title: 'How intuitive did you find the Prompt → Copy → Vote flow?',
          required: true,
          options: [
            { value: 1, label: '1️⃣ Very confusing' },
            { value: 2, label: '2️⃣ Somewhat confusing' },
            { value: 3, label: '3️⃣ Neutral' },
            { value: 4, label: '4️⃣ Easy to follow' },
            { value: 5, label: '5️⃣ Instantly clear' },
          ],
        },
        {
          id: 'q2',
          type: 'multi',
          title: 'Which phase did you enjoy most?',
          required: true,
          options: [
            { value: 'prompt', label: 'Prompt' },
            { value: 'copy', label: 'Copy' },
            { value: 'vote', label: 'Vote' },
            { value: 'results', label: 'Viewing results' },
          ],
        },
        {
          id: 'q3',
          type: 'text',
          title: 'What felt least clear or engaging about any phase?',
          placeholder: 'Share any confusing steps or feedback ideas',
        },
        {
          id: 'q4',
          type: 'compound',
          title: 'Did you ever feel “stuck” or unsure what to do next?',
          primary: {
            id: 'q4-choice',
            type: 'single',
            title: 'Stuck or unsure?',
            options: [
              { value: 'yes', label: 'Yes (please explain)' },
              { value: 'no', label: 'No' },
            ],
          },
          followUp: {
            id: 'q4-detail',
            type: 'text',
            title: 'If yes, what happened?',
            placeholder: 'Tell us about the confusing moment…',
          },
        },
        {
          id: 'q5',
          type: 'scale',
          title: 'How fair did the scoring and payouts feel?',
          required: true,
          options: [
            { value: 1, label: '1️⃣ Very unfair' },
            { value: 2, label: '2️⃣ Somewhat unfair' },
            { value: 3, label: '3️⃣ Neutral' },
            { value: 4, label: '4️⃣ Fair' },
            { value: 5, label: '5️⃣ Very fair' },
          ],
        },
        {
          id: 'q6',
          type: 'single',
          title: 'Did you understand how Flipcoins (f) worked (entry costs, prizes, refunds)?',
          required: true,
          options: [
            { value: 'yes', label: 'Yes, completely' },
            { value: 'somewhat', label: 'Somewhat' },
            { value: 'no', label: 'No, unclear' },
          ],
        },
      ],
    },
    {
      id: 'section-design',
      title: '🎨 Section 2 — Interface & Design',
      questions: [
        {
          id: 'q7',
          type: 'scale',
          title: 'How smooth was the overall user experience (navigation, timing, responsiveness)?',
          required: true,
          options: [
            { value: 1, label: '1️⃣ Very frustrating' },
            { value: 2, label: '2️⃣ Needs improvement' },
            { value: 3, label: '3️⃣ Neutral' },
            { value: 4, label: '4️⃣ Smooth' },
            { value: 5, label: '5️⃣ Excellent' },
          ],
        },
        {
          id: 'q8',
          type: 'single',
          title: 'Were the timers, buttons, and feedback messages clear?',
          options: [
            { value: 'always', label: 'Always' },
            { value: 'usually', label: 'Usually' },
            { value: 'occasionally', label: 'Occasionally unclear' },
            { value: 'often', label: 'Often unclear' },
          ],
        },
        {
          id: 'q9',
          type: 'text',
          title: 'Did you encounter any bugs or glitches?',
          placeholder: 'Share reproduction steps or screenshots if you have them',
        },
        {
          id: 'q10',
          type: 'scale',
          title: 'How did you find the results screen (vote breakdown, payouts, clarity)?',
          required: true,
          options: [
            { value: 1, label: '1️⃣ Very confusing' },
            { value: 2, label: '2️⃣ Somewhat unclear' },
            { value: 3, label: '3️⃣ Neutral' },
            { value: 4, label: '4️⃣ Clear' },
            { value: 5, label: '5️⃣ Excellent' },
          ],
        },
      ],
    },
    {
      id: 'section-engagement',
      title: '⚙️ Section 3 — Engagement & Social Features',
      questions: [
        {
          id: 'q11',
          type: 'single',
          title: 'Would you recommend it to a friend?',
          required: true,
          options: [
            { value: 'yes', label: 'Yes' },
            { value: 'maybe', label: 'Maybe' },
            { value: 'no', label: 'No' },
          ],
        },
        {
          id: 'q12',
          type: 'multi',
          title: 'Which social features would you most like to see?',
          options: [
            { value: 'friends', label: 'Friend list / challenges' },
            { value: 'leaderboards', label: 'Leaderboards' },
            { value: 'achievements', label: 'Achievement sharing' },
            { value: 'comments', label: 'Commenting / reactions' },
            { value: 'other', label: 'Other (please describe)' },
          ],
        },
      ],
    },
    {
      id: 'section-final',
      title: '🧩 Section 4 — Final Thoughts',
      questions: [
        {
          id: 'q13',
          type: 'text',
          title: 'What was your favorite moment or feature?',
        },
        {
          id: 'q14',
          type: 'text',
          title: 'What was the most frustrating or confusing part?',
        },
        {
          id: 'q15',
          type: 'text',
          title: 'Any other feedback, suggestions, or ideas for future updates?',
        },
      ],
    },
  ],
};

type AnswerMap = Record<string, unknown>;

type CompoundValue = {
  choice: string | null;
  detail?: string;
};

const ensureCompoundValue = (value: unknown): CompoundValue => {
  if (value && typeof value === 'object') {
    const compound = value as CompoundValue;
    return {
      choice: compound.choice ?? null,
      detail: compound.detail ?? '',
    };
  }
  return { choice: null, detail: '' };
};

const hasAnswerValue = (value: unknown): boolean => {
  if (value === null || value === undefined) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'string') return value.trim().length > 0;
  if (typeof value === 'object') {
    const compound = value as CompoundValue;
    if (typeof compound.choice === 'string' && compound.choice.trim().length > 0) {
      return true;
    }
    return Object.values(compound).some((entry) => {
      if (typeof entry === 'string') {
        return entry.trim().length > 0;
      }
      return Boolean(entry);
    });
  }
  return true;
};

const BetaSurveyPage: React.FC = () => {
  const navigate = useNavigate();
  const { state } = useGame();
  const playerId = state.player?.player_id ?? '';
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (submitted) {
      const timer = window.setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [submitted, navigate]);

  const updateAnswer = (questionId: string, value: unknown) => {
    if (validationError) {
      setValidationError(null);
    }
    setAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  const toggleMultiAnswer = (questionId: string, option: string) => {
    if (validationError) {
      setValidationError(null);
    }
    setAnswers((prev) => {
      const existing = prev[questionId];
      const current = Array.isArray(existing)
        ? (existing as string[])
        : [];
      const next = current.includes(option)
        ? current.filter((item) => item !== option)
        : [...current, option];
      return {
        ...prev,
        [questionId]: next,
      };
    });
  };

  const handleCompoundPrimaryChange = (question: CompoundSurveyQuestion, value: string) => {
    if (validationError) {
      setValidationError(null);
    }
    setAnswers((prev) => {
      const existing = ensureCompoundValue(prev[question.id]);
      return {
        ...prev,
        [question.id]: {
          choice: value,
          detail: value === 'yes' ? existing.detail : '',
        },
      };
    });
  };

  const handleCompoundDetailChange = (question: CompoundSurveyQuestion, detail: string) => {
    if (validationError) {
      setValidationError(null);
    }
    setAnswers((prev) => {
      const existing = ensureCompoundValue(prev[question.id]);
      return {
        ...prev,
        [question.id]: {
          choice: existing.choice,
          detail,
        },
      };
    });
  };

  const validate = () => {
    const missing = betaSurveyDefinition.requiredQuestionIds.filter((questionId) => {
      const value = answers[questionId];
      return !hasAnswerValue(value);
    });

    if (missing.length > 0) {
      setValidationError('Please answer all required questions before submitting.');
      return false;
    }

    setValidationError(null);
    return true;
  };

  const prepareAnswerPayload = (question: SurveyQuestion): BetaSurveyAnswerPayload => {
    const storedValue = answers[question.id];
    switch (question.type) {
      case 'scale':
        return {
          question_id: question.id,
          value:
            typeof storedValue === 'number'
              ? storedValue
              : typeof storedValue === 'string'
              ? Number.parseInt(storedValue, 10) || null
              : null,
        };
      case 'multi':
        return {
          question_id: question.id,
          value: Array.isArray(storedValue) ? (storedValue as string[]) : [],
        };
      case 'text':
        return {
          question_id: question.id,
          value: typeof storedValue === 'string' ? storedValue : '',
        };
      case 'single':
        return {
          question_id: question.id,
          value: typeof storedValue === 'string' ? storedValue : null,
        };
      case 'compound':
        return {
          question_id: question.id,
          value: ensureCompoundValue(storedValue),
        };
      default: {
        const exhaustiveCheck: never = question;
        throw new Error(`Unhandled survey question type ${(exhaustiveCheck as { id?: string }).id ?? 'unknown'}`);
      }
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiError(null);

    if (!validate()) {
      return;
    }

    try {
      setSubmitting(true);
      const payload = betaSurveyDefinition.sections
        .flatMap((section) => section.questions)
        .map(prepareAnswerPayload);

      await apiClient.submitBetaSurvey({
        survey_id: betaSurveyDefinition.id,
        answers: payload,
      });

      if (playerId) {
        markSurveyCompleted(playerId);
      }

      setSubmitted(true);
    } catch (error) {
      setApiError(extractErrorMessage(error) || 'Something went wrong while submitting the survey.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8">
        <div className="tile-card p-6 md:p-10 max-w-4xl mx-auto">
          <header className="mb-8">
            <h1 className="text-3xl font-display font-bold text-quip-navy">
              {betaSurveyDefinition.title}
            </h1>
            <p className="mt-2 text-quip-teal text-base">
              {betaSurveyDefinition.description}
            </p>
            <p className="mt-1 text-sm text-quip-navy/70">
              Thank you for helping us shape the future of Quipflip!
            </p>
          </header>

          {submitted ? (
            <div className="rounded-tile border border-quip-teal bg-quip-teal/10 px-4 py-3 text-quip-navy">
              <p className="font-semibold">Thank you for your feedback!</p>
              <p className="text-sm">We&apos;re redirecting you back to the dashboard...</p>
            </div>
          ) : (
            <form className="space-y-10" onSubmit={handleSubmit}>
              {validationError && (
                <div className="rounded-tile border border-red-300 bg-red-50 px-4 py-3 text-red-700">
                  {validationError}
                </div>
              )}
              {apiError && (
                <div className="rounded-tile border border-red-300 bg-red-50 px-4 py-3 text-red-700">
                  {apiError}
                </div>
              )}

              {betaSurveyDefinition.sections.map((section) => (
                <section key={section.id} className="space-y-6">
                  <h2 className="text-2xl font-display font-semibold text-quip-navy">
                    {section.title}
                  </h2>

                  <div className="space-y-6">
                    {section.questions.map((question) => (
                      <div key={question.id} className="rounded-tile border border-quip-navy/10 bg-white p-4 shadow-tile-sm">
                        <div className="mb-3 flex flex-col gap-1">
                          <p className="text-lg font-semibold text-quip-navy">
                            {question.title}
                            {question.required && <span className="ml-2 text-sm font-normal text-red-500">*</span>}
                          </p>
                          {'description' in question && question.description ? (
                            <span className="text-sm text-quip-navy/70">{question.description}</span>
                          ) : null}
                        </div>

                        {question.type === 'scale' && (
                          <div className="grid gap-2 sm:grid-cols-5">
                            {question.options.map((option) => (
                              <label
                                key={option.value}
                                className={`flex cursor-pointer items-center gap-2 rounded-tile border px-3 py-2 text-sm transition hover:border-quip-teal ${
                                  answers[question.id] === option.value
                                    ? 'border-quip-teal bg-quip-teal/10 text-quip-navy'
                                    : 'border-quip-navy/20 text-quip-navy'
                                }`}
                              >
                                <input
                                  type="radio"
                                  name={question.id}
                                  value={option.value}
                                  className="text-quip-teal focus:ring-quip-teal"
                                  checked={answers[question.id] === option.value}
                                  onChange={() => updateAnswer(question.id, option.value)}
                                />
                                <span>{option.label}</span>
                              </label>
                            ))}
                          </div>
                        )}

                        {question.type === 'single' && (
                          <div className="space-y-2">
                            {question.options.map((option) => (
                              <label
                                key={option.value}
                                className="flex cursor-pointer items-center gap-3 rounded-tile border border-quip-navy/10 px-3 py-2 text-quip-navy transition hover:border-quip-teal"
                              >
                                <input
                                  type="radio"
                                  name={question.id}
                                  value={option.value}
                                  className="text-quip-teal focus:ring-quip-teal"
                                  checked={answers[question.id] === option.value}
                                  onChange={() => updateAnswer(question.id, option.value)}
                                />
                                <span>{option.label}</span>
                              </label>
                            ))}
                          </div>
                        )}

                        {question.type === 'multi' && (
                          <div className="space-y-2">
                            {question.options.map((option) => {
                              const selected = Array.isArray(answers[question.id])
                                ? (answers[question.id] as string[]).includes(option.value)
                                : false;
                              return (
                                <label
                                  key={option.value}
                                  className={`flex cursor-pointer items-center gap-3 rounded-tile border px-3 py-2 text-quip-navy transition hover:border-quip-teal ${
                                    selected ? 'border-quip-teal bg-quip-teal/10' : 'border-quip-navy/10'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    name={`${question.id}-${option.value}`}
                                    value={option.value}
                                    className="text-quip-teal focus:ring-quip-teal"
                                    checked={selected}
                                    onChange={() => toggleMultiAnswer(question.id, option.value)}
                                  />
                                  <span>{option.label}</span>
                                </label>
                              );
                            })}
                          </div>
                        )}

                        {question.type === 'text' && (
                          <textarea
                            name={question.id}
                            className="min-h-[96px] w-full rounded-tile border border-quip-navy/20 bg-white px-3 py-2 text-quip-navy shadow-inner focus:border-quip-teal focus:outline-none"
                            placeholder={question.placeholder}
                            value={typeof answers[question.id] === 'string' ? (answers[question.id] as string) : ''}
                            onChange={(event) => updateAnswer(question.id, event.target.value)}
                          />
                        )}

                        {question.type === 'compound' && (
                          <div className="space-y-3">
                            <div className="space-y-2">
                              {question.primary.options.map((option) => {
                                const value = ensureCompoundValue(answers[question.id]);
                                return (
                                  <label
                                    key={option.value}
                                    className="flex cursor-pointer items-center gap-3 rounded-tile border border-quip-navy/10 px-3 py-2 text-quip-navy transition hover:border-quip-teal"
                                  >
                                    <input
                                      type="radio"
                                      name={`${question.id}-primary`}
                                      value={option.value}
                                      className="text-quip-teal focus:ring-quip-teal"
                                      checked={value.choice === option.value}
                                      onChange={() => handleCompoundPrimaryChange(question, option.value)}
                                    />
                                    <span>{option.label}</span>
                                  </label>
                                );
                              })}
                            </div>

                            {ensureCompoundValue(answers[question.id]).choice === 'yes' && (
                              <textarea
                                name={`${question.id}-detail`}
                                className="min-h-[96px] w-full rounded-tile border border-quip-navy/20 bg-white px-3 py-2 text-quip-navy shadow-inner focus:border-quip-teal focus:outline-none"
                                placeholder={question.followUp.placeholder}
                                value={ensureCompoundValue(answers[question.id]).detail ?? ''}
                                onChange={(event) => handleCompoundDetailChange(question, event.target.value)}
                              />
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              ))}

              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => navigate(-1)}
                  className="rounded-tile border border-quip-navy/20 px-5 py-2 font-semibold text-quip-navy transition hover:border-quip-teal hover:text-quip-teal"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-tile bg-quip-navy px-6 py-2 font-semibold text-white shadow-tile-sm transition hover:bg-quip-teal disabled:cursor-not-allowed disabled:bg-quip-navy/70"
                >
                  {submitting ? 'Submitting…' : 'Submit feedback'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default BetaSurveyPage;
