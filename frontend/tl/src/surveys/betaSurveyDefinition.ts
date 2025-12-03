import { BETA_SURVEY_ID } from '@crowdcraft/utils/betaSurvey.ts';
import type { SurveyDefinition } from '@crowdcraft/types/survey.ts';

export const betaSurveyDefinition: SurveyDefinition = {
  id: BETA_SURVEY_ID,
  title: 'ThinkLink Beta Tester Survey',
  description: 'Help us polish ThinkLink before launch by sharing your beta impressions.',
  requiredQuestionIds: ['q1', 'q2', 'q4', 'q5', 'q6', 'q11'],
  sections: [
    {
      id: 'section-fun',
      title: '💬 Section 1 — Fun & Replayability',
      questions: [
        {
          id: 'q1',
          type: 'scale',
          title: 'Overall, how enjoyable was ThinkLink?',
          required: true,
          options: [
            { value: 1, label: '1️⃣ Not fun at all' },
            { value: 2, label: '2️⃣ A bit dull' },
            { value: 3, label: '3️⃣ Decent' },
            { value: 4, label: '4️⃣ Fun' },
            { value: 5, label: '5️⃣ Super fun' },
          ],
        },
        {
          id: 'q2',
          type: 'single',
          title: 'Would you play again soon?',
          required: true,
          options: [
            { value: 'yes', label: 'Yes' },
            { value: 'maybe', label: 'Maybe' },
            { value: 'no', label: 'No' },
          ],
        },
        {
          id: 'q3',
          type: 'scale',
          title: 'How enjoyable was it to answer prompts compared to seeing how others answered prompts?',
          options: [
            { value: 1, label: '1️⃣ Much less enjoyable' },
            { value: 2, label: '2️⃣ Slightly less enjoyable' },
            { value: 3, label: '3️⃣ About the same' },
            { value: 4, label: '4️⃣ Slightly more enjoyable' },
            { value: 5, label: '5️⃣ Much more enjoyable' },
          ],
        },
      ],
    },
    {
      id: 'section-clarity',
      title: '🧭 Section 2 — Clarity of Rules',
      questions: [
        {
          id: 'q4',
          type: 'scale',
          title: 'How clear were the rules for writing phrases?',
          required: true,
          options: [
            { value: 1, label: '1️⃣ Very confusing' },
            { value: 2, label: '2️⃣ Somewhat unclear' },
            { value: 3, label: '3️⃣ Neutral' },
            { value: 4, label: '4️⃣ Clear' },
            { value: 5, label: '5️⃣ Crystal clear' },
          ],
        },
        {
          id: 'q5',
          type: 'scale',
          title: 'How clear was what you were supposed to do in Challenge Mode?',
          required: true,
          options: [
            { value: 1, label: '1️⃣ Very confusing' },
            { value: 2, label: '2️⃣ Somewhat unclear' },
            { value: 3, label: '3️⃣ Neutral' },
            { value: 4, label: '4️⃣ Clear' },
            { value: 5, label: '5️⃣ Instantly clear' },
          ],
        },
      ],
    },
    {
      id: 'section-economy',
      title: '💰 Section 3 — Difficulty & Economy',
      questions: [
        {
          id: 'q6',
          type: 'scale',
          title: 'How fair did the linkcoin costs and payouts feel?',
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
          id: 'q7',
          type: 'single',
          title: 'Did you run out of linkcoins or feel pressured by entry costs?',
          options: [
            { value: 'never', label: 'Never' },
            { value: 'sometimes', label: 'Sometimes' },
            { value: 'often', label: 'Often' },
          ],
        },
      ],
    },
    {
      id: 'section-ui',
      title: '🎨 Section 4 — UI & UX',
      questions: [
        {
          id: 'q8',
          type: 'scale',
          title: 'Were the timers, buttons, and feedback easy to see and use?',
          options: [
            { value: 1, label: '1️⃣ Very unclear' },
            { value: 2, label: '2️⃣ Needs work' },
            { value: 3, label: '3️⃣ Neutral' },
            { value: 4, label: '4️⃣ Clear' },
            { value: 5, label: '5️⃣ Perfectly clear' },
          ],
        },
        {
          id: 'q9',
          type: 'single',
          title: 'How usable was the game on your device (including mobile if you tried it)?',
          options: [
            { value: 'great', label: 'Great' },
            { value: 'okay', label: 'Okay but could improve' },
            { value: 'difficult', label: 'Difficult to use' },
          ],
        },
      ],
    },
    {
      id: 'section-final',
      title: '🧩 Section 5 — Final Thoughts',
      questions: [
        {
          id: 'q10',
          type: 'text',
          title: 'What was the best part of ThinkLink for you?',
        },
        {
          id: 'q11',
          type: 'text',
          title: 'What was the most confusing or frustrating part?',
          required: true,
        },
        {
          id: 'q12',
          type: 'text',
          title: 'Anything else we should know?',
        },
      ],
    },
  ],
};
