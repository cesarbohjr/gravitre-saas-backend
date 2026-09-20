# Gravitre UX/UI 3.0 Plus — Authenticated Journey Results

**Date:** 2026-09-20  
**Environment policy:** Staging first → controlled prod smoke after staging PASS  
**Spec:** `e2e/ux30-journey-audit.spec.ts`  
**Credentials:** Never stored in this doc — use CI secrets or approved local env

---

## Summary

| ID | Journey | Status | Evidence |
|----|---------|--------|----------|
| J1 | Login → Home | **NOT PROVEN** | Spec ready; requires staging run with live Supabase |
| J2 | Home → AI | **NOT PROVEN** | Not in priority spec yet |
| J3 | Home → Agent → detail → chat | **NOT PROVEN** | — |
| J4 | Home → Workflow → create → run | **NOT PROVEN** | — |
| J5 | Home → Connector → connect → verify | **NOT PROVEN** | — |
| J6 | Intelligence lens switch | **NOT PROVEN** | Spec ready; staging run pending |
| J7 | Activity failure → evidence | **NOT PROVEN** | Spec ready; may BLOCK if fixture org has no failures |
| J8 | Approval → approve | **NOT PROVEN** | — |
| J9 | Source → add | **NOT PROVEN** | — |
| J10 | Marketplace → install | **NOT PROVEN** | — |
| J11 | Command palette → Activity | **NOT PROVEN** | Spec ready; staging run pending |
| J12 | Settings / Admin | **NOT PROVEN** | — |
| J13 | Workspace switch | **NOT PROVEN** | — |
| J14 | Environment switch | **NOT PROVEN** | — |
| J15 | Deep links | **NOT PROVEN** | — |
| J16 | Back navigation | **NOT PROVEN** | — |
| J17 | Lite seat | **NOT PROVEN** | — |

**Prod smoke:** **NOT PROVEN** (blocked until staging PASS for J1, J6, J7, J11)

**Last local run (2026-09-20):** 4 skipped (no live Supabase in agent env), 1 passed (environment gate). Journeys remain **NOT PROVEN** until staging secrets are supplied.

---

## Blockers

| Blocker | Detail |
|---------|--------|
| Staging target | Set `PLAYWRIGHT_BASE_URL` to approved staging URL (not committed) |
| Supabase secrets | `SUPABASE_URL`, keys — same pattern as `navigation-e2e.yml` |
| Billing fixtures | `e2e/.fixtures/billing-users.json` (gitignored; seeded in CI) |
| Failure data for J7 | Fixture org may have zero failed outcomes → journey records **BLOCKED**, not FAIL |

---

## How to run (staging)

```bash
# Example — replace base URL with approved staging host
PLAYWRIGHT_BASE_URL=https://<staging-host> \
SUPABASE_URL=<from-secrets> \
SUPABASE_ANON_KEY=<from-secrets> \
SUPABASE_SERVICE_ROLE_KEY=<from-secrets> \
npx playwright test e2e/ux30-journey-audit.spec.ts
```

After run: update this table with PASS / FAIL / BLOCKED and paste Playwright annotation timestamps (no passwords).

---

## Evidence format (when executed)

```
PASS — J6 Intelligence lens switch @ 2026-09-20T…Z target=https://… playwright annotation
BLOCKED — J7 no failed outcomes in fixture org @ 2026-09-20T…Z
FAIL — J11 command palette — <reason>
```
