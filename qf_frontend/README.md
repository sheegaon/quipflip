# Quipflip Frontend

React + TypeScript frontend for the Quipflip phrase association game.

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **React Router** - Navigation
- **Axios** - HTTP client
- **Tailwind CSS** - Styling
- **Context API** - State management

## Prerequisites

- Node.js 18+ and npm
- Backend API running at `http://localhost:8000` (or configured URL)

## Installation

```bash
# Install dependencies
npm install

# Create environment file (optional)
cp .env.example .env

# Edit .env if backend is not on localhost:8000
# VITE_API_URL=http://localhost:8000
```

## Development

```bash
# Start development server (with option to see on local network)
npm run dev -- --host

# The app will be available at http://localhost:5173 and on your local network
```

## Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client and TypeScript types
│   │   ├── client.ts     # Axios-based API client
│   │   └── types.ts      # TypeScript interfaces
│   ├── components/       # Reusable components
│   ├── config/           # Tutorial steps configuration
│   ├── contexts/         # React Context for state management
│   ├── hooks/            # Custom React hooks
│   ├── pages/            # Screen components
│   ├── App.tsx           # Main app component with routing
│   ├── main.tsx          # Entry point
│   └── index.css         # Global styles
├── public/               # Static assets
├── .env                  # Environment variables
└── package.json
```

## API Integration

The frontend connects to the backend API using the `apiClient` in `src/api/client.ts`.

### Environment Variables

- `VITE_API_URL` - Backend API URL (default: `http://localhost:8000`)
- `VITE_GOOGLE_CLIENT_ID` - Google OAuth client ID (for future use)

### Authentication

Players authenticate using email and password. Both access and refresh tokens are stored in **HTTP-only cookies** for maximum security:
- **Access tokens** (2-hour lifetime): Automatically sent with all API requests
- **Refresh tokens** (30-day lifetime): Used for automatic token rotation
- **Security benefits**: Tokens inaccessible to JavaScript, protected from XSS attacks
- **Session persistence**: Users remain logged in across browser refreshes and sessions

The backend automatically handles token validation and refresh using cookies - no manual token management needed in the frontend.

Each player has a visible username and a hidden pseudonym (randomly auto-generated during registration). Other players see only the hidden pseudonym in game results.

### State Management

The `GameContext` manages global state:
- Authentication status (JWT tokens)
- Player balance and info
- Active round state
- Pending results
- Phraseset summary
- Unclaimed results
- Round availability

### Polling Strategy

- Balance & round availability: Every 60 seconds
- Pending results, phraseset summary, unclaimed results: Every 90 seconds
- All data fetched on initial authentication

## User Flow

1. **Landing Page** - Create account with email & password (username generated automatically) or login with email & password
2. **Dashboard** - View balance, claim bonus, select round type, access phraseset tracking
3. **Round Screens** - Complete prompt/copy/vote rounds with timers and feedback
4. **Results** - View finalized phrasesets with pseudonym display, vote breakdown and collect payouts
5. **Tracking** - View all your phrasesets organized by role (prompt/copy/vote) and status

## Key Components

### Timer Component
- Real-time countdown from server `expires_at` timestamp
- Visual states: normal (blue) → warning (yellow) → urgent (red/pulsing)
- Automatically disables submission when expired

### GameContext
- Centralized state management
- Automatic polling for updates
- Error handling and notifications
- Session token persistence

### Round Pages
- **PromptRound** - Submit a phrase for a creative prompt with like/dislike feedback
- **ImpostorRound** - Submit a similar phrase without seeing the prompt
- **VoteRound** - Identify the original phrase from three options
- **Results** - View vote breakdown and collect payouts
- **PhrasesetTracking** - Browse all phrasesets by role and status with filtering

## Error Handling

- API errors are transformed to user-friendly messages
- Error notifications auto-dismiss after 5 seconds
- Invalid/expired tokens trigger automatic logout
- 401 errors automatically trigger token refresh before retrying request
- Network errors prompt retry suggestions
- **Request cancellation:** AbortController integration prevents memory leaks and React warnings

## Styling

Uses Tailwind CSS utility classes for:
- Responsive layouts (mobile-first)
- Color-coded round types
- Interactive button states
- Gradient backgrounds
- Loading states

## Troubleshooting

### Backend not connecting
- Ensure backend is running at the configured `VITE_API_URL`
- Check browser console for CORS errors
- Ensure cookies are enabled in your browser (required for authentication)
- Check browser DevTools > Application > Cookies for `quipflip_access_token` and `quipflip_refresh_token`

### Timer not working
- Ensure system clock is accurate
- Check `expires_at` timestamp in browser devtools
- Backend and frontend should use UTC time

### Polling issues
- Check browser console for API errors
- Verify network connectivity
- Check that authentication cookies are present and valid (DevTools > Application > Cookies)
- Clear cookies and log in again if experiencing persistent 401 errors

## Development Tips

- Use React DevTools to inspect component state
- Use Network tab to monitor API calls
- Check Context state in GameContext
- Timer updates every 1 second automatically

## Production Deployment

For production deployment:

1. Update `VITE_API_URL` to production backend URL
2. Build the app: `npm run build`
3. Deploy `dist/` folder to static hosting (Vercel, Netlify, etc.)
4. Ensure HTTPS for JWT token security
5. Configure backend CORS for your frontend domain with credentials support
6. Ensure cookie SameSite and Secure settings are properly configured for production