# Auth / OAuth runbook (gravitre.app)

## Architecture

| Layer | Role |
|-------|------|
| **Vercel** (`apps/web`) | Login UI, `/auth/callback` PKCE exchange, session cookies |
| **Supabase** (`smyeexlrqdpymwjmgzqu`) | Google/GitHub/Azure OAuth, JWT issuance |
| **Railway** (`gravitre-saas-backend`) | Validates JWT on `/api/auth/me` via `SUPABASE_JWT_SECRET` |

OAuth redirect chain:

1. Browser → `signInWithOAuth` → Supabase authorize
2. Supabase → `https://gravitre.app/auth/callback?code=...`
3. Next.js exchanges code, sets `sb-*` cookies, redirects to `/operator`
4. Middleware `getUser()` must see valid cookies

## `session_expired` on login

Usually **stale `sb-*` cookies** (session invalid but cookies remain). Fixed by:

- Middleware clearing auth cookies when redirecting to login
- Login page calling `signOut({ scope: "local" })` on `session_expired` / `auth_callback_failed`
- Canonical origin via `NEXT_PUBLIC_APP_URL=https://gravitre.app` for all redirects

## Required production config

### Vercel (`gravitre-saas-backend` project)

- `NEXT_PUBLIC_APP_URL=https://gravitre.app`
- `NEXT_PUBLIC_SUPABASE_URL=https://smyeexlrqdpymwjmgzqu.supabase.co`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — anon key for that project
- `FASTAPI_BASE_URL=https://gravitre-saas-backend-production.up.railway.app`

### Supabase Dashboard → Authentication → URL Configuration

- **Site URL:** `https://gravitre.app`
- **Redirect URLs:** `https://gravitre.app/auth/callback`, `https://gravitre.app/**`, plus localhost entries for dev

CLI sync (needs `SUPABASE_ACCESS_TOKEN`):

```powershell
powershell -File scripts/sync-supabase-auth-urls.ps1
```

Or full sync + Vercel env:

```bash
bash scripts/configure-auth-production.sh
```

### Railway

- `SUPABASE_URL=https://smyeexlrqdpymwjmgzqu.supabase.co`
- `SUPABASE_JWT_SECRET` — must match Supabase **Settings → API → JWT Secret** (invalid secret → `/api/auth/me` 401 → client shows `session_expired`)

### Google Cloud Console (OAuth client used by Supabase)

Authorized redirect URI:

```
https://smyeexlrqdpymwjmgzqu.supabase.co/auth/v1/callback
```

## Verify

```powershell
# Invalid code should → auth_callback_failed (not session_expired)
curl.exe -sI "https://gravitre.app/auth/callback?code=invalid-test"

# After real OAuth, Railway should accept JWT
# (use browser Network tab: /api/auth/me → 200)
```

## Code map

- `apps/web/lib/oauth.ts` — starts OAuth
- `apps/web/app/auth/callback/route.ts` — PKCE `exchangeCodeForSession`
- `apps/web/middleware.ts` — protects app routes
- `apps/web/lib/auth-session.ts` — canonical origin + cookie cleanup
