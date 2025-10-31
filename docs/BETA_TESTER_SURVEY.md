Here’s the trimmed survey, then I’ll show you the steps + a Codex-style prompt.

## Quipflip Beta Tester Survey (In-App)

### 💬 Section 1 — Gameplay Experience

1. How intuitive did you find the **Prompt → Copy → Vote** flow?

   * 1️⃣ Very confusing
   * 2️⃣ Somewhat confusing
   * 3️⃣ Neutral
   * 4️⃣ Easy to follow
   * 5️⃣ Instantly clear

2. Which phase did you enjoy most?

   * [ ] Prompt
   * [ ] Copy
   * [ ] Vote
   * [ ] Viewing results

3. What felt least clear or engaging about any phase?
   *Open-ended*

4. Did you ever feel “stuck” or unsure what to do next?

   * [ ] Yes (please explain)
   * [ ] No

5. How fair did the scoring and payouts feel?

   * 1️⃣ Very unfair
   * 2️⃣ Somewhat unfair
   * 3️⃣ Neutral
   * 4️⃣ Fair
   * 5️⃣ Very fair

6. Did you understand how **Flipcoins (f)** worked (entry costs, prizes, refunds)?

   * [ ] Yes, completely
   * [ ] Somewhat
   * [ ] No, unclear

### 🎨 Section 2 — Interface & Design

7. How smooth was the overall user experience (navigation, timing, responsiveness)?

   * 1️⃣ Very frustrating
   * 2️⃣ Needs improvement
   * 3️⃣ Neutral
   * 4️⃣ Smooth
   * 5️⃣ Excellent

8. Were the timers, buttons, and feedback messages clear?

   * [ ] Always
   * [ ] Usually
   * [ ] Occasionally unclear
   * [ ] Often unclear

9. Did you encounter any bugs or glitches?
   *Open-ended*

10. How did you find the **results screen** (vote breakdown, payouts, clarity)?

    * 1️⃣ Very confusing
    * 2️⃣ Somewhat unclear
    * 3️⃣ Neutral
    * 4️⃣ Clear
    * 5️⃣ Excellent

### ⚙️ Section 3 — Engagement & Social Features

11. Would you recommend it to a friend?

    * [ ] Yes
    * [ ] Maybe
    * [ ] No

12. Which social features would you most like to see?

    * [ ] Friend list / challenges
    * [ ] Leaderboards
    * [ ] Achievement sharing
    * [ ] Commenting / reactions
    * [ ] Other (please describe)

### 🧩 Section 4 — Final Thoughts

13. What was your favorite moment or feature?
    *Open-ended*

14. What was the most frustrating or confusing part?
    *Open-ended*

15. Any other feedback, suggestions, or ideas for future updates?
    *Open-ended*

---

## Steps to add this as an **in-app survey** (for your current React + FastAPI stack)

1. **Define the survey schema on the frontend**

   * Create a TS type like `Survey`, `SurveyQuestion`, `SurveyAnswer`.
   * Hardcode this one survey (you don’t need a CMS yet).

2. **Render the survey in a dedicated page/modal**

   * Easiest: add a route like `/survey/beta` and a CTA (“Tell us what you think”) in the dashboard.
   * Or: show it once per user after they complete N rounds (you already have `/player/dashboard` and phraseset summaries — you can gate off that).

3. **Collect answers locally in component state**

   * For multiple choice: store value as string / array.
   * For open-ended: store text.
   * Include metadata: player_id, username, app version, timestamp.

4. **POST to a new backend endpoint**

   * Add e.g. `POST /feedback/beta-survey` to FastAPI.
   * Body: `{ survey_id: "beta_oct_2025", player_id, answers: [...] }`.
   * Store as JSON in a `feedback` table or even a generic `survey_responses` table (id, player_id, survey_id, payload JSONB, created_at).

5. **Return 200 and hide survey**

   * On success, set `has_completed_beta_survey=true` in player profile (or separate table) so you don’t re-prompt.

6. **Add an admin view later**

   * Simple React page that calls `GET /feedback/beta-survey` and lists responses.

---

## Prompt to feed to Codex

You can drop this into your AI coding assistant to get a React component + FastAPI endpoint scaffold.

````text
You are helping me implement an in-app beta tester survey for my game Quipflip.

Context:
- Frontend: React + TypeScript + Vite, already using React Router and Context for auth/game state.
- Backend: FastAPI with JWT auth. We already have routers like /player, /rounds, /phrasesets.
- I want to add ONE hardcoded survey called "beta_oct_2025".
- Authenticated players only. We know the player_id from the JWT on the backend and from context on the frontend.

Tasks:

1. FRONTEND (React + TS)
- Create a React component called `BetaSurveyPage`.
- Render the questions listed above.
- Store answers in component state.
- On submit, POST to `/feedback/beta-survey` with JSON:
  {
    survey_id: "beta_oct_2025",
    answers: [
      { question_id: "q1", value: 4 },
      { question_id: "q2", value: "Vote" },
      ...
    ]
  }
- If the request succeeds, show a thank-you message and navigate back to dashboard.
- Add basic validation: required for Q1, Q2, Q5, Q6, Q7, Q10, Q11.

2. BACKEND (FastAPI)
- Add a new router module, e.g. `routers/feedback.py`.
- Create endpoint: POST `/feedback/beta-survey`
  - Requires auth (reuse existing dependency).
  - Request model:
    ```python
    class SurveyAnswer(BaseModel):
        question_id: str
        value: Any

    class SurveySubmission(BaseModel):
        survey_id: str
        answers: list[SurveyAnswer]
    ```
  - On request, read current_user / player_id from the dependency.
  - Insert into a table `survey_responses` with columns:
    - id (uuid)
    - player_id (uuid)
    - survey_id (text)
    - payload (JSONB)
    - created_at (timestamp, utc)
  - If the player has already submitted for `beta_oct_2025`, just return 200 with a message like "already submitted".
- Add a GET `/feedback/beta-survey` (admin only, can stub auth) that returns the last 100 submissions.

3. DATABASE
- Generate SQLAlchemy model for `survey_responses`.
- Generate an Alembic migration to create the table.

4. STYLE
- Use the existing Tailwind setup in the project for inputs and buttons. Form should be mobile-friendly.

Output:
- React component code (BetaSurveyPage.tsx)
- FastAPI router code (feedback.py)
- SQLAlchemy model + Alembic migration snippet
- Example JSON payload from the frontend
- Any necessary additions to `main.py` to include the new router
````

That should be enough for Codex/Cursor/Copilot to spit out the actual code that matches your existing project shape.
