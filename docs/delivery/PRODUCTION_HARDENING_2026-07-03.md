# Gravitre Production Hardening (2026-07-03)

## STEP 0 — Already in place (confirmed, not rebuilt)

| Item | Status |
|------|--------|
| Pydantic `Settings` in `backend/app/config.py` | Live — validates required Supabase/Stripe fields at startup |
| Structured logging + request ID context | Live — `backend/app/core/logging.py`, `request_tracing` middleware in `main.py` |
| HTTP exception normalization | Live — `backend/app/core/errors.py` (`http_exception_handler`) |
| Stripe webhook signature + idempotency | Live — `stripe.Webhook.construct_event`, `stripe_webhook_events` table |
| CORS explicit allowlist (not `*`) | Live — was localhost + `NEXT_PUBLIC_APP_URL`; extended today |
| Route-level `error.tsx` boundaries | Live — 93 routes already have `error.tsx` |
| Scheduler per-iteration error isolation | Live — e.g. `company_intelligence_scheduler._run_once` catches per-org failures |
| AI/org rate limiting (model path) | Live — `ai_guardrails.enforce_rate_limit` on model router |
| Entitlement/trial blocking tests | Live — `test_entitlement_service.py`, `test_entitlements.py` |
| Supabase client (no SQLAlchemy pool) | Architecture — pooling N/A; uses Supabase REST via service role |

## SECTION 1 — Security

| Item | Result |
|------|--------|
| HTTP security headers | **Added** — `apps/web/next.config.mjs` (`headers()` with HSTS, CSP, X-Frame-Options, etc.) |
| CORS allowlist | **Hardened** — added `gravitre.app`, `www.gravitre.app`, `STAGING_ORIGIN` env |
| Rate limiting (sensitive POST routes) | **Added** — `backend/app/core/rate_limiter.py`, `middleware/api_rate_limit.py` on auth/intelligence/agent-jobs/marketplace/admin MCP |
| Webhook verification | **Confirmed present** — Stripe construct_event + idempotency tests pass |

## SECTION 2 — Error handling and observability

| Item | Result |
|------|--------|
| Structured error responses | **Partial** — global handler normalizes; many routes still use string `detail` (incremental migration) |
| Global exception handler | **Added** — catches unhandled exceptions, no raw trace to clients |
| Structured JSON logging | **Extended** — `setup_logging()` + optional `LOG_FORMAT=json` |
| Request ID middleware | **Already existed** — `request_tracing` sets `X-Request-ID` |
| Health check endpoint | **Extended** — DB + Redis checks, `checks` object, Railway target |

## SECTION 3 — Database reliability

| Item | Result |
|------|--------|
| Connection pool config | **N/A documented** — Supabase REST; no SQLAlchemy engine |
| Slow query logging | **Not added** — would require Postgres driver instrumentation |
| Scheduler error isolation | **Confirmed** — company intelligence + memory promotion schedulers |

## SECTION 4 — Frontend reliability

| Item | Result |
|------|--------|
| `global-error.tsx` | **Added** |
| API fetcher 429 handling | **Added** — `RateLimitError` + `Retry-After` |
| Route error boundaries | **Already existed** — 93 `error.tsx` files; no mass duplication |

## SECTION 5 — Environment config

| Item | Result |
|------|--------|
| Pydantic Settings validation | **Already existed** in `app/config.py` |
| Secrets not in logs/responses | **Confirmed** — global 500 hides internals; spot-check clean |
| `.env.example` | **Updated earlier** — FASTAPI_BASE_URL / NEXT_PUBLIC_API_URL guidance |

## SECTION 6 — Deployment reliability

| Item | Result |
|------|--------|
| Railway healthcheck config | **Added** — `railway.json` → `/health`, 30s timeout |
| Graceful shutdown | **Partial** — lifespan cancels scheduler tasks; uvicorn SIGTERM default |
| Migration safety | **Manual** — migrations via Supabase CLI/GitHub Actions; run before deploy |

## SECTION 7 — Test coverage

| Item | Result |
|------|--------|
| New tests | **Added** — `backend/tests/test_critical_paths.py` (rate limit 429, global handler, health checks) |
| Trial/entitlement tests | **Already existed** |

## SECTION 8 — Monitoring scaffolding

| Item | Result |
|------|--------|
| Business event logger | **Added** — `backend/app/core/metrics.py` (`log_business_event`) |
| Uptime monitor | **Documented** — point external monitor at `https://gravitre-saas-backend-production.up.railway.app/health` |

## ITEMS REQUIRING MANUAL ACTION

1. Add `/health` to an external uptime monitor (Better Uptime, Checkly, etc.).
2. Set `LOG_FORMAT=json` on Railway if log aggregation expects JSON.
3. Set `STAGING_ORIGIN` on staging deployments if used.
4. Run Supabase migrations before promoting backend deploys.

## ITEMS REQUIRING FOLLOW-UP

1. **Bulk HTTPException string → structured dict** — hundreds of routes; migrate incrementally.
2. **Slow query middleware** — needs Postgres/query-layer hooks if moving off Supabase REST.
3. **CSP tighten in production** — remove `unsafe-eval` when Next.js build allows.

## Final verdict

Before this pass, production failures surfaced as blank spinners, misleading zeros, and opaque 502s when the backend failed to boot. After this pass: security headers and CORS are explicit, sensitive POST routes are rate-limited, health checks expose DB/cache state for Railway, unhandled exceptions return a consistent JSON shape, the frontend handles 429/402/401, and schedulers remain isolated per tick. A production incident is now easier to trace via request IDs and structured logs, and abuse on auth/intelligence paths is throttled at the edge.
