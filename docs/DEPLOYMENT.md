# Deployment Guide

This guide covers the production deployment setup for the multi-game QuipFlip backend and both frontends (all housed in this repository), including environment variables and configuration for Vercel and Heroku.

## Architecture Overview

- **Backend (multi-game)**: Single FastAPI service on Heroku (`https://quipflip-c196034288cd.herokuapp.com`) hosting both Quipflip (`/qf/*`) and Initial Reaction (`/ir/*`) APIs.
- **Frontends**: Two Vercel projects in this repo
  - `qf_frontend` → Quipflip web client
  - `ir_frontend` → Initial Reaction web client
- **API proxy**: Vercel rewrites `/api/*` to the shared backend for same-origin REST calls
  - HttpOnly cookies work seamlessly
  - Maximum iOS Safari compatibility
- **WebSocket**: Token exchange pattern (Vercel doesn't support WebSocket proxying)
  - Step 1: Fetch short-lived token via REST (through Vercel proxy)
  - Step 2: Use token for direct WebSocket connection to Heroku
  - Token expires in 60 seconds for security
- **Cookies**: SameSite=Lax with Secure flag (same-origin for REST)
- **Benefits**:
  - REST API maintains iOS Safari compatibility
  - WebSocket gets real-time connection without proxy limitations
  - HttpOnly cookies protect long-lived tokens
  - Short-lived WebSocket tokens limit exposure risk

## Backend Configuration (Heroku)

### Required Environment Variables

Set these in the Heroku dashboard or via `heroku config:set`:

```bash
# Application Environment
ENVIRONMENT=production

# Security (CRITICAL - must be changed from default)
SECRET_KEY=<your-strong-random-secret-key>

# Database (automatically provided by Heroku Postgres addon)
DATABASE_URL=<postgres-connection-string>

# Redis (automatically provided by Heroku Redis addon)
REDIS_URL=<redis-connection-string>

# Frontend URL (for CORS)
FRONTEND_URL=https://quipflip.xyz

# Optional: Custom allowed origins (comma-separated)
# ALLOWED_ORIGINS=https://quipflip.xyz,https://www.quipflip.xyz

# API Keys (for AI features)
OPENAI_API_KEY=<your-openai-api-key>
GEMINI_API_KEY=<your-gemini-api-key>
AI_PROVIDER=openai  # or "gemini"

# Phrase Validator Service
PHRASE_VALIDATOR_URL=https://quipflip-pvw-f508f6eb7783.herokuapp.com
USE_PHRASE_VALIDATOR_API=true
```

### Cookie Configuration

The backend automatically configures cookies based on the `ENVIRONMENT` variable:

- **Production** (`ENVIRONMENT=production`):
  - `SameSite=Lax` (all traffic same-origin via Vercel proxy)
  - `Secure=True` (HTTPS required)
  - `HttpOnly=True` (prevents JavaScript access)
  - **Note**: HttpOnly cookies automatically sent by browser for same-origin requests

- **Development** (`ENVIRONMENT=development`):
  - `SameSite=Lax` (localhost same-site)
  - `Secure=False` (HTTP allowed for localhost)
  - `HttpOnly=True`

### CORS Configuration

The backend allows the following origins:
- Value of `FRONTEND_URL` environment variable
- `http://localhost:5173` (for local development)
- Any additional origins in `ALLOWED_ORIGINS` (comma-separated)

CORS is configured with:
- `allow_credentials=True` (required for cookies)
- `allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]`
- `allow_headers=["*"]`

## Frontend Configuration (Vercel)

### Shared proxy setup

Both Vercel projects (`qf_frontend` and `ir_frontend`) ship with a `vercel.json` that rewrites `/api/:path*` to the Heroku backend. This keeps REST requests same-origin so HttpOnly cookies work across both games.

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://quipflip-c196034288cd.herokuapp.com/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/"
    }
  ]
}
```

### Quipflip frontend (`qf_frontend`)

- **Environment variable**: `VITE_API_URL=/api` → client appends `/qf` automatically (requests land at `/api/qf/*`).
- **Build settings** (Vercel):
  - Framework Preset: Vite
  - Build Command: `npm run build`
  - Output Directory: `dist`
  - Install Command: `npm install`
- **WebSocket**: Uses REST token exchange then connects directly to `wss://quipflip-c196034288cd.herokuapp.com/qf/users/online/ws?token=...`.

### Initial Reaction frontend (`ir_frontend`)

- **Environment variable**: `VITE_API_URL=/api/ir` (includes game prefix so axios base URL resolves to `/api/ir/*`).
- **Build settings** (Vercel):
  - Framework Preset: Vite
  - Build Command: `npm run build`
  - Output Directory: `dist`
  - Install Command: `npm install`
- **WebSocket**: Not currently required for gameplay; REST uses same proxy and HttpOnly cookies.

## WebSocket Setup

### Online Users Feature (Quipflip)

The Quipflip Online Users page demonstrates real-time WebSocket functionality with token exchange:

1. **Token Exchange Flow**:
   - Frontend calls `GET /api/qf/auth/ws-token` (REST via Vercel proxy)
   - HttpOnly cookie automatically validated
   - Backend returns short-lived token (60 seconds)
   - Frontend uses token for WebSocket connection

2. **WebSocket Connection**:
   - URL: `wss://quipflip-c196034288cd.herokuapp.com/qf/users/online/ws?token=<short_token>`
   - Direct connection to Heroku (bypasses Vercel)
   - Token passed as query parameter
   - Server validates token from query parameter

3. **Authentication**:
   - Server validates short-lived token
   - Rejects with WebSocket code 1008 (policy violation) if auth fails
   - Client detects 1008 and shows "Authentication failed" message
   - Token expiration after 60 seconds closes WebSocket gracefully

4. **Broadcasting**:
   - Server sends `online_users_update` messages every 5 seconds
   - Message includes user list, count, and timestamp
   - Broadcast only runs when at least one client is connected

5. **Fallback Mechanism**:
   - If WebSocket fails, client falls back to HTTP polling
   - Polls `GET /api/qf/users/online` every 10 seconds
   - Seamless transition between WebSocket and polling

### Acceptance Criteria

✓ Open two browsers → both show identical online user lists
✓ Updates appear within ≤5 seconds
✓ Invalid/expired tokens rejected with WebSocket code 1008
✓ If WebSocket unavailable, polling takes over automatically

## Deployment Checklist

### Backend (Heroku)

- [ ] Set `ENVIRONMENT=production`
- [ ] Set unique `SECRET_KEY` (not the default value)
- [ ] Configure `DATABASE_URL` (via Heroku Postgres addon)
- [ ] Configure `REDIS_URL` (via Heroku Redis addon, optional)
- [ ] Set `FRONTEND_URL` to the primary production host and include both Vercel frontends in `ALLOWED_ORIGINS`
- [ ] Add API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`)
- [ ] Verify CORS covers both frontend domains
- [ ] Test WebSocket endpoint: `wss://quipflip-c196034288cd.herokuapp.com/users/online/ws`

### Quipflip frontend (Vercel)

- [ ] Set `VITE_API_URL=/api` (proxied through Vercel and auto-appended with `/qf`)
- [ ] Verify `vercel.json` has API proxy rewrite rule
- [ ] Deploy and verify build succeeds
- [ ] Test REST API calls go through Vercel proxy
- [ ] Test WebSocket connection to `/users/online/ws`
- [ ] Verify cookies are set and sent with requests
- [ ] Test in multiple browsers (Chrome, Safari, Firefox)
- [ ] Test on iOS Safari (common cookie issue)

### Initial Reaction frontend (Vercel)

- [ ] Set `VITE_API_URL=/api/ir` (proxied through Vercel with IR prefix)
- [ ] Verify `vercel.json` has API proxy rewrite rule
- [ ] Deploy and verify build succeeds
- [ ] Test REST API calls go through Vercel proxy
- [ ] Verify cookies are set and sent with requests
- [ ] Test in multiple browsers (Chrome, Safari, Firefox)

## Testing

### Manual Testing

1. **Cookie Authentication (Quipflip routes)**:
   ```bash
   # Login and verify cookies are set
   curl -X POST https://quipflip-c196034288cd.herokuapp.com/qf/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"test","password":"test"}' \
     -c cookies.txt -v

   # Verify cookies work on subsequent requests
   curl https://quipflip-c196034288cd.herokuapp.com/qf/player/me \
     -b cookies.txt
   ```

2. **WebSocket Connection (Quipflip Online Users)**:
   ```javascript
   // Test in browser console on https://quipflip.xyz
   const token = document.cookie.split('; ')
     .find(row => row.startsWith('quipflip_access_token='))
     .split('=')[1];

   const ws = new WebSocket(
     `wss://quipflip-c196034288cd.herokuapp.com/qf/users/online/ws?token=${token}`
   );

   ws.onopen = () => console.log('Connected!');
   ws.onmessage = (e) => console.log('Message:', JSON.parse(e.data));
   ws.onerror = (e) => console.error('Error:', e);
   ```

3. **Cross-Site Cookies**:
   - Open browser DevTools → Application/Storage → Cookies
   - Verify `quipflip_access_token` has:
     - `SameSite: None`
     - `Secure: true`
     - `HttpOnly: true`

### Automated Testing

```bash
# Backend tests
pytest

# Quipflip frontend build test
cd qf_frontend
npm run build
npm run preview

# Initial Reaction frontend build test
cd ../ir_frontend
npm run build
npm run preview
```

## Troubleshooting

### Issue: Cookies not being set

**Solution**: Verify:
1. `ENVIRONMENT=production` is set on Heroku
2. Frontend is accessed via HTTPS (match the deployed domain)
3. Backend CORS allows each deployed frontend host

### Issue: WebSocket connection fails

**Solution**: Check:
1. Browser console for connection errors
2. WebSocket URL is using `wss://` (not `ws://`)
3. Access token is valid and not expired
4. Backend logs for authentication errors

### Issue: "Authentication failed" on WebSocket

**Solution**:
1. Verify cookies are being sent with requests
2. Check token expiration (access tokens last 2 hours)
3. Try refreshing the page to get a new token
4. Check browser console for WebSocket close code (should be 1008)

### Issue: Updates not appearing in real-time

**Solution**:
1. Check "Live" indicator on Online Users page (should be green)
2. If red, check browser console for WebSocket errors
3. Verify fallback polling is working (updates every 10s)
4. Check backend logs for broadcast task errors

## Monitoring

### Backend Health

```bash
# Check if app is running
curl https://quipflip-c196034288cd.herokuapp.com/health

# View logs
heroku logs --tail --app quipflip-c196034288cd
```

### Frontend Build Status

- Check each Vercel project (`qf_frontend`, `ir_frontend`) for deployment status
- View deployment logs for build errors
- Test Quipflip at https://quipflip.xyz and Initial Reaction at its Vercel deployment URL

### WebSocket Metrics

Monitor in backend logs:
- Connection count (logged when clients connect/disconnect)
- Broadcast task status (logs every 5 seconds when active)
- Authentication failures (logged with 1008 close code)

## Security Considerations

1. **Secret Key**: Must be changed from default in production
2. **HTTPS Required**: SameSite=None cookies require Secure flag
3. **Token Expiration**: Access tokens expire after 2 hours
4. **HttpOnly Cookies**: Prevents XSS attacks from stealing tokens
5. **CORS Configuration**: Only allows specific origins
6. **WebSocket Auth**: Validates tokens before accepting connections

## References

- [Heroku Deployment](https://devcenter.heroku.com/articles/getting-started-with-python)
- [Vercel Deployment](https://vercel.com/docs/deployments/overview)
- [MDN: SameSite Cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite)
- [WebSocket Protocol](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
