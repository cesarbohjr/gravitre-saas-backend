# Unified turn Phase 2 — live verification status

## Deploy + shadow enable

| Step | Status | Evidence |
|------|--------|----------|
| Prod `git_sha` starts with `3cef41f5` / `03f2fa4f` | **NOT RUN** | `GET https://api.gravitre.app/health` @ 2026-07-22T00:29Z → `5d99f9ef…` |
| `UNIFIED_TURN_SHADOW_ENABLED=true` on Railway | **NOT RUN** | Blocked on deploy |
| Local `railway_prod_deploy.py` | **FAILED** | Railway GraphQL **403** (project token invalid/expired) |
| GitHub Actions `Unified Turn Phase 2 Live` run [29880132964](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29880132964) | **FAILED** | `RAILWAY_TOKEN` secret **empty** in workflow env |

**Operator unblock (required before live Phase 2):**

1. Railway → project → **Settings → Tokens** → create/rotate a **project access token**.
2. Set GitHub repo secret **`RAILWAY_TOKEN`** to that token (and refresh `backend/.env.operator.local` if you deploy locally).
3. Redeploy backend from `main` tip (`03f2fa4f` or later) — Railway dashboard “Deploy” on linked repo, or re-run workflow **`unified-turn-phase2-live.yml`** with `commit_sha=03f2fa4f`.
4. Confirm `/health` `git_sha` prefix matches deployed commit.

Shadow flag is set by the workflow step `railway variables set UNIFIED_TURN_SHADOW_ENABLED=true` (or set manually in Railway service variables).

## Phase 2 batteries

| Battery | Status |
|---------|--------|
| Pending-reply 24-case (`verify-pending-reply-classifier-live.py`) | **NOT RUN** (prod tip + shadow) |
| Conversational 20-case (`verify-conversational-path-live.py`) | **NOT RUN** |
| Unified shadow matrix (`verify-unified-turn-phase2-live.py`) | **NOT RUN** |

Orchestration: `scripts/verify-unified-turn-phase2-live.py` (targeted shadow audit cases + invokes both classical batteries). Workflow: `.github/workflows/unified-turn-phase2-live.yml`.

## Code on `main`

- Shadow path: `3cef41f5` + CI/workflow fixes `03f2fa4f` (pending push fix for last test).

After deploy + shadow enabled, expect audit rows: `unified_turn.shadow.completed` on `audit_events` per chat turn (conversation resource).
