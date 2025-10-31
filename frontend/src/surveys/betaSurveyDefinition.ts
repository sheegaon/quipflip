import { BETA_SURVEY_ID } from '../utils/betaSurvey';
import type { SurveyDefinition } from '../types/survey';

export const betaSurveyDefinition: SurveyDefinition = {
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
