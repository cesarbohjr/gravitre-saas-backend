# Gravitre — agent instructions

Repository layout: Next.js app in `apps/web`, FastAPI backend in `backend`, production at https://gravitre.app.

Engineering standards and audit evidence rules live in `docs/ENGINEERING_STANDARDS.md` and `.cursor/rules/`.

## Cloud Agent — after Automate releases

Use this when a change ships (or is about to ship) **Plays**, **Workflows**, or **Schedules** under `apps/web/app/(app)/plays`, `workflows`, or `schedules`, or backend routes/services that feed those pages (`/api/plays`, workflow fleet list, schedules aggregation).

Do **not** treat merge + green CI as done until production acceptance below is **PASS** or honestly labeled **NOT RUN** with a named blocker.

### Required before calling the release complete

1. **Merge gates (already on PR):** full CI — web lint/typecheck/build/tests, backend pytest, integration smoke. See `.github/workflows/ci.yml`.
2. **Deploy alignment**
   - Vercel production (`gravitre.app`): hero assets respond, e.g. `/illustrations/hero-plays.svg` → HTTP 200.
   - Railway: `GET https://gravitre-saas-backend-production.up.railway.app/health` → `git_sha` matches the merged `main` commit (see `.github/workflows/railway-backend-production.yml`).
   - Supabase: only if the diff includes migrations; follow the repo migration governance runbook — never apply prod migrations without explicit human approval.
3. **Plays production acceptance (when credentials exist)**
   - Contract: `docs/delivery/plays-production-acceptance.md`.
   - Workflow: **Plays production acceptance** (`.github/workflows/plays-production-acceptance.yml`) — `workflow_dispatch` on `main`, optional `backend_url` (default Railway prod).
   - Needs GitHub **production** environment secrets (`SUPABASE_*`) and a token the workflow mints via `scripts/mint_smoke_org_session.py`; proof script `scripts/verify-plays-production.py` writes `docs/delivery/plays-production-acceptance.json` (artifact upload).
   - Cloud Agent tokens often **cannot** dispatch this workflow; if blocked, record **NOT RUN — no workflow_dispatch / production secrets** and ask a human to run it from Actions.
4. **Authenticated UI on gravitre.app (roles)**
   - With a real session (admin + non-admin as appropriate): open **Plays**, **Workflows**, **Schedules** — hero + stat filters, views, detail panel, calendar/agenda, honest truncation copy, admin-only retry. No console errors on those routes.
   - Vercel **preview** URLs for this repo may be team SSO-gated; prefer **gravitre.app** after merge when cloud login is unavailable.
   - If manual UI testing is required and `computerUse` is unavailable, say so explicitly; do not upgrade **NOT RUN** to **PASS**.

### Evidence to cite in the delivery report

- CI run URL on the merge PR.
- Merge commit SHA.
- `/health` `git_sha` and timestamp.
- HTTP checks for hero SVGs and auth redirect on `/plays` (307 → login when logged out is expected).
- Plays acceptance artifact or workflow run URL when step 3 ran.
- For UI claims: screenshot/video under `/opt/cursor/artifacts/` or audit-grade production proof from the acceptance script.
