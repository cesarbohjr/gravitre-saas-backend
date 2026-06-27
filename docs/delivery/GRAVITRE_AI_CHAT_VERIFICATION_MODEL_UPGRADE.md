# Gravitre AI Chat Verification + Model Upgrade — 2026-06-07

Principal-engineer verification of all chat surfaces, gap fixes, and model-tier audit. Model configuration was reviewed per role; **no wholesale model ID swaps** were applied because current tiers already map to current-generation models.

---

## PHASE 1 — Live verification results

**Target:** `https://api.gravitre.app` (Railway backend) + `https://gravitre.app` (Vercel proxy)  
**Auth:** Service-role minted JWT via `backend/.env.operator.local` (smoke script)  
**Suite:** `npm run smoke:ai-production:report` + unauthenticated route probes

### Unauthenticated (confirmed this session)

| Check | Result | Notes |
|-------|--------|-------|
| `GET /health` | **200** | Backend healthy; `/api/health` returns **404** by design |
| `GET /api/admin/intelligence/outcomes` | **401** | Route exists |
| `GET /api/admin/optimization-suggestions` | **401** | Route exists (v10.1) |
| `POST .../apply-preview` | **401** | Route exists |
| `https://gravitre.app/api/admin/intelligence/outcomes` | **401** | Next.js → Railway proxy works |

### Authenticated smoke (2026-06-07 run)

| Step | Surface | Status | Detail |
|------|---------|--------|--------|
| health | Platform | **PASS** | `status: ok` |
| meson_interpret | Meson copilot | **PASS** | Plan returned |
| agents_list | Agent chat / operator | **PASS** | Agents reachable |
| agent_job | Agent jobs (async ReAct) | **PASS** | `completed`, `aiStatus=ok`, trace present |
| **assistant_chat** | **Assistant SSE** | **FAIL** | Missing `text-start` SSE event (STA-5) |
| workflow_dry_run | Workflow builder | *not reached* | Smoke aborted at assistant_chat |
| workflow_execute | Workflow runs | *not reached* | |
| workflow_digital_twin | Digital twin | *not reached* | |
| failure_predictions_scan | CS intelligence | *not reached* | |
| integration_health | Enterprise health | *not reached* | |
| role_packs | Marketplace | *not reached* | |
| federation_lists | Federation | *not reached* | |
| run_interrupt_routes | Run control | *not reached* | |
| agent_interrupt_channel | Agent interrupts | *not reached* | |
| meson_copilot_routes | Meson suggestions/alerts | *not reached* | |

**Prior baseline (2026-06-19):** Full 15/15 smoke pass including `assistant_chat: deltas=21 chars=109` (`docs/delivery/smoke-ai-production-latest.json`). Regression detected on 2026-06-07 before fix.

### Per-surface chat map (not all live-tested this session)

| Surface | Route / API | Live verified? | Intelligence stack |
|---------|-------------|----------------|-------------------|
| **Assistant chat** | `/assistant` → `POST /api/chat` → `/api/assistant/chat` | **Partial** — SSE contract failed until fix | AgentIntelligence + ReAct + RAG + org context + company intelligence block (if snapshot exists) |
| **Agent chat** | `/agents/[id]/chat` → same pipeline + `agent_id` | **Not live-tested** | Same + agent memory + persona |
| **Operator tasks** | `/operator` → `/api/operators/sessions/{id}/task` | **Not live-tested** | AgentIntelligence.execute_task (non-streaming) |
| **Agent jobs** | `/assignments` → `/api/agent-jobs` | **PASS** (smoke) | ReAct trace + tools |
| **Meson interpret** | Workflow builder | **PASS** (smoke) | MesonService + model_router |
| **Meson copilot** | Builder panel | *not reached* | Proxy routes only |
| **Daily briefing / org context** | `/api/assistant/daily-briefing`, `/org-context` | **Not live-tested** | OrgContextService |
| **Conversations** | `/api/conversations/*` | **Not live-tested** | Persistence layer |
| **Admin intelligence** | `/admin/intelligence` | **Unauthenticated only** (401) | Read APIs; admin JWT not exercised |
| **RAG / search hub** | `/chat` page, `/api/search`, `/api/rag/query` | **Not live-tested** | Separate from streaming assistant |

---

## PHASE 2 — Gaps found and fixed

### 1. Assistant chat SSE regression (most significant user-facing gap)

**Symptom:** Production smoke `assistant_chat` failed with `missing text-start SSE event (STA-5)`.

**Root cause:** `AgentIntelligence.execute_task_streaming()` could finish with `react_result.answer` populated but **no `text-start` / `text-delta` / `text-end` events** when ReAct returned a final answer without emitting `text_delta` chunks (e.g. tool-only iterations ending with content only on `react_result`). The UI and smoke contract require AI SDK text events before `finish`.

**Fix:** `backend/app/operators/agent_intelligence.py` — after the ReAct loop, if `full_content` is non-empty but `text_id` was never set, synthesize `text-start`, a single `text-delta`, and `text-end` before `AssistantStreamComplete`.

**Test:** `test_streaming_emits_text_events_when_react_returns_answer_only` in `tests/operators/test_agent_intelligence.py`.

### 2. Production health-check script pointed at wrong path

**Symptom:** `scripts/fix-prod-api-proxy.ps1` checked `gravitre.app/api/health` (always 404).

**Fix:** Check `https://api.gravitre.app/health` instead.

### 3. Company intelligence scheduler — **unverified in production (risk, not confirmed broken)**

**Hypothesis:** v1/v3/v6/v8 orchestrator output may be correct in code but **absent in chat** if `company_intelligence_scheduler` never persists snapshots.

**Facts from code:**

- Scheduler starts in-process on API boot (`main.py`) when `COMPANY_INTELLIGENCE_INTERVAL_SECONDS > 0` (default **28800s / 8h**), with **5-minute initial delay**.
- Chat reads snapshots via `get_context_for_prompt()` — returns **empty string** if no row or snapshot older than **36 hours**.
- Disabling env (`COMPANY_INTELLIGENCE_INTERVAL_SECONDS=0`) would silently skip all org learning.

**Status:** **Not confirmed live** — Railway env/logs were not inspected this session. Chat still responds without the block; intelligence enrichment may be missing rather than chat being down.

**Recommended follow-up:** Confirm Railway env ≠ 0; inspect logs for `company_intelligence_tick` / `company_intelligence_org_completed`; check `company_intelligence_snapshots` (or equivalent table) for recent `updated_at`.

---

## PHASE 3 — Model audit and upgrade

### 3.3 — Tier routing still makes sense

The four assistant **modes** (`fast` / `standard` / `reasoning` / `agent`) map to different **TaskType → complexity tier → failover order**, not just different model strings:

| Mode | Default model | TaskType | Complexity | Failover bias (`auto`) |
|------|---------------|----------|------------|-------------------------|
| fast | gpt-5.4-mini | summarization | **low** | OpenAI first (cheapest) |
| standard | gpt-5.5 | rag_answering | **medium** | OpenAI first |
| reasoning | gpt-5.5 | decision_reasoning | **high** | **Anthropic first** |
| agent | gpt-5.5 | workflow_planning | **high** | **Anthropic first** |

**Conclusion:** Even though `standard` / `reasoning` / `agent` share `gpt-5.5` as the OpenAI default, tier boundaries remain meaningful via **TaskType**, **tool iteration limits** (`MODE_CONFIG`), and **provider failover order**. No tier restructuring required.

### Current models, per role

| Role / tier | OpenAI | Anthropic | Gemini | Verdict |
|-------------|--------|-----------|--------|---------|
| **Low** (classification, intent, summarization) | gpt-5.4-mini | claude-haiku-4-5-20251001 | gemini-2.5-flash | **Fine as-is** — already cost-optimized |
| **Medium** (RAG, content gen, optimization) | gpt-5.5 | claude-sonnet-4-6 | gemini-2.5-pro | **Fine as-is** — current flagship tier |
| **High** (workflow planning, decision, debate) | gpt-5.5 | claude-sonnet-4-6 | gemini-2.5-pro | **Fine as-is** — separation is failover + task type, not a stale model |
| **Assistant fast mode** | gpt-5.4-mini | (via override) | (via override) | **Fine as-is** |
| **Assistant standard/reasoning/agent** | gpt-5.5 | (via override) | (via override) | **Fine as-is** |
| **Embeddings** | text-embedding-3-small | — | — | **Fine as-is** — not chat |
| **Gemini failover only** | — | — | 2.5-flash / 2.5-pro | **No upgrade** — Gemini 3.x would require adapter `supported_models`, billing multipliers, and live API verification; tertiary failover only |

### Recommended changes (with justification)

| Role | Recommend upgrade? | Justification |
|------|-------------------|---------------|
| OpenAI low/medium/high | **No** | gpt-5.4-mini / gpt-5.5 are already the configured current generation; pricing table verified May 2026 in `model_router.py` |
| Anthropic low/medium/high | **No** | Haiku 4.5 + Sonnet 4.6 are current; high-tier Anthropic-first failover already rewards reasoning workloads |
| Gemini failover | **No (defer)** | Would not improve primary-path chat; needs SDK + billing validation before swap |
| MODE_CONFIG / tier count | **No** | fast vs standard vs reasoning vs agent still differ materially in tools and iterations |

### 3.4 — Implemented model configuration changes

**None.** This was an intentional config-only review — existing `MODEL_TIERS` + `model_router` abstraction is correct; no identifier changes met the bar for justified upgrade.

### 3.5 — Tests added

| Test | File |
|------|------|
| `test_model_router_returns_updated_model_per_tier` | `tests/services/test_model_router.py` |
| `test_existing_tier_routing_logic_unchanged_in_structure` | `tests/services/test_model_router.py` |
| `test_chat_surfaces_still_function_with_new_models` | `tests/test_assistant_unified_pipeline.py` |
| `test_streaming_emits_text_events_when_react_returns_answer_only` | `tests/operators/test_agent_intelligence.py` |

---

## PHASE 4 — Post-upgrade re-verification

**Model IDs unchanged** — Phase 4 re-run is against the **SSE fix**, not new models.

| Check | Result |
|-------|--------|
| Targeted pytest (model router + assistant pipeline + streaming fix) | **21 passed** |
| Full backend pytest | **1501 passed**, **2 pre-existing failures** (unchanged): HubSpot OAuth scope test, Slack invoke test |
| Production smoke re-run | **Pending deploy** — fix is local until Railway redeploy |

After deploy, re-run:

```bash
npm run smoke:ai-production:report
```

---

## pytest summary

- **1501 passed** (after this session's tests)
- **2 failed** (pre-existing, unrelated): `test_hubspot_authorize_url_contains_params`, `test_invoke_slack_success`

---

## Final verdict

**Before this session:** Platform health, agent jobs, and Meson interpret were **confirmed working live** with authenticated smoke. Assistant chat had **regressed** since the 2026-06-19 full smoke pass — SSE text events could be absent when ReAct supplied an answer without streaming deltas. Admin intelligence routes exist (401) but were **not** verified with an admin JWT response body. Company intelligence enrichment in chat prompts is **code-correct but production scheduler execution unverified** — if the scheduler never runs, orchestrator output would be absent in practice despite v8–v11 code being deployed.

**Fixed this session:** Assistant streaming SSE contract restored for answer-only ReAct completions; production proxy health script corrected.

**Model upgrades:** **None applied.** Per-role audit found OpenAI and Anthropic tiers already on current-generation IDs; tier routing architecture remains sound; Gemini failover upgrade deferred as low-impact and unvalidated.

**Honest confidence statement:** Only surfaces exercised with a **real authenticated request** in this session are listed as confirmed in Phase 1. Surfaces marked "not live-tested" or "pending deploy" should not be treated as production-verified until smoke passes end-to-end after Railway picks up the SSE fix.
