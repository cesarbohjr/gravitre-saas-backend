# UI/UX audit pass 2 — final deliverable (2026-07-25)

Scope: functional reliability, responsive layout, frontend-backend wiring, code cleanliness, backend parity.

**Shipped commits (main):** `be0ca238` (audit fixes) → `9f83cb67` (homepage RSC) → `42013a1b` (Railway deploy gate) → `2bf67f6b` (healthcheck cold-start)

---

## Part A — Functional reliability

### FIXED
| Item | Evidence |
|------|----------|
| Link checker `/` false empty | `scripts/check-deployed-links.py` `SERVER_SHELL_PATHS`; exit **0** |
| Legacy redirect assertions | PASS prod 2026-07-25: `/support/getting-started`, `/guides/create-your-first-ai-agent`, `/docs/guides/how-to-create-your-first-agent`, `/docs/sdk/node` |
| Metadata regressions | PASS `/api`, `/support`, `/changelog` |
| Full crawl (131 pages, 5226 edges) | **0 broken 4xx** — `docs/delivery/link-check-audit-pass2-final.json` |
| `apiFetch` 60s timeout + user message | `RequestTimeoutError` in `apps/web/lib/fetcher.ts` (`be0ca238`) |
| Home dashboard loading/error | Skeleton + `WorkSectionErrorCard` (`apps/web/app/home/page.tsx`) |
| Live activity rail runs error | User-visible message on runs fetch failure |
| **Homepage production crash** | Vercel digest `3346737748` — Lucide icons passed RSC→client; fixed `9f83cb67`; prod HTML contains “Built for operators, not chatbots” @ 2026-07-25 |
| Standing link-check CI | Nightly `.github/workflows/production-hardening-smoke.yml` |

### CONFIRMED ALREADY CORRECT
- **Post-deploy chat smoke** — `.github/workflows/railway-backend-production.yml` (backend-changed pushes only after `42013a1b`)
- **Connectors page** — `isLoading` / `error` / empty in `apps/web/app/marketplace/connectors/page.tsx`

### NAMED GAP
- **Authenticated in-app route crawl** — Playwright `navigation-e2e.yml` remains manual dispatch; HTML crawl covers marketing/docs shell

---

## Part B — Responsive design

### FIXED
| Item | File |
|------|------|
| Agent chat message actions (mobile hover-only) | `apps/web/app/agents/[id]/chat/page.tsx` — visible below `sm`, hover-reveal desktop |
| BusinessOutcome title overflow | `business-outcome-view.tsx` — `break-words` |

### CONFIRMED ALREADY CORRECT (code review)
- Conversation sidebar — mobile drawer (`fixed md:static`, scrim, `w-72`)
- Live activity rail — `w-[86%] max-w-sm` mobile overlay, `xl:` static
- AiWorkspace bubbles — `max-w-[min(...)]`, standard `sm/md/xl` Tailwind
- Breakpoint system — Tailwind defaults on audited surfaces; localized `max-w-[...]` for chat density only

### NAMED GAP
- **Screenshot QA at 375/390/768/1280** — code patterns sound; v0 scopes visual polish (see handoff below)

---

## Part C — Frontend-backend wiring

### CONFIRMED ALREADY CORRECT
- Settings → Webhooks — real Supabase API + loading/error/empty (prior pass fix retained)
- Environment surfacing — `top-bar.tsx` production/staging badge; `x-environment` on every `apiFetch`
- Settings/Billing — real Stripe/subscription flows with toast errors on write failure

### NAMED GAP
- Exhaustive button→endpoint matrix — no new mock-data controls found; full sweep deferred

---

## Part D — Code cleanliness

### FIXED
- ESLint burn-down — **313 → 307** warnings (0 errors); unused imports in `pricing-page-data.ts`, `icons.tsx`

### NAMED GAP
- Classical pipeline rollback — `unified_turn_classical_fallback.py` intentional until unified-turn sign-off
- Remaining ESLint — exported API type unused-vars, `set-state-in-effect` hooks (~300 warnings)

### CONFIRMED ALREADY CORRECT
- No scratch `console.log` in `apps/web/app/ai/**`

---

## Part E — Backend parity

### CONFIRMED ALREADY CORRECT
- `pip-audit` in CI — `.github/workflows/ci.yml` `security-scan`
- `pnpm audit` in CI — critical fail + high report
- Prod `/health` — `git_sha=2bf67f6bb6cdb4db2b6e5c46d25da709dce5f205` @ `2026-07-25T07:15:18Z`, checks healthy

### NAMED GAP
- Dead endpoint inventory — not re-enumerated; OpenAPI redaction covers public surface

---

## Deploy / verification (final)

| Check | Result |
|-------|--------|
| `check-deployed-links.py` prod | **PASS** exit 0, 131 pages |
| Prod homepage | **PASS** — marketing SSR content (no error digest) |
| Prod `/health` git_sha | `2bf67f6b…` @ 2026-07-25T07:15:18Z |
| ESLint web | 307 warnings, 0 errors |
| Railway deploy gate (frontend-only) | **SKIPPED** run `30148808303` after `42013a1b` (expected) |
| Post-deploy chat smoke | Runs on backend-changed pushes only |
