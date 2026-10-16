# Master plan — what “fully built” means (2026-10-14)

This document separates **code complete** from **production capable** (acceptance + operator gates).

## Code complete on `cursor/full-release-implementation-6b92`

| Release | Delivered in code | Still partial / not started |
|---------|-------------------|-----------------------------|
| **R1** | Six-pack + follow-ups on `main` | Full authenticated acceptance matrix; Vercel key audit; incident review |
| **R2** | Approval scope (+ audit fixes), atomic idempotency **claim** (flag default off), lifecycle persist only, write authority config | Enforce mode; pg concurrency tests; lifecycle UI/voice consumers; relay dry-run |
| **R3** | Event-trigger queue, turn_id attribution, Freshservice trigger UI, automation actor | HubSpot test delivery; Freshservice prod E2E; metering reconciliation / ROI |
| **R4** | Option A scaffold: `parent_org_id`, app resolver, RLS parent path | Client switcher, external MCP API, R4 acceptance |
| **Parallel track** | — | Turn tracing, latency proof, memory disposition, resurfacing routes |
| **R7** | — | Budget caps, adaptive routing |

## Production gates (cannot be closed by code alone)

1. `docs/delivery/release1-production-acceptance.md` — **NOT RUN** without test-org credentials.
2. `DOMAIN_EVENT_RELAY_ENABLED` — stay **false** until backlog dry-run approved on staging.
3. Migrations `20261014060000`, `20261014100000`, `20261014110000` — batch apply per runbook; not applied in this agent session.
4. Deploy pair — reconcile Vercel web SHA vs Railway `git_sha` before sign-off.

## Local engineering evidence

Run: `python3 scripts/verify-release-engineering-gates.py` → `docs/delivery/release-engineering-gates.json`.
