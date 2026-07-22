# Unified turn Phase 2 — live verification status

Updated: 2026-07-22

## What we learned from CLI / GitHub Actions

| Finding | Detail |
|---------|--------|
| GraphQL deploy | **403 / Cloudflare 1010** — project token cannot deploy via Public API from Actions |
| `railway redeploy` | Returns ok but **restarts the same image** — `git_sha` stays `5d99f9ef…` |
| `railway up` | **Works** — uploads backend and starts a build (example: service `20c41db0…` deployment `481aa63f…`) |
| Health stuck | `/health` still reports `5d99f9ef…` — almost certainly a **pinned `GIT_SHA` service variable** (health used to prefer `GIT_SHA` over `RAILWAY_GIT_COMMIT_SHA`) |
| Shadow flag | You set `UNIFIED_TURN_SHADOW_ENABLED=true` in Railway UI — good; code not live until tip advances |

## One manual step that unblocks everything (do this now)

1. Open Railway service **gravitre-saas-backend** → **Variables**.
2. Find **`GIT_SHA`**:
   - Either **delete it**, or set it to tip **`858bb4d9`** / full `858bb4d9…` (current `main` when this doc was written; check `git rev-parse HEAD` after pull).
3. Open the latest failed workflow deploy’s **Build Logs** link (from Actions), or trigger a fresh deploy:
   - [Unified Turn Phase 2 Live](https://github.com/cesarbohjr/gravitre-saas-backend/actions/workflows/unified-turn-phase2-live.yml) → Run workflow, leave `commit_sha` empty, `enable_shadow=true`.
4. Confirm [https://api.gravitre.app/health](https://api.gravitre.app/health) `git_sha` starts with the tip (not `5d99f9ef`).

Optional better token: replace GitHub secret `RAILWAY_TOKEN` with an **account/team** token from [https://railway.com/account/tokens](https://railway.com/account/tokens) so CLI can set variables without the dashboard.

## Code fixes shipped on `main`

- Deploy workflow uses **`railway up ./backend --path-as-root --ci`** (waits for build), not GraphQL / bare redeploy.
- Health prefers **`RAILWAY_GIT_COMMIT_SHA` then `GIT_SHA`**.
- Dockerfile accepts build-time `GIT_SHA` ARG.
- Phase 2 battery: `scripts/verify-unified-turn-phase2-live.py`.

## Batteries

| Battery | Status |
|---------|--------|
| Deploy tip + shadow | **BLOCKED** on pinned `GIT_SHA` / tip advance |
| Pending-reply 24 + conversational 20 + shadow audits | **NOT RUN** until tip matches |

Latest Actions runs:

- [29893361361](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29893361361) — `railway up` uploaded; health wait timed out on `5d99f9ef`
- [29892352732](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29892352732) — GraphQL 1010 → redeploy; same stuck SHA
