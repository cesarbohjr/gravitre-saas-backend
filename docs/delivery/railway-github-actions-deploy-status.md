# Railway GitHub Actions vs prod deploy status

Updated: 2026-08-01

## Symptom

Workflow **Railway backend production** / CLI deploy shows **FAILED** at Build image step `[3/5] COPY requirements.txt …` with **failed to calculate checksum**, while a parallel **via GitHub** deploy succeeds and **`/health` `git_sha`** advances. Requirements files are present — this is a race, not a missing file.

## Fix (2026-08-01)

Even `force_railway_up=true` **waits for GitHub auto-deploy first**. CLI `railway up` runs only when `/health` is still stale after that wait (true stuck tip). This stops FAILED CLI builds from racing a healthy GitHub deploy (e.g. `da229da5` tip live while CLI upload failed at COPY checksum).

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
