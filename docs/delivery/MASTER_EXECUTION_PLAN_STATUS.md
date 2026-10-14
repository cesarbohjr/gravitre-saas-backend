# Master execution plan — cross-reference (2026-10-14)

**Repo baseline this pass:** `origin/main` @ `ce9c53b36` (docs only after security + automate merges).  
**Production backend `/health` (sampled):** `git_sha=b642dd156` @ `2026-10-14T05:22:17Z` — includes Release 1–3 security/governance merges (#401–#420); one commit behind current `main` (docs-only delta).

Legend: **COMPLETE** (code merged + evidence cited) · **PARTIAL** · **NOT RUN** (prod acceptance / migration apply) · **NOT STARTED** · **BLOCKED** (human gate)

---

## 1. Establish baseline

| Item | Status | Evidence / next action |
|------|--------|------------------------|
| Read AGENTS.md / engineering standards | COMPLETE | This session |
| Inspect main / open PRs | COMPLETE | Six Release 1 branches merged #401–#407; follow-ups #402,#408–#410; Release 2–3 stack #412–#420 |
| Recover Release 1 bundle/patches | **N/A** | Work already on `main`; remote `claude/*` tips are ancestors of `main` |
| Backend test baseline (8 provider-blocked failures) | PARTIAL | Environmental; preserve on any re-run — not re-executed this pass |
| Production Supabase migration apply state | NOT RUN | Migrations in repo `20261013005000`–`20261013060000`; prod apply requires explicit human approval per `AI_RELEASE_INSTRUCTIONS.md` |
| Railway / Vercel SHA alignment | PARTIAL | `/health` `b642dd156` matches merged automate PR; full pair check via new workflow (below) |

---

## 2. Release 1 — publish and validate six branches

### A. Publish six branches

| # | Branch | Migration | Merge | Status |
|---|--------|-----------|-------|--------|
| 1 | `claude/emergency-membership-and-route-client` | `20261013005000` | #401 | **COMPLETE** (code) |
| 2 | `claude/mcp-no-tenant-stdio` | — | #403 | **COMPLETE** (code) |
| 3 | `claude/governance-tables-member-write-lockdown` | `20261013010000` | #404 | **COMPLETE** (code) |
| 4 | `claude/relay-claims-only-handled-events` | `20261013020000` | #405 | **COMPLETE** (code) |
| 5 | `claude/retrieval-excludes-deleted-sources` | `20261013030000` | #406 | **COMPLETE** (code) |
| 6 | `claude/watcher-no-self-asserted-approval` | — | #407 | **COMPLETE** (code) |

### B. Scope preserved (code on main)

| Fix area | Status | Tests / notes |
|----------|--------|----------------|
| Emergency membership + route client | COMPLETE | `backend/tests/db/test_emergency_membership_lockdown_pg.py`; `apps/web/__tests__/api/route-client-no-service-role-fallback.test.ts` |
| MCP stdio block + remote validation | COMPLETE | `backend/tests/services/test_mcp_stdio_and_network_policy.py` (30 passed this pass) |
| Governance member-write lockdown | COMPLETE | Migration + merged PR #404 |
| Relay claims handled types only | COMPLETE | `DOMAIN_EVENT_RELAY_ENABLED` remains off by policy |
| Retrieval excludes dead sources | COMPLETE | Migration `20261013030000` |
| Watcher ignores caller approval | COMPLETE | Merged #407 |

### C. Migration / deployment sequence

| Step | Status | Evidence |
|------|--------|----------|
| Emergency migration first | PARTIAL | SQL in repo; prod apply NOT RUN |
| Ordered migrations through `20261013030000` | PARTIAL | Same |
| Relay stays off through deploy | COMPLETE | `scripts/railway_safety_vars.py` pins false; scheduler no-ops |
| Backend + web deploy of merged SHAs | PARTIAL | Railway `b642dd156`; Vercel gravitre.app HTTP 200 for hero assets |

### D. Production acceptance (Release 1 gate)

| Check | Status | Evidence |
|-------|--------|----------|
| Anonymous `/api/sessions?org_id=…` | PARTIAL | `2026-10-14` curl → HTTP 500 `permission denied for table organization_members` — no session rows returned (not ideal status code; no data leak) |
| Member / admin mutation matrix | NOT RUN | Requires dedicated test org + session |
| MCP stdio / SSRF | NOT RUN | Prod mutation not authorized in agent session |
| Relay pending outcomes | NOT RUN | Needs prod DB read |
| Retrieval dead sources | NOT RUN | Needs prod disconnect fixture |
| Watcher approval binding | NOT RUN | Needs prod write attempt |
| Normal signed-in surfaces | NOT RUN | No production SSO in this session |

Contract + script: `docs/delivery/release1-production-acceptance.md`, `scripts/verify-release1-production-smoke.py`.

### E. Additional security (separate PRs — not the six)

| Item | Status | PR |
|------|--------|-----|
| Settings-team DELETE / member removal | COMPLETE | #402 |
| Org settings field contract | COMPLETE | #409 + migration `20261013050000` |
| Users/agents member write contract | COMPLETE | #408 + `20261013040000` |
| Protected web route consumers audit | PARTIAL | Route client tests; no full `/api` crawl artifact |
| Privilege hygiene | COMPLETE | #410 + `20261013060000` |

**Release 1 gate:** **PARTIAL** — code merged and locally tested; production migration apply + authenticated acceptance **NOT RUN**.

---

## 3. Release 2 — governed execution and durable results

| Item | Status | PR / evidence |
|------|--------|----------------|
| Admin queue approval binding | COMPLETE | #413 |
| Capability policy at provider boundary (external send class) | COMPLETE | #412 |
| Write authority at invoke spine (shadow) | COMPLETE | #414 |
| No blind write retries / idempotency | COMPLETE | #415 |
| Background verification updates conversation | COMPLETE | #416 |
| Unified lifecycle envelope (chat/voice/ROI) | PARTIAL | Multiple prior execution-verification PRs; full envelope gate not re-proven live |
| Relay activation / backlog processing | **DEFERRED** | Fix shipped; activation explicitly not authorized |
| Release 2 acceptance (double approval, 502 no dup, etc.) | NOT RUN | Requires live provider fixtures |

---

## 4. Parallel track — conversation quality, intelligence, memory

| Item | Status | Notes |
|------|--------|-------|
| Single context artifact / turn trace | PARTIAL | Unified turn flags on in prod `/health` |
| Latency SLO measurement | PARTIAL | Scripts exist; targets not re-run this pass |
| WORK_STATE / context engine (#393) | COMPLETE (code) | #393 merged; live account data proof NOT RUN |
| Connector lineage / memory tagging | PARTIAL | #374 merged; legacy row disposition needs human choice |
| Document lineage / snapshot routes | PARTIAL | Incremental deletion #375; not full closure |

**Gate:** **NOT RUN**

---

## 5. Release 3 — Freshservice workflow and economics

| Item | Status | PR |
|------|--------|-----|
| Signed webhooks / replay safety | COMPLETE | #418 |
| Freshservice → workflow run | COMPLETE | #419 |
| HubSpot signature full URI | COMPLETE | #417 |
| Per-turn assistant metering | COMPLETE | `claude/assistant-metering-per-turn` → main |
| Run time and cost record | COMPLETE | #420 |
| End-to-end ticket update + read-back acceptance | NOT RUN | Needs pilot org + Freshservice secret |

---

## 6. Release 7 — model routing and pricing

| Item | Status |
|------|--------|
| Tier → catalog ID validation | PARTIAL (`backend/tests/services/test_llm_catalog.py`) |
| Adaptive routing behind flag | PARTIAL |
| Org/run budget caps | NOT STARTED |
| Packaging from measured economics | NOT STARTED |

---

## 7. Release 4 — MSP tenancy and external distribution

| Item | Status |
|------|--------|
| Client model decision (child org vs scoped resources) | **NOT STARTED** — requires documented product choice before migrations |
| Cross-client isolation in connectors/memory/billing | NOT STARTED |
| External Gravitre MCP + revocable API keys for workflows | NOT STARTED (org `api_keys` exists for settings; not workflow MCP endpoint) |
| Marketplace / vendor directory apps | PARTIAL (marketplace PRs open — out of master security track) |

---

## 8. Infrastructure / rollout contract

| Item | Status | Action |
|------|--------|--------|
| Production release verification workflow | PARTIAL | Added in PR branch `cursor/master-plan-execution-6b92` (from #424) |
| Migration governance CI | COMPLETE | #425 merged |
| Release queue runbook doc | PARTIAL | Updated in this PR |
| Supabase prod migration executor | BLOCKED | Human approval + staging per `AI_RELEASE_INSTRUCTIONS.md` |

---

## Recommended order from here

1. Human: apply Release 1 migrations on staging → prod in numeric order with preflight logs.  
2. Run `scripts/verify-release1-production-smoke.py` after deploy; run authenticated matrix with test org.  
3. Merge production verification workflow; watch `workflow_dispatch` after next `main` CI success.  
4. Release 2 live acceptance on staging connectors.  
5. Document Release 4 client model; then implement migrations (no schema until decision).  

Do **not** enable `DOMAIN_EVENT_RELAY_ENABLED` until handler idempotency and dry-run backlog review are explicitly approved.
