# Frontend IA consolidation — verify

**Date:** 2026-08-03  
**Commits:** `f58e115d` (hubs/nav), `b64add73` (chat IA FAQ short-circuit)  
**API tip evidence:** `git_sha=b64add73bd2f60500694177386e617bc528bdcf7` @ health after deploy  
**Vercel production:** `dpl_AhNkw7pCw84wLwrqoMmespzUNyZH` READY for `f58e115d` (gravitre.app)

## Counts

| Metric | Before | After |
|--------|--------|-------|
| Admin primary sidebar items | 31 | **15** (incl. Getting Started; **14** when setup complete) |
| Activity hub | Outcomes + Runs + Failure Alerts peers | `/activity` + Failures tab |
| Intelligence | 9 Insights peers | 1 hub + section links |
| Settings peers | Settings + Enterprise + Federation + Environments | 1 Settings (3 tiers) |

## Evidence

- Link check: `docs/delivery/frontend-ia-link-check.json` — **PASS** (15 admin items; retired hrefs absent)
- Live chat IA battery: `docs/delivery/frontend-ia-chat-battery-live.json` — **PASS — 4/4** on tip `b64add73`  
  - Conversations: activity `1ea9d421…` / agents `edd2139c…` / settings `…` / intelligence `…` (see JSON for latest IDs after FAQ short-circuit re-run)
- Vitest: `apps/web/__tests__/lib/app-routes.test.ts` — 9 passed
- Pytest: `backend/tests/services/test_frontend_ia_nav_faq.py` — 4 passed

## v0 visual handoff

Only after this functional bar: see `docs/delivery/frontend-ia-v0-handoff-prompt.md`.
