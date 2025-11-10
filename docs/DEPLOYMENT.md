# Deployment Guide

This guide covers the production deployment setup for QuipFlip, including environment variables and configuration for both frontend (Vercel) and backend (Heroku).

## Architecture Overview

- **Frontend**: Hosted on Vercel at `quipflip.xyz`
- **Backend**: Hosted on Heroku at `quipflip-c196034288cd.herokuapp.com`
- **Hybrid Approach**:
  - **REST API**: Proxied through Vercel (`/api/*` → Heroku) for same-origin requests, iOS compatibility
  - **WebSocket**: Direct connection to Heroku (`wss://quipflip-c196034288cd.herokuapp.com`)
- **Cookies**: SameSite=None with Secure flag (required for cross-site WebSocket authentication)
- **Benefits**:
  - REST API maintains iOS Safari cookie compatibility via same-origin proxy
  - WebSocket gets real-time connection directly to backend
  - Single cookie configuration works for both

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
  - `SameSite=None` (required for cross-site WebSocket connections)
  - `Secure=True` (required for SameSite=None)
  - `HttpOnly=True` (prevents JavaScript access)
  - **Note**: REST API uses Vercel proxy (same-origin), but WebSocket needs cross-site cookies

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

### Environment Variables

Set these in the Vercel dashboard under Project Settings → Environment Variables:

```bash
# REST API URL (proxied through Vercel for same-origin requests)
VITE_API_URL=/api

# WebSocket URL (direct connection to Heroku backend)
VITE_WEBSOCKET_URL=wss://quipflip-c196034288cd.herokuapp.com
```

### Vercel Configuration

Ensure `vercel.json` includes the rewrite rule for the API proxy:

```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://quipflip-c196034288cd.herokuapp.com/:path*"
    }
  ]
}
```

### Build Settings

- **Framework Preset**: Vite
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Install Command**: `npm install`

### Important Notes

1. **Hybrid Connection Strategy**:
   - **REST API**: Uses `/api` which Vercel proxies to Heroku (same-origin from browser perspective)
   - **WebSocket**: Connects directly to `wss://quipflip-c196034288cd.herokuapp.com` (cross-site)
   - Benefits: iOS Safari compatibility for REST + real-time WebSocket support

2. **Cookie Handling**:
   - REST API: Cookies sent automatically as same-origin (via Vercel proxy)
   - WebSocket: Cookies sent as cross-site with SameSite=None (requires Secure flag)
   - WebSocket also includes token as query parameter for compatibility

3. **WebSocket URL Construction**:
   - Production: Uses `VITE_WEBSOCKET_URL` directly
   - Development: Constructs from `VITE_API_URL` or defaults to `localhost:8000`
   - Token automatically appended from cookies

## WebSocket Setup

### Online Users Feature

The Online Users page demonstrates real-time WebSocket functionality:

1. **Client Connection**:
   - URL: `wss://quipflip-c196034288cd.herokuapp.com/users/online/ws?token=<access_token>`
   - Token is read from `quipflip_access_token` cookie
   - Token is also sent in cookies for fallback

2. **Authentication**:
   - Server validates token from query parameter or cookie
   - Rejects with WebSocket code 1008 (policy violation) if auth fails
   - Client detects 1008 and shows "Authentication failed" message

3. **Broadcasting**:
   - Server sends `online_users_update` messages every 5 seconds
   - Message includes user list, count, and timestamp
   - Broadcast only runs when at least one client is connected

4. **Fallback Mechanism**:
   - If WebSocket fails, client falls back to HTTP polling
   - Polls `GET /api/users/online` every 10 seconds
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
- [ ] Set `FRONTEND_URL=https://quipflip.xyz`
- [ ] Add API keys (`OPENAI_API_KEY`, `GEMINI_API_KEY`)
- [ ] Verify CORS allows `https://quipflip.xyz`
- [ ] Test WebSocket endpoint: `wss://quipflip-c196034288cd.herokuapp.com/users/online/ws`

### Frontend (Vercel)

- [ ] Set `VITE_API_URL=/api` (proxied through Vercel)
- [ ] Set `VITE_WEBSOCKET_URL=wss://quipflip-c196034288cd.herokuapp.com`
- [ ] Verify `vercel.json` has API proxy rewrite rule
- [ ] Deploy and verify build succeeds
- [ ] Test REST API calls go through Vercel proxy
- [ ] Test WebSocket connection to `/users/online/ws`
- [ ] Verify cookies are set and sent with requests
- [ ] Test in multiple browsers (Chrome, Safari, Firefox)
- [ ] Test on iOS Safari (common cookie issue)

## Testing

### Manual Testing

1. **Cookie Authentication**:
   ```bash
   # Login and verify cookies are set
   curl -X POST https://quipflip-c196034288cd.herokuapp.com/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"test","password":"test"}' \
     -c cookies.txt -v

   # Verify cookies work on subsequent requests
   curl https://quipflip-c196034288cd.herokuapp.com/player/me \
     -b cookies.txt
   ```

2. **WebSocket Connection**:
   ```javascript
   // Test in browser console on https://quipflip.xyz
   const token = document.cookie.split('; ')
     .find(row => row.startsWith('quipflip_access_token='))
     .split('=')[1];

   const ws = new WebSocket(
     `wss://quipflip-c196034288cd.herokuapp.com/users/online/ws?token=${token}`
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
cd backend
pytest tests/

# Frontend build test
cd frontend
npm run build
npm run preview
```

## Troubleshooting

### Issue: Cookies not being set

**Solution**: Verify:
1. `ENVIRONMENT=production` is set on Heroku
2. Frontend is accessed via HTTPS (`https://quipflip.xyz`)
3. Backend CORS allows `https://quipflip.xyz`

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

- Check Vercel dashboard for deployment status
- View deployment logs for build errors
- Test at https://quipflip.xyz

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
