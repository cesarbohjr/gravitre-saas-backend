# UI/UX audit pass 2 — 2026-07-24

Scope: functional reliability, responsive layout, frontend-backend wiring, code cleanliness, backend parity.

## Part A — Functional reliability

### FIXED
- **Link checker false failure on `/`** — `scripts/check-deployed-links.py` treats client-rendered marketing shell (`SERVER_SHELL_PATHS`) as alive when `og:title` is present. Re-run exit **0**; artifact `docs/delivery/link-check-audit-pass2.json`.
- **Legacy redirect assertions still live** — PASS on prod: `/support/getting-started`, `/guides/create-your-first-ai-agent`, `/docs/guides/how-to-create-your-first-agent`, `/docs/sdk/node`; metadata PASS on `/api`, `/support`, `/changelog`.
- **Unbounded frontend API calls** — `apiFetch()` now aborts after 60s (`DEFAULT_API_TIMEOUT_MS`) and throws `RequestTimeoutError` with user-facing copy (`apps/web/lib/fetcher.ts`).
- **Home dashboard silent load** — skeleton while onboarding loads; `WorkSectionErrorCard` on failure (`apps/web/app/home/page.tsx`).
- **Live activity rail runs silent failure** — user-visible error when runs list fetch fails (`apps/web/app/ai/_components/live-activity-rail.tsx`).
- **Standing link-check CI** — nightly `production-hardening-smoke.yml` step runs `check-deployed-links.py` against `https://gravitre.app`.

### CONFIRMED ALREADY CORRECT
- **Post-deploy chat smoke** — `.github/workflows/railway-backend-production.yml` runs `scripts/smoke-post-deploy-chat-live.py` after `/health` git_sha gate.
- **No new broken URLs (4xx)** on prod crawl (2026-07-25 run).

### NAMED GAP
- **Link checker crawl depth** — homepage is client-rendered; HTML crawl discovers 0 edges (links hydrate client-side). Known assertions + metadata cover regressions; full in-app route crawl needs Playwright (existing `navigation-e2e.yml`, manual dispatch only).

## Part B — Responsive design

### FIXED
- **Agent chat message actions on mobile** — copy/regenerate rail was hover-only; now always visible below `sm`, hover-reveal on desktop (`apps/web/app/agents/[id]/chat/page.tsx`).
- **BusinessOutcome long titles** — `break-words` on title to prevent overflow (`business-outcome-view.tsx`).

### CONFIRMED ALREADY CORRECT (code review)
- **Conversation history sidebar** — mobile drawer (`fixed md:static`, scrim, `w-72`, explicit close).
- **Live activity rail** — mobile overlay `w-[86%] max-w-sm`, `xl:` static sidebar.
- **AiWorkspace / chat bubbles** — `max-w-[min(...)]`, standard Tailwind `sm/md/xl` breakpoints (no ad-hoc breakpoint system drift found on audited surfaces).

### NAMED GAP
- **Visual breakpoint QA at 375/768/1280** — layout patterns are sound in code; no browser screenshot pass in this cycle. v0 handoff scopes presentation polish on surfaces below.

## Part C — Frontend-backend wiring

### CONFIRMED ALREADY CORRECT
- **Settings → Webhooks** — real Supabase wiring with loading/error/empty (`apps/web/app/settings/page.tsx`, `apps/web/app/api/settings/webhooks/route.ts`).
- **Environment selector** — `top-bar.tsx` shows production/staging badge; `x-environment` header on every `apiFetch` via `getEnvironmentHeader()`.

### NAMED GAP
- **Full dead-affordance sweep** — no new mock-data controls found beyond prior webhooks fix; exhaustive button→endpoint matrix deferred (large scope).

## Part D — Code cleanliness

### FIXED
- **ESLint burn-down** — 309 → **306** warnings (`--fix` + unused imports in `pricing-page-data.ts`, `icons.tsx`, `auth-session.ts`).

### NAMED GAP
- **Classical pipeline removal** — `unified_turn_classical_fallback.py` and fallthrough in `unified_turn_reasoning_service.py` remain as intentional rollback; removal blocked on unified-turn live stability sign-off.
- **Remaining ESLint** — mostly `@typescript-eslint/no-unused-vars` on exported API types and `react-hooks/set-state-in-effect`; batch fix is a dedicated hygiene pass.

### CONFIRMED ALREADY CORRECT
- **No scratch `console.log`** in `apps/web/app/ai/**` from recent work.

## Part E — Backend parity

### CONFIRMED ALREADY CORRECT
- **pip-audit in CI** — `.github/workflows/ci.yml` `security-scan` job runs `scripts/pip-audit-backend.py`.
- **pnpm audit in CI** — same job, critical fail + high report.

### NAMED GAP
- **Dead endpoint inventory** — not re-enumerated this pass; prior OpenAPI redaction covers public surface.

## Verification (pre-push)

| Check | Result |
|-------|--------|
| `check-deployed-links.py` prod | **PASS** exit 0 |
| ESLint web | 306 warnings, 0 errors |
| Prod `/health` git_sha (pre-push) | `81ff4a26…` |

Post-push: CI → Railway backend deploy gate + post-deploy chat smoke; nightly link-check on schedule.
