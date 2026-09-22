# Gravitre UX/UI 3.0 Plus — Authenticated Journey Results

**Date:** 2026-09-21  
**Environment policy:** Staging first → controlled prod smoke after staging PASS  
**Spec:** `e2e/ux30-journey-audit.spec.ts`  
**Credentials:** Never stored in this doc — uses `e2e/.fixtures/gravitre-e2e-storage.json` (gitignored)

---

## Summary

| ID | Journey | Status | Evidence |
|----|---------|--------|----------|
| J1 | Login → Home | **NOT PROVEN** | — |
| J2 | Home → AI | **NOT PROVEN** | — |
| J3 | Home → Agent → detail → chat | **NOT PROVEN** | — |
| J4 | Home → Workflow → create → run | **NOT PROVEN** | — |
| J5 | Home → Connector → connect → verify | **NOT PROVEN** | — |
| J6 | Intelligence I1 field + lens switch | **PASS** | Playwright @ `https://gravitre.app` 2026-09-21 · `intelligence-i1-i2` + map canvas + lens Learns→Predicts · deploy `9ab9c205`+ |
| J7 | Activity inspect + trace | **PASS** | Playwright @ `https://gravitre.app` 2026-09-21 · org `f07e57c0-1501-4000-8000-c04e57a00001` · `activity-trace-a1` + `activity-trace-rail` + `activity-trace-story` visible · deploy `b4f0e32d` |
| J8 | Approval → approve | **NOT PROVEN** | — |
| J9 | Source → add | **NOT PROVEN** | — |
| J10 | Marketplace → install | **NOT PROVEN** | — |
| J11 | Command palette → Activity | **NOT PROVEN** | — |
| J12 | Settings / Admin | **NOT PROVEN** | — |
| J13 | Workspace switch | **NOT PROVEN** | — |
| J14 | Environment switch | **NOT PROVEN** | — |
| J15 | Deep links | **NOT PROVEN** | — |
| J16 | Back navigation | **NOT PROVEN** | — |
| J17 | Lite seat | **NOT PROVEN** | — |

**Prod smoke (Activity + Intelligence pilots):** **PARTIAL PASS** — J7 PASS deploy `b4f0e32d` · J6 PASS deploy `9ab9c205`+ on `gravitre.app`

---

## J6 Wave 1 re-run (2026-09-22) — BLOCKED

**Attempt:** Post–Wave 1 deploy (`27da2830` I3 matrix default + I2 mobile)  
**Result:** **NOT RUN** — expired `e2e/.fixtures/gravitre-e2e-storage.json`; `beforeEach` timed out on marketing/login (no `aside nav`).  
**Action:** Regenerate storage via `e2e/consume-smoke-session.mjs`, then re-run J6 (asserts `intel-i3-matrix`, Matrix→Field toggle).

---

## J6 detail (2026-09-21)

**Command:**
```bash
PLAYWRIGHT_BASE_URL=https://gravitre.app \
PLAYWRIGHT_SKIP_BACKEND=1 \
PLAYWRIGHT_REUSE_SERVER=1 \
npx playwright test e2e/ux30-journey-audit.spec.ts -g "J6"
```

**Result:** PASS (42s)

**Observed:**
- Authenticated session via storage state (isolated smoke org `f07e57c0-…`)
- `/intelligence` I1 surface: `data-testid="intelligence-i1-i2"`
- Map canvas visible; lens switch Knows → Learns → Predicts
- I2 stream closed by default after deploy `9ab9c205` (`intel-i2-toggle` present, stream hidden)

---

## J7 detail (2026-09-21)

**Command:**
```bash
PLAYWRIGHT_BASE_URL=https://gravitre.app \
PLAYWRIGHT_SKIP_BACKEND=1 \
PLAYWRIGHT_REUSE_SERVER=1 \
npx playwright test e2e/ux30-journey-audit.spec.ts -g "J7"
```

**Result:** PASS (1.4m)

**Observed:**
- Authenticated session via storage state (isolated smoke org)
- `/activity` loaded; outcome selected (All filter — no failed outcomes in org)
- Activity A1 pilot visible: `data-testid="activity-trace-a1"`, rail + story panel
- Run/trace link present on selected outcome

**Note:** Failed-status filter returned zero rows in isolated org — not a product FAIL; test falls back to All.

---

## Blockers (remaining journeys)

| Blocker | Detail |
|---------|--------|
| Staging-only URL | J7 executed on production `gravitre.app` (approved smoke org); dedicated staging host optional for J1/J6/J11 |
| Failure fixture data | Isolated org has no failed outcomes — J7 PASS uses succeeded outcome + TRACE panel |

---

## Evidence format

```
PASS — J7 activity inspect + trace @ 2026-09-21T…Z target=https://gravitre.app org=f07e57c0-… deploy=b4f0e32d
```
