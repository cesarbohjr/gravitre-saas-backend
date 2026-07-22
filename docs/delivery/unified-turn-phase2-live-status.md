# Unified turn Phase 2 — live verification status

Updated: 2026-07-22

## Status summary

| Step | Status |
|------|--------|
| GitHub `RAILWAY_TOKEN` secret | Present (updated 2026-07-22) |
| Railway `UNIFIED_TURN_SHADOW_ENABLED=true` | Set by you in UI |
| Code on `main` | Tip **`500f8224`** (unified-turn shadow + copy guard + deploy via `railway up`) |
| Prod `git_sha` | **STUCK** at **`5d99f9ef…`** — tip **not** live |
| Phase 2 batteries | **NOT RUN** (blocked on tip) |

Active run: [29894310148](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29894310148)

## Root cause (confirmed from Actions logs)

1. GraphQL deploy → **Cloudflare 1010 / 403** (project token cannot mutate via Public API).
2. `railway redeploy` → ok but **same image**, SHA unchanged.
3. `railway up ./backend` → **upload + build starts** (e.g. deployment `481aa63f…` on service `20c41db0…`) but `/health` still shows `5d99f9ef…`.
4. That pattern means a **pinned Railway service variable `GIT_SHA=5d99f9ef…`** (or equivalent) is winning, or the new build never becomes the production traffic target.

Health now prefers `RAILWAY_GIT_COMMIT_SHA` then `GIT_SHA` (commit `500f8224`), but **that code is not on prod until tip advances**.

## Do this in Railway (required)

1. Open project → service **`gravitre-saas-backend`** → **Variables**.
2. Find **`GIT_SHA`**:
   - **Delete it**, or set to **`500f8224`** / full SHA of current `main`.
3. Confirm **`UNIFIED_TURN_SHADOW_ENABLED=true`** is still set.
4. Open Deployments → ensure the latest **`railway up` / GitHub** deployment is **Success** and **Promoted** (not failed / rolled back).
5. Hard-refresh [https://api.gravitre.app/health](https://api.gravitre.app/health) — `git_sha` must **not** be `5d99f9ef…`.

Optional: replace GitHub secret `RAILWAY_TOKEN` with an **account token** from [https://railway.com/account/tokens](https://railway.com/account/tokens) so Actions can set variables without the dashboard.

## After tip moves

Re-run workflow (or wait for [29894310148](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29894310148)):

[Unified Turn Phase 2 Live](https://github.com/cesarbohjr/gravitre-saas-backend/actions/workflows/unified-turn-phase2-live.yml)

Artifacts will include:

- `docs/delivery/unified-turn-phase2-battery-live.json`
- pending-reply + conversational battery JSON
