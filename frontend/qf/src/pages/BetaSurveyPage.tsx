import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '@/api/client';
import { Header } from '../components/Header';
import { useGame } from '../contexts/GameContext';
import type { SurveyQuestion, CompoundSurveyQuestion } from '@crowdcraft/types/survey.ts';
import { markSurveyCompleted } from '@crowdcraft/utils/betaSurvey.ts';
import { betaSurveyDefinition } from '../surveys/betaSurveyDefinition';
import type { QFBetaSurveyAnswerPayload } from '@crowdcraft/api/types.ts';

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

  const prepareAnswerPayload = (question: SurveyQuestion): QFBetaSurveyAnswerPayload => {
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
    <div className="min-h-screen bg-ccl-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8">
        <div className="tile-card p-6 md:p-10 max-w-4xl mx-auto">
          <header className="mb-8">
            <h1 className="text-3xl font-display font-bold text-ccl-navy">
              {betaSurveyDefinition.title}
            </h1>
            <p className="mt-2 text-ccl-teal text-base">
              {betaSurveyDefinition.description}
            </p>
            <p className="mt-1 text-sm text-ccl-navy/70">
              Thank you for helping us shape the future of Quipflip!
            </p>
          </header>

          {submitted ? (
            <div className="rounded-tile border border-ccl-teal bg-ccl-teal/10 px-4 py-3 text-ccl-navy">
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
                  <h2 className="text-2xl font-display font-semibold text-ccl-navy">
                    {section.title}
                  </h2>

                  <div className="space-y-6">
                    {section.questions.map((question) => (
                      <div key={question.id} className="rounded-tile border border-ccl-navy/10 bg-white p-4 shadow-tile-sm">
                        <div className="mb-3 flex flex-col gap-1">
                          <p className="text-lg font-semibold text-ccl-navy">
                            {question.title}
                            {question.required && <span className="ml-2 text-sm font-normal text-red-500">*</span>}
                          </p>
                          {'description' in question && question.description ? (
                            <span className="text-sm text-ccl-navy/70">{question.description}</span>
                          ) : null}
                        </div>

                        {question.type === 'scale' && (
                          <div className="grid gap-2 sm:grid-cols-5">
                            {question.options.map((option) => (
                              <label
                                key={option.value}
                                className={`flex cursor-pointer items-center gap-2 rounded-tile border px-3 py-2 text-sm transition hover:border-ccl-teal ${
                                  answers[question.id] === option.value
                                    ? 'border-ccl-teal bg-ccl-teal/10 text-ccl-navy'
                                    : 'border-ccl-navy/20 text-ccl-navy'
                                }`}
                              >
                                <input
                                  type="radio"
                                  name={question.id}
                                  value={option.value}
                                  className="text-ccl-teal focus:ring-ccl-teal"
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
                                className="flex cursor-pointer items-center gap-3 rounded-tile border border-ccl-navy/10 px-3 py-2 text-ccl-navy transition hover:border-ccl-teal"
                              >
                                <input
                                  type="radio"
                                  name={question.id}
                                  value={option.value}
                                  className="text-ccl-teal focus:ring-ccl-teal"
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
                                  className={`flex cursor-pointer items-center gap-3 rounded-tile border px-3 py-2 text-ccl-navy transition hover:border-ccl-teal ${
                                    selected ? 'border-ccl-teal bg-ccl-teal/10' : 'border-ccl-navy/10'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    name={`${question.id}-${option.value}`}
                                    value={option.value}
                                    className="text-ccl-teal focus:ring-ccl-teal"
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
                            className="min-h-[96px] w-full rounded-tile border border-ccl-navy/20 bg-white px-3 py-2 text-ccl-navy shadow-inner focus:border-ccl-teal focus:outline-none"
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
                                    className="flex cursor-pointer items-center gap-3 rounded-tile border border-ccl-navy/10 px-3 py-2 text-ccl-navy transition hover:border-ccl-teal"
                                  >
                                    <input
                                      type="radio"
                                      name={`${question.id}-primary`}
                                      value={option.value}
                                      className="text-ccl-teal focus:ring-ccl-teal"
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
                                className="min-h-[96px] w-full rounded-tile border border-ccl-navy/20 bg-white px-3 py-2 text-ccl-navy shadow-inner focus:border-ccl-teal focus:outline-none"
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
                  className="rounded-tile border border-ccl-navy/20 px-5 py-2 font-semibold text-ccl-navy transition hover:border-ccl-teal hover:text-ccl-teal"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="rounded-tile bg-ccl-navy px-6 py-2 font-semibold text-white shadow-tile-sm transition hover:bg-ccl-teal disabled:cursor-not-allowed disabled:bg-ccl-navy/70"
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
