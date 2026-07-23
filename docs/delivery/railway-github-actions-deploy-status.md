# Railway GitHub Actions vs prod deploy status

Updated: 2026-07-23

## Symptom

Workflow **Railway backend production** fails on `railway up … --ci` with exit **1** and only `Deploy failed` in logs, while **`/health` `git_sha`** on `api.gravitre.app` still advances to the CI commit shortly after.

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

## Fix

Workflow treats **`/health` `git_sha` match** (via `scripts/railway_prod_deploy.py --wait-health-only`) as the **only** job failure gate. It **skips** `railway up` when health is already on/at/after the CI commit, and **does not fail** the job solely on `railway up` exit code when health later matches (warning annotation only).

## Operational note

If you want a single deploy path, either disable GitHub auto-deploy on the Railway service **or** remove the workflow’s `railway up` and keep health verification only — do not run both without the skip/health gate above.
