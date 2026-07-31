# Auth / OAuth runbook (gravitre.app)

## Hide `*.supabase.co` on Google / Microsoft OAuth screens

Users must never see `smyeexlrqdpymwjmgzqu.supabase.co` on login. Fix:

1. **Supabase custom domain** `auth.gravitre.app` (optional; only after DNS + activate — see below)
2. **Until then:** production uses **`https://gravitre.app/auth/v1/*`** proxy (set `NEXT_PUBLIC_SUPABASE_AUTH_URL=https://gravitre.app` and `SUPABASE_PROJECT_URL=https://<ref>.supabase.co` on Vercel)
3. **Do not** point `NEXT_PUBLIC_SUPABASE_AUTH_URL` at `auth.gravitre.app` until Supabase custom domain is **activated** — otherwise login 404s (`DEPLOYMENT_NOT_FOUND`)

Code reads branded URL from `apps/web/lib/supabase/url.ts` (`getSupabasePublicUrl()`). Same-origin fallback proxies `/auth/v1/*` on `gravitre.app` when `SUPABASE_PROJECT_URL` is set (`next.config.mjs`).

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
- `NEXT_PUBLIC_SUPABASE_AUTH_URL=https://auth.gravitre.app` (browser — never `*.supabase.co` in prod)
- `SUPABASE_PROJECT_URL=https://smyeexlrqdpymwjmgzqu.supabase.co` (server-only)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — anon key for that project
- `FASTAPI_BASE_URL=https://gravitre-saas-backend-production.up.railway.app`

### Supabase Dashboard → Authentication → URL Configuration

- **Site URL:** `https://gravitre.app`
- **Redirect URLs:** `https://gravitre.app/auth/callback`, `https://gravitre.app/**`, plus localhost entries for dev

CLI sync (needs `SUPABASE_ACCESS_TOKEN`):

```powershell
powershell -File scripts/sync-supabase-auth-urls.ps1
```

Or full sync + Vercel env (requires GitHub/repo secrets `SUPABASE_ACCESS_TOKEN`, `VERCEL_TOKEN`):

```bash
bash scripts/configure-auth-production.sh
```

Enable Google login provider on Supabase (linked CLI + `backend/.env.operator.local`):

```powershell
npm run auth:supabase-google
```

One-pass platform setup (Supabase, Google, Vercel deploy, GitHub secrets):

```powershell
npm run platform:apply
# After first-time GCP login:
gcloud auth login
npm run platform:apply
```

Set GitHub secrets only:

```powershell
npm run platform:github-secrets
```

Add repository secrets for the **Auth Config Sync** workflow (Settings → Secrets → Actions):

| Secret | Purpose |
|--------|---------|
| `SUPABASE_ACCESS_TOKEN` | Management API auth URL + Google secret patch |
| `SUPABASE_PROJECT_REF` | `smyeexlrqdpymwjmgzqu` |
| `VERCEL_TOKEN` | Vercel env upsert + optional deploy |
| `VERCEL_ORG_ID` | `gravitre-ai` |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://smyeexlrqdpymwjmgzqu.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key |

### Railway

- `SUPABASE_URL=https://smyeexlrqdpymwjmgzqu.supabase.co`
- `SUPABASE_URL` — used for JWKS (`/auth/v1/.well-known/jwks.json`) when tokens are **ES256**
- `SUPABASE_JWT_SECRET` — legacy **HS256** verification only; ES256 user tokens are verified via JWKS automatically

### Google Cloud Console (Gravitre OAuth client)

**Login (Supabase):**

```
https://smyeexlrqdpymwjmgzqu.supabase.co/auth/v1/callback
```

**Connectors (Railway API)** — see [integration/GOOGLE_OAUTH.md](integration/GOOGLE_OAUTH.md):

```
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_analytics/callback
https://gravitre-saas-backend-production.up.railway.app/api/connectors/oauth/google_calendar/callback
```

CLI: `npm run google:setup`, `npm run google:fill-env`, `npm run google:railway`, `npm run google:check`

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
- `apps/web/proxy.ts` — protects app routes (Next.js 16 proxy; replaces deprecated `middleware.ts`)
- `apps/web/lib/auth-session.ts` — canonical origin + cookie cleanup
