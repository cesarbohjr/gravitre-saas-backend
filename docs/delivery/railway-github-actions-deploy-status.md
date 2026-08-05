# Railway GitHub Actions vs prod deploy status

Updated: 2026-08-05

## Fix (2026-08-05b) — watchPatterns false skip + CLI redeploy of stale tip

Root cause of Phase 1 health stuck on `554403df` through a full wait + forced
redeploy (CI run [30988877306](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/30988877306)):

1. **Railway GitHub watchPatterns false negative (recurring)** — commit
   `cb62f2d9` changed many `backend/app/**` files, but Railway status was
   `No deployment needed - watched paths not modified`. Same skip for
   `218b5d2e` / `5e198066`. Only `882eed34` deployed because it touched
   `.railway-deploy-stamp`. **Fix:** broaden `backend/railway.toml`
   `watchPatterns` to both Root-Directory-relative (`app/**`) and
   repo-root-relative (`backend/app/**`) globs; keep the stamp lever.
2. **GraphQL force → CLI redeploy of the live tip (mechanism gap)** — force
   path hit `GraphQL deploy failed (HTTP Error 403 …)` then fell back to
   `railway redeploy`, which rebuilds the *currently running* deployment
   (`554403df`), not `--commit-sha`. Wait cycle then timed out on the same
   stale SHA. **Fix:** refuse CLI redeploy fallback when a tip SHA is pinned;
   fail the gate instead of claiming a force-deploy.

## Fix (2026-08-05) — tip lag + fake tip

Two failures pinned prod on stale SHAs while `main` advanced:

1. **CI-gated Railway workflow** — `workflow_run` required full CI `success`. Web /
   Lighthouse / pip-audit failures **skipped** the backend deploy gate even when
   `backend/` changed. **Fix:** trigger on `push` to `main` with `backend/**` paths
   (no full-CI green requirement).
2. **Fake tip via `GIT_SHA`** — force path ran `railway variables set GIT_SHA=…`.
   `/health` can report that override while `RAILWAY_GIT_COMMIT_SHA` (real image)
   stayed old. **Fix:** never set `GIT_SHA` on force; delete override before wait;
   GraphQL redeploy only.

## Updated: 2026-08-01

## Symptom

Workflow **Railway backend production** / CLI deploy shows **FAILED** at Build image step `[3/5] COPY requirements.txt …` with **failed to calculate checksum**, while a parallel **via GitHub** deploy succeeds and **`/health` `git_sha`** advances. Requirements files are present — this is a race, not a missing file.

## Fix (2026-08-01b)

`force_railway_up=true` **never** runs `railway up` (CLI image upload). After waiting for GitHub auto-deploy, a stuck tip uses `scripts/railway_prod_deploy.py --commit-sha …` (GraphQL / CLI redeploy of the GitHub commit). That avoids FAILED builds at `COPY requirements*.txt` / `failed to calculate checksum` when two Metal builders race.

## Fix (2026-08-01)

Even `force_railway_up=true` **waits for GitHub auto-deploy first**. CLI `railway up` was previously a last resort when `/health` stayed stale; that path raced healthy GitHub deploys (e.g. tip live while CLI upload failed at COPY checksum) and is removed.

## Fix (2026-07-31)

Default deploy gate **waits for GitHub-connected auto-deploy only**. CLI `railway up` runs only on `workflow_dispatch` with `force_railway_up=true` (default **false**).

Example: CI run [29985678545](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29985678545) failed at `railway up` (~12s after upload); prod **`/health`** showed `19bdf7d2…` matching the same push.

## Root cause (not the fsutil config-path issue)

| Issue | Signature |
|-------|-----------|
| **Monorepo config-path (historical)** | Build logs: `fsutil.NewFS(.../backend): no such file or directory` — Root Directory + `backend/Dockerfile` double prefix |
| **This CI noise (current)** | Upload + `scheduling build on Metal builder` then **`Deploy failed`** with **no** fsutil line; prod tip updates anyway |

**Cause:** Two deploy triggers on the same `main` push:

1. **Railway GitHub integration** (repo-connected auto-deploy)
2. **`.github/workflows/railway-backend-production.yml`** → `railway up ./backend --path-as-root --ci`

The CLI `--ci` waiter often exits **1** when the competing deployment wins, is superseded, or the watched build fails/cancels — even though the **other** deployment succeeds.

## Fix (2026-07-25)

1. **Skip deploy gate on frontend-only pushes** — workflow job `detect-backend-changes` uses `scripts/railway_commit_touches_backend.py`; no Railway CLI upload or 15m health wait when `backend/` is untouched.
2. **Remove `railway up --ci` from CI** — rely on GitHub-connected Railway auto-deploy + `/health` poll only (eliminates duplicate FAILED deployments on the service).
3. **Tighten `watchPatterns`** in `backend/railway.toml` to backend app paths only (`app/**`, requirements, Dockerfile).

## Fix (2026-07-23)

## Operational note

If you want a single deploy path, either disable GitHub auto-deploy on the Railway service **or** remove the workflow’s `railway up` and keep health verification only — do not run both without the skip/health gate above.
