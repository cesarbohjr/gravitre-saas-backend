# Gravitre routing & decision map (standing reference)

**Status:** Diagnosis only — no product fixes in this pass  
**Product name:** Gravitre  
**Evidence bar:** Every claim is **CONFIRMED** (code path, unit probe, or cited test) or **UNKNOWN** (not traced). No “probably fine.”  
**Last full audit:** 2026-08-05  
**Update rule:** Refresh this document whenever unified-turn fallthrough reasons, `_MESSAGE_TOOL_SSE_PATTERNS`, pack-common regexes, orchestration intent rules, catalog schema standards, or entry-point wiring change.

---

## Executive verdict

There is still **no single deterministic router**. Chat LIVE (`apply_unified_turn_live`) is the densest decision surface, but workflows, agent jobs, and most extension actions **never enter it**. Routing remains a stack of: feature flags → pending-family resume → LLM shadow outcome → pack-common regex → classical-defer regex bag → orchestration heuristics → classical ReAct / `ChatActionMapper`. Three production bugs this program already hit (pending-family silent bypass, `parameter_ledger` overwrite, TRY-chip fabricated plan) are instances of that stack, not isolated edge cases.

**Catalog size (CONFIRMED 2026-08-05):** 687 `ActionSpec` rows across 77 vendors (`all_catalog_action_specs()`).

---

## Naming flag — “Gravitree” vs “Gravitre” (do not rename in this pass)

**CONFIRMED:** ~199 files match `Gravitree|gravitree` (repo scan 2026-08-05). Highest-density product surfaces include:

| Area | Examples |
|------|----------|
| Extension | `apps/extension/content/shared.js`, `manifest.json`, store listing |
| Web | `apps/web/lib/connectors.ts`, `components/gravitre/gravitree-loader.tsx`, docs MDX |
| Backend | `extension_bridge_service.py`, `auth_mode.py`, voice/module-d docs |
| Delivery artifacts | many `docs/delivery/*` JSON/MD |

**Follow-up (separate, reviewed change):** deliberate rename plan for user-facing strings + intentional code identifiers (`gravitree_voice`, headers, component filenames). **Do not** bundle renames into routing fixes.

---

# Part A — Intake: every way a message enters

| # | Entry point | First code that touches the message | Pre-reasoning work | Reaches `apply_unified_turn_live`? |
|---|-------------|-------------------------------------|--------------------|-----------------------------------|
| A1 | **Main chat (typed)** | `apps/web/app/api/chat/route.ts` → `POST ${API}/api/assistant/chat` → `backend/app/routers/assistant.py` → `AgentIntelligence.execute_task_streaming` | Auth/org, conversation load, classification/enrichments, intelligence mode | **YES** when `unified_turn_live_enabled` |
| A2 | **TRY chips / suggested prompts** | `ai-landing.tsx` / `ai-workspace.tsx` call `onExampleSelect(text)` → same `/api/chat` path as A1. Prompts from `AI_EXAMPLE_PROMPTS` in `ai-mode-config.ts` (MSP Clay→HubSpot, Drive summarize, HubSpot+Slack, failed runs, pipeline, Asana). Welcome roles use `welcome-flow.ts` → `/ai?prompt=` | Chip text is submitted **as the user message** (no separate pack id). Normalization is whatever A1 does. | **YES** (same as A1) |
| A3 | **Workflow canvas — manual / schedule / webhook** | Workflow run APIs → `ExecutionService` / `_execute_workflow_with_context` / `workflows/execute.py` | Typed step graph from stored workflow definition; not chat NL routing | **NO** — plan is **retrieved** from workflow definition |
| A4 | **Agent assignments / agent jobs** | `agent_jobs` queue + `operators/agent_jobs.py` worker → governed `ModelRouter` | Durable job payload; not unified-turn live | **NO** for queue worker path. Agent **chat UI** (`agents/[id]/chat`) uses `/api/chat` → **YES** (A1) |
| A5 | **Browser extension** | `backend/app/routers/extension.py` | See sub-rows | Mixed |
| A5a | Extension enrich | `POST /api/extension/enrich` → `enrich_from_page_context` | Page URL/context; connector inventory; **no** unified turn | **NO** |
| A5b | Extension workflow execute | `POST /api/extension/workflows/execute` → stage/confirm → `_execute_workflow_with_context` | Approve-first token; stored workflow | **NO** |
| A5c | Extension actions | `POST /api/extension/actions/execute` → `execute_extension_action` | Direct invoke + confirm token | **NO** |
| A5d | Extension quick chat | `POST /api/extension/chat` → `chat_from_extension` → `execute_task_streaming` | Page context fenced as DATA; may hand off to `/ai?c=` | **YES** (same LIVE gate as A1) |
| A6 | **API integrations / webhooks** | e.g. `/api/webhooks/hubspot`, Salesforce, PagerDuty, Stripe | Event → connector/workflow handlers; billing paths separate | **UNKNOWN** per-webhook whether any path can call chat LIVE (not traced end-to-end this pass). Stripe is billing, not NL routing. |
| A7 | **Assistant API direct** | `POST /api/assistant/chat` (same as A1 without Next proxy) | Same as A1 | **YES** |

**CONFIRMED first LIVE gate (A1/A2/A5d):** `apply_unified_turn_live` in `unified_turn_reasoning_service.py` — if `unified_turn_live_enabled` is false → `fallthrough_reason=live_disabled`, return `None` → classical.

---

# Part B — Complete routing / decision inventory

## B.1 Live fallthrough reasons (`apply_unified_turn_live` → `None` or skip)

| Reason code | Condition (CONFIRMED) | Returns | Tests |
|-------------|----------------------|---------|-------|
| `live_disabled` | `unified_turn_live_enabled=false` | `None` | Structural (flag path); live battery env-dependent |
| `pending_family_classical_resume` | `has_pending_family(task_state)` and pending resolver returned no LIVE reply (confirm/reject/modify/slot_answer) | `None` (was silent before audit fix) | **COVERED** — `test_unified_turn_reasoning.py` asserts reason |
| `outcome_skipped` / `outcome_error` | Shadow result `outcome_kind` in `{skipped,error}` | `None` | Partial unit coverage |
| `defer_classical_tool_sse` | Text kind + `message_requires_classical_tool_sse(message)` and not intercepted by pack-common / live orch staging | `None` | **COVERED** for pattern hits + MSP TRY exception |
| `defer_connector_tool_proposal` | Dead branch for defer naming — `connector_tool_proposal` now **forces** `should_defer…=False` | N/A (kept for audit string if kind matched old path) | Historical bug documented in code comment |
| `violates_no_pending_hold` | LIVE text claims hold while no pending | `None` | **COVERED** |
| `false_connector_disconnect_claim` | LIVE claims disconnect while connectors connected | `None` | **COVERED** |
| `write_plan_unavailable` | Write proposal but `plan_from_react_tool_call` is None or no `conversation_id` | `None` | Partial |
| `read_tool_classical` | Tool proposal is read (not approval write) | `None` → classical governed read | Partial |
| `unhandled_kind_{kind}` | Outcome kind not mapped to LIVE stop | `None` | Catch-all — **UNTESTED** as exhaustive matrix |

**Order inside LIVE (CONFIRMED, critical):**

1. Flag gate  
2. Channel override / meta capability / pending LIVE resolvers  
3. **Pending-family classical resume** (explicit fallthrough)  
4. `run_unified_turn_shadow`  
5. **Pack-common list create** (stage `awaiting_confirm`)  
6. **Pack-common MSP Clay→HubSpot enrich** (stage `create_workflow`)  
7. Classical defer check → if would defer **and** `is_orchestration_intent` → **LIVE orchestration staging** (anti–TRY-chip invent)  
8. Else bare defer → classical  
9. Text kinds / write approval / read fallthrough / unhandled  

## B.2 `_MESSAGE_TOOL_SSE_PATTERNS` (exact bag)

Source: `unified_turn_classical_fallback.py` (16 patterns). Match ⇒ classical tool SSE needed **unless** MSP enrich pack-common matches first.

| # | Pattern | Risk |
|---|---------|------|
| 1 | `\bconnectors?\b.*\bconnected\b` | Broad “connectors…connected” |
| 2 | `\bwhat connectors\b` | Exact-ish |
| 3 | `\bgetconnectorstatus\b` | Probe |
| 4 | `\brefund policy\b` | KB probe |
| 5 | `\binternal (?:org )?knowledge\b` | KB |
| 6 | `\bfictional subsidiary\b` | Probe |
| 7 | `\bzephyr dynamics\b` | Probe |
| 8 | `\boutline\b.*\bplan\b.*\btools?\b` | Wave 6–7 |
| 9 | `\bplan\b.*\bbefore\b.*\btools?\b` | Wave 6–7 |
| 10 | `\bcontact lists?\b` | **HIGH** — any “contact list” defer |
| 11 | `\bapollo\b` | **HIGH** — any Apollo mention defer |
| 12 | `\bslack\b` | **HIGH** — any Slack mention defer |
| 13 | `\bpost (?:a )?(?:slack )?message\b` | Slack write |
| 14 | `\bcreate an? apollo contact list\b` | Narrow create |
| 15 | `\bsearchknowledgebase\b` | Probe |
| 16 | `\bknowledge base\b` | KB |

**MSP exception (CONFIRMED):** `message_requires_classical_tool_sse` returns `False` if `try_pack_common_msp_enrich_workflow_plan(text)` hits — because TRY prompt contains “Apollo” + “contact list”.

## B.3 Classical / legacy reachability by entry point

| Entry | Classical ReAct / governed chat | `ChatActionMapper` | Orchestration service | Stored workflow engine |
|-------|----------------------------------|--------------------|-----------------------|------------------------|
| A1/A2 chat + TRY | YES on every LIVE `None` | YES inside classical + pack-common list create | YES (LIVE-before-defer + classical) | Via staged `create_workflow` |
| A3 workflows | NO | NO | NO | YES (definition) |
| A4 agent jobs | UNKNOWN (ModelRouter path; not unified LIVE) | UNKNOWN | UNKNOWN | Possible via steps |
| A5a–c extension | NO | Partial (enrich suggestions) | NO | YES on workflow execute |
| A5d extension chat | YES (same as A1) | YES | YES | Possible |

## B.4 Plan GENERATED vs RETRIEVED

| Path | Generate or retrieve? | Can fabricate ungrounded steps? |
|------|----------------------|---------------------------------|
| Pack-common MSP enrich | **Retrieve-ish** — stages seeded pack workflow slug/name/goal constants | Low for structure; **does not check pack install** (only connected clay/hubspot/apollo) — CONFIRMED |
| Pack-common list create | **Hybrid** — `ChatActionMapper` + pack defaults | Medium if mapper wrong tool |
| LIVE orchestration before defer | **Generated** via `ChatOrchestrationService.process_turn` + mapper per segment | **YES** — this class invented wrong Search-contacts steps pre-fix |
| Classical ReAct after defer | **Generated** | **YES** |
| Canvas / extension workflow execute | **Retrieved** from workflow row | No invent of steps (params only) |
| Agent job ModelRouter | **Generated** (model + tools) | **YES** — UNKNOWN how often |

## B.5 Pack / intent matching mechanisms

| Mechanism | Type | Embedding? | Notes |
|-----------|------|------------|-------|
| `_MSP_CLAY_HUBSPOT_ENRICH` | Regex windows **0–200 / 0–120** chars between keywords | No | Widened after ~80-char gap bug; TRY prompt ~106 chars enrich→HubSpot |
| `_NAMED_LIST` | Capture name `{0,80}` chars | No | Fragile name length |
| `_OMIT_NAME_LIST_CREATE` / `LIST_CREATE_INTENT` | Verb + ≤3 adj tokens + list/group/segment | No | “set up a list” / “spin up…list” miss |
| `_MSP_PACK_HINT` | `\bmsp|prospecting|…\b` | No | |
| `ChatOrchestrationService.is_orchestration_intent` | Multi-integration mention, segment split, `MULTI_STEP_HINT`, `REPORT_ORCHESTRATION`, `MULTI_ACTION` | No | `len(text) < 12` ⇒ false |
| `ChatActionMapper` | Verb/object/vendor scoring over execution matrix | No | Still active — **not** a dead remnant |
| Unified-turn shadow | LLM structured outcome | N/A | Reasoning layer (flexible by design) |
| Catalog keyword/embedding narrowing | Latency path for tool subset | Embedding used for **tool shortlist**, not pack-intent match | CONFIRMED distinction |

**Pack install gate:** `PACK_IDS` is metadata in catalog helpers; `try_pack_common_msp_enrich_workflow_plan` / list create **do not** require pack installation — only connector connectivity. **CONFIRMED gap.**

## B.6 Character / window limits (named fragile rules)

| Rule | Limit | Location | Status |
|------|-------|----------|--------|
| MSP enrich clay↔hubspot windows | 120–200 `[\s\S]` | `pack_common_intent_defaults.py` | Fixed from prior ~80 gap for TRY; still windowed |
| Named list capture | 80 chars | `_NAMED_LIST` | Active |
| Trailing list name | 60 chars | trail regex | Active |
| `FROM_ENTITY` | 80 chars | `chat_action_mapper.py` | Active |
| Google Ads structure | 80 / 200 | `GOOGLE_ADS_STRUCTURE_INTENT` | Active |
| Orchestration min length | 12 chars | `is_orchestration_intent` | Active |
| Pending classifier subject preview | `[:80]` display only | `pending_reply_classifier.py` | Not a match window |

## B.7 Decision-point test coverage matrix

| Decision | Automated assertion? | What it actually asserts |
|----------|---------------------|--------------------------|
| `pending_family_classical_resume` | COVERED | Reason string + audit payload |
| MSP TRY chip LIVE path | COVERED | `test_unified_turn_msp_try_chip_live_path.py`, pack-common match, defer=false |
| HubSpot+Slack TRY defer/orch | COVERED | `test_unified_turn_hubspot_slack_try_chip_live_path.py` — defer true for that chip |
| Classical SSE pattern bag | PARTIAL | A few connector/KB strings — **not** exhaustive 16-pattern matrix |
| List-create verb synonyms | PARTIAL | Happy paths; “set up” / “spin up” **UNTESTED** (probe MISS) |
| Pack install required | UNTESTED | No assert that pack must be installed |
| All `unhandled_kind_*` | UNTESTED | No enum exhaustiveness test |
| Extension chat → LIVE | UNKNOWN | Not traced in this pass with live HTTP |
| Agent job routing vs chat | UNKNOWN | Code shows ModelRouter worker ≠ LIVE |
| NL variance for packs | PARTIAL | Unit probe this audit (below); not CI battery |

---

# Part C — Natural language → action (variance probe)

**Method:** Local deterministic probe `scripts/probe-routing-decision-map.py` against pack-common + defer + orch + mapper (2026-08-05). **Not** a live prod chat battery — label **CONFIRMED (unit)** / do not upgrade to production PASS.

## C.1 MSP Clay→HubSpot enrich (same intent, 8 phrasings)

| Phrasing | Pack HIT | Classical defer | Orch intent |
|----------|----------|-----------------|-------------|
| Exact AI Chat TRY prompt | HIT | False | True |
| “enrich my apollo MSP Prospects…Clay…HubSpot MSPs” | HIT | False | True |
| “Clay enrich Apollo list…HubSpot…” | HIT | False | True |
| “take MSP Prospects from Apollo, enrich via Clay…” | HIT | False | True |
| “run clay enrichment on the apollo msp prospects…hubspot” | HIT | False | True |
| “clay to enrich contacts then hubspot sync for msp prospects” | HIT | False | True |
| “enrich contacts with clay then add to hubspot” | HIT | False | True |
| “use clay enrichment for my outreach list into hubspot” | **MISS** | False | False |

**Spread (unit):** 7/8 HIT. Failure mode: soft “outreach list” without clay↔hubspot window + MSP anchors.

## C.2 List create (8 phrasings)

| Phrasing | HIT/MISS |
|----------|----------|
| Create HubSpot static list named MSPs | HIT |
| make me a new hubspot list called MSPs | HIT |
| add a contact list MSPs in hubspot | HIT |
| new apollo contact list for msp outreach | HIT |
| can you set up a list MSPs on hubspot? | **MISS** (`set up` outside `LIST_CREATE_INTENT`) |
| I want a hubspot segment named MSPs | **MISS** (no create/new/add/make) |
| create list | **MISS** (too thin / mapper) |
| spin up an outreach list in apollo for MSPs | **MISS** (`spin up` outside verbs) |

**Spread (unit):** 4/8 HIT. **Specificity still required:** create/new/add/make + list/group/segment within 3 adjective tokens.

## C.3 HubSpot + Slack multi-step (5 phrasings)

All five: `orch=True`, `defer=True` (Slack pattern). Relies on LIVE-orchestration-before-defer (post TRY-chip class fix). **UNKNOWN** without LIVE integration whether staged plan steps are correct for each phrasing.

## C.4 Named fragile risks (even without a live bug yet)

1. **RISK-DEFER-APOLLO-SLACK** — Any message containing `\bapollo\b` or `\bslack\b` forces classical defer for text kinds unless pack-common MSP or live orch staging wins.  
2. **RISK-LIST-VERB-CLOSED** — `LIST_CREATE_INTENT` closed verb set; natural “set up / spin up / I want a segment” miss.  
3. **RISK-WINDOWED-PACK** — MSP enrich still `[\s\S]{0,N}` windows; long asides between clay/enrich/hubspot can miss.  
4. **RISK-ORCH-GENERATE** — Orchestration still **generates** steps via mapper; LIVE staging prevents bare classical invent but does not guarantee correct tools.  
5. **RISK-MAPPER-WRONG-TOOL** — Probe: “search GitHub issues…” → `github_pulls_list`; “list ClickUp tasks” → `clickup_spaces_list`.  
6. **RISK-PACK-NO-INSTALL-CHECK** — Pack-common fires without pack install.  
7. **RISK-80-NAME-CAP** — List name capture 80 chars; long quoted names truncate/fail.

---

# Part D — Execution & completion verification

## D.1 Shared write-effect model (CONFIRMED)

`classify_write_effect` / `has_effect_proof` in `connector_outcome_effects.py`:

- Mutating success **without** vendor id / vendor URL → effect `unknown` (not `created`).  
- Explicit `created` without proof → downgraded to `unknown`.  
- Async markers → `accepted_async`.  
- Chat orch + workflow execute call `finalize_execution_outcome` + `VerifiedOutputRef`.

BusinessOutcome projector: does **not** claim `module_a_verified_output` for unproven creates (code comment CONFIRMED).

## D.2 By action class

| Class | How “complete” is decided | Gap? |
|-------|---------------------------|------|
| Connector **read** | Tool/HTTP success + returned payload shape | No vendor state re-fetch required — acceptable for reads |
| Connector **write** (chat/LIVE) | HTTP/tool success **plus** effect proof for “created”; else `unknown` / unproven | **PARTIAL** — proof is presence of ids/URLs in response, **not** always a follow-up GET that list was populated (#184 class) |
| Pack multi-step / workflow | Step engine success + Module A outcome finalize | Per-step same as above; **end-state population** not universally re-verified |
| Extension enrich | Suggestion matches — not a write complete | N/A |
| Agent jobs | ModelRouter/tool results | **UNKNOWN** whether all paths call `finalize_execution_outcome` |

## D.3 Consistency across entry points

| Entry | Uses effect honesty / BusinessOutcome? |
|-------|----------------------------------------|
| Chat / TRY / extension chat | CONFIRMED converge on finalize + effect classify for connector writes |
| Workflow engine | CONFIRMED `finalize_execution_outcome` in execute path |
| Extension workflow confirm | Same engine path — CONFIRMED |
| Extension one-shot actions | CONFIRMED via `execute_extension_action` (assumes shared finalize — **spot-check recommended**) |
| Agent job worker | **UNKNOWN** |

**Named gap D-GAP-POPULATION:** “List created” with `list_id` proof ≠ “list contains the expected members.” That is inferred completion, not BusinessOutcome verified-output against vendor membership.

---

# Part E — UI / UX honesty

## E.1 Outcomes surface (CONFIRMED)

`business-outcome-view.tsx` maps:

- `verification.verified === true` → **Verified**  
- failed → **Failed**  
- else → **Not verified** / unproven (explicitly not a green success)

UI does **not** invent Verified without DTO flag. **CONFIRMED** for this component.

## E.2 Chat / run / extension

| Surface | Can show confident “completed” when Part D is weak? | Evidence |
|---------|-----------------------------------------------------|----------|
| BusinessOutcome | Unproven labeled — honest | Code |
| Chat progress “Completed:” step labels | **UNKNOWN** — labels mean step finished in run timeline, not vendor re-verify | Needs UX copy audit |
| Run detail | **UNKNOWN** without full UI trace this pass | |
| Extension overlay | Voice notes / handoff; enrich stub still says “Gravitree” | Naming + honesty UNKNOWN for write confirms |

## E.3 Error actionability (Module D voice)

| Path | Specific next step? |
|------|---------------------|
| Write missing params / approval | CONFIRMED — clarify or “Reply **yes**…” copy from pack-common / write gate |
| Classical tool failure | PARTIAL — `tool_error_messages` exists; **UNKNOWN** coverage for all connectors |
| Extension disconnected | Returns connect CTA (copy still “Gravitree”) | Recoverable |
| Generic 500 from extension chat | `detail=str(exc)[:500]` — **weak** Module D compliance |

---

# Part F — Prioritized findings & closure plan

Ranked by severity × breadth × structural fix value.

| Rank | ID | Status | Finding | Severity | Breadth | Fix shape |
|------|----|--------|---------|----------|---------|-----------|
| 1 | F1 | **CLOSED (Phase 1, 2026-08-05)** — `retrieve_plan_gate.py` hard gate before shadow / orch `_build_plan` / ReAct; ambiguous → clarify | Dual pipeline invents plans when pack miss | **Silent user-facing** | A1/A2/A5d | Structural retrieve-before-generate |
| 2 | F2 | **CLOSED (Phase 1)** — removed bare apollo/slack/contact-list/knowledge-base; defer via `needs_tool_sse` + reduced safety net | Bare vendor defer patterns | High | Any Apollo/Slack utterance | Structured LIVE signal |
| 3 | F3 | **CLOSED (Phase 1)** — C.2 probe **8/8 HIT** (unit); verbs set up/spin up/want/need; name capture 150 | List-create verb gaps | High | Pack TRY + NL list creates | Verb expansion |
| 4 | F4 | **CLOSED (Phase 1)** — object-noun scoring + confusable veto; github issues / clickup tasks / SF contacts correct; G.1 9/10 HIT (linear catalog gap) | Mapper wrong-tool class | High | 77-vendor mapper | Noun-weighted scoring |
| 5 | F5 | **CLOSED (Phase 2)** — `require_pack_install=True` on retrieve gate + classical MSP intercept; missing pack → honest clarify + Marketplace CTA | Pack-common ignores pack install | Medium–High | MSP/Prospecting | Install gate |
| 6 | F6 | **CLOSED (Phase 2)** — `collection_population_verify.py` follow-up / membership proof; chat + extension + existing workflow honesty; empty → partial_success / accepted_async | Write completion without membership verify | Medium | Writes/lists | Population verify |
| 7 | F7 | **CLOSED (Phase 5)** — see `routing-map-phase5-f7-traces.md`; webhooks not NL-routed; agent_jobs ModelRouter text named exception | Agent jobs / webhooks outside map | Medium | Non-chat | Traced contracts |
| 8 | F8 | **CLOSED (Phase 4)** — schema standard doc + CI lint; when/why on 100% catalog via builder; write→destructive; MCP hints derived; id aliases | Catalog schema quality | High for new connectors | 689 actions | Standard + lint |
| 9 | F9 | **OUT OF SCOPE** this program | Gravitree naming debt | Brand | Cross-cutting | Separate PR series |
| 10 | F10 | **CLOSED (Phase 3)** — `unified_turn_fallthrough.py` enum + AST CI; defer pattern ± matrix; NL variance + withhold-fabrication battery | Exhaustive fallthrough / pattern CI | Medium | LIVE | Enum + CI batteries |

### Sequenced closure plan (recommended)

1. **Freeze the decision table** — promote this doc’s B.1–B.2 into a code-owned enum + dashboard (golden signals already counts `fallthrough_reason`).  
2. **Retrieve-before-generate** — any message matching pack workflow / installed pack common intent must stage the seeded plan; classical generate only if retrieve misses.  
3. **Retire keyword defer bag** — defer only on structured LIVE tags (`needs_tool_sse`, probe ids), not `\bapollo\b`.  
4. **NL variance CI** — expand pack + list-create batteries beyond exact TRY strings (use C.1–C.2 as seed).  
5. **Verified population checks** for list/sync writes (D-GAP-POPULATION).  
6. **Schema standard adoption** (G.2) as required PR checklist + lint.  
7. **Gravitree rename** as its own PR series.

---

# Part G — Connector generalization & schema catalogue

## Research grounding (adopted as audit rubric)

JSON Schema **2020-12** is the converged standard behind OpenAI structured outputs, Anthropic tool use, and MCP (2026-07-28). Tool-selection quality is dominated by schema/description discipline.

## G.1 Zero connector-specific code vs legacy

| Path | Zero connector-specific? | Evidence |
|------|--------------------------|----------|
| Unified-turn LIVE tool proposal from catalog schemas | **Aspirational / PARTIAL** | LIVE still falls through reads; writes use registry + `evaluate_connector_tool_proposal` |
| `ChatActionMapper` + execution matrix | **NO** — per-matrix scoring, aliases, Google Ads regex | Active in classical + pack list create |
| Pack-common regex | **NO** — MSP/Prospecting specific | |
| Defer pattern bag | **NO** — vendor keywords | |
| Workflow typed steps | N/A — not NL | |

### Untested-connector NL probe (mapper only, unit)

| Vendor | Utterance | Result |
|--------|-----------|--------|
| asana | create task… | HIT `asana_tasks_create` |
| clickup | list open tasks | HIT **`clickup_spaces_list`** (wrong class) |
| github | search issues… | HIT **`github_pulls_list`** (wrong class) |
| notion | create page… | HIT `notion_pages_create` |
| airtable | find records… | HIT `airtable_records_list` |
| monday | create item… | HIT `monday_items_create` |
| linear | create issue… | **MISS** |
| zendesk | list tickets… | HIT `zendesk_tickets_list` |
| salesforce | find contacts… | HIT `salesforce_leads_search` (contact≠lead risk) |
| intercom | search conversations… | HIT `intercom_conversations_list` |

**Verdict:** “Any properly-schemed connector works automatically via unified-turn” is **NOT CONFIRMED** today. Mapper can fire without LIVE; wrong-tool hits are real in unit probe. Full LIVE pass/fail for these vendors: **UNKNOWN** (not run in prod this pass).

## G.2 Seven principles (draft enforced standard)

Adopt as checklist for every new/changed `ActionSpec`:

1. **NAMING** — `vendor.resource.verb` (≥3 segments).  
2. **DESCRIPTION QUALITY** — when/why to use, not only mechanical what.  
3. **FLAT, ATOMIC SCHEMAS** — one purpose; avoid mega-tools/flags.  
4. **JSON SCHEMA CONFORMANCE** — enums, required, types (2020-12).  
5. **TOKEN BUDGET** — concise descriptions; rely on keyword/embedding narrowing for the prompt subset.  
6. **ANNOTATIONS** — `kind` + `destructive` / `requires_approval` must be the **same** signal as write authority (no parallel hint system).  
7. **OUTPUT STRUCTURING** — parseable results + verified-output fields for writes.

## G.3 Catalog scores (CONFIRMED 2026-08-05 probe)

| Metric | Value |
|--------|-------|
| Total actions | **687** |
| Vendors | **77** |
| kind read / write / advanced | 271 / 185 / 231 |
| tier v1–v4 | 263 / 189 / 200 / 35 |
| Description length 20–59 chars | **98.5%** |
| Description length ≥60 | 1.5% |
| Descriptions with when/why cues (`when `, `use this`, …) | **0%** |
| Inline `input_schema.properties` | **0** props counted (98.3% empty inline schema field) |
| `action_parameters` coverage | **63 / 687 (9.2%)** |
| `destructive=true` | 197 |
| writes not marked destructive | **6** |
| `requires_approval` | 24 (writes with approval: 6) |
| Names with &lt;3 dot segments | **27** (e.g. `email.send`, `slack.post_message`, `salesforce.query`, Segment `*.identify`) |

**Interpretation:** Structural CI may exist for marketplace publish, but **description/schema quality is not enforced**. New connectors will not reliably NL-route from schema alone until G.2 is mandatory and `action_parameters` (or equivalent JSON Schema) covers the long tail.

### Improvement list (wrong-tool risk order)

1. Require when/why descriptions (≥1 sentence functional).  
2. Expand real JSON Schema / `action_parameters` beyond ~9% coverage.  
3. Normalize the 27 non-`vendor.resource.verb` ids (compat aliases OK).  
4. Align `destructive` / approval with all 185 writes.  
5. Add readOnly/destructive annotations consistent with MCP hints **mapped from** existing `kind`/`destructive` (single source).  
6. CI: reject placeholder descriptions; reject empty schema for chat-visible tools.  
7. Variance tests for top-N actions per new vendor before marking “generalized.”

## G.4 Standing process gap

**CLOSED (Phase 4, 2026-08-05):** Standard published at `docs/engineering/connector-action-schema-standard.md` with CI lint `backend/tests/connectors/test_action_schema_standard_lint.py`. G.3 baseline numbers above remain the pre-Phase-4 snapshot; post-fix when/why coverage is 100% of catalog via builder enforcement (see `routing-map-phase4-f8-evidence.json`).

---

## G.5 Advanced schema augmentation — progressive disclosure beyond base JSON Schema

**Research grounding (2025–2026 production techniques):** At catalog scale past ~494 tools, full schema dumps degrade tool-selection accuracy. Three shipped approaches converge on **progressive disclosure** (lightweight metadata first; full detail only when relevant):

| Technique | Source | Mechanism | Reported token effect |
|-----------|--------|-----------|------------------------|
| Tool Search Tool | Anthropic, 2025-11-24 | Tools marked `defer_loading:true`; a search tool substitutes; keyword search loads 3–5 full defs (~3K tokens) on demand | ~85% reduction |
| Code Mode | Cloudflare, 2026-02-20 | Typed SDK; model writes code against API surface instead of N callable tool defs | ~99.9% input reduction |
| Code execution + MCP | Anthropic, 2025-11-04 | Servers presented as filesystem-like discoverable API | ~150K → ~2K (98.7%) |
| BFCL (now V4) | Berkeley Function Calling Leaderboard | Cross-vendor accuracy yardstick, including **correctly withholds** when no right tool exists | Eval shape, not a compression technique |

Gravitre catalog size (**689** actions as of Phase 4; was 687 at initial audit) is past the measured overflow band — progressive disclosure is a real risk domain, not hypothetical.

### G.5.1 Is progressive disclosure applied on every Part A entry point?

| Entry (Part A) | Tool schemas to the model? | Narrowing applied? | Pattern |
|----------------|----------------------------|--------------------|---------|
| A1/A2 Main chat + TRY (LIVE path) | Yes — unified-turn shadow | **YES** — `embed_narrow_tools_for_turn` / `keyword_narrow_tools_for_turn` → `max_tools` (~32); embedding for task turns when catalog ≥ `unified_turn_embed_min_catalog_tools` (default 40) | Narrow-then-attach full schemas |
| A1/A2 Classical ReAct fallthrough | Yes — ReAct loop | **YES** — `react_engine` → `narrow_tools_for_turn` + `compress_tool_definitions` | Same family |
| A5d Extension chat | Yes — same `execute_task_streaming` | **YES** — same as A1 | Same family |
| A3 Workflow canvas / schedule / webhook-triggered workflow | No LLM tool dump — typed steps from definition | N/A (retrieve plan, not tool-calling) | Not applicable |
| A5a–c Extension enrich / workflow execute / one-shot action | Direct invoke or staged workflow | N/A — no multi-hundred tool prompt | Not applicable |
| A4 Agent jobs (ModelRouter worker) | ReAct via `AgentIntelligence.execute_task` (not `ModelRouter.complete`+tools) | **CONFIRMED YES** — `react_engine._react_loop` → `narrow_tools_for_turn` (cap 28) before `_chat_with_tools`; `tool_query` now passed from job path | Standing CI: `test_g5_unnarrowed_tool_attach_guard.py` |
| A6 Inbound product webhooks (HubSpot/SF/PD) | No NL tool calling | N/A | not NL-routed (Phase 5) |
| Pack-common / `ChatActionMapper` | Deterministic regex/score — not OpenAI tool-defs | Different mechanism (matrix scoring) | Can invent wrong tools without LLM schema dump (F4 class) |

**Verdict (2026-08-05 closeout):** Narrowing is **CONFIRMED** on A1/A2/A5d LIVE, classical ReAct, and **A4 agent jobs** (same `narrow_tools_for_turn` in ReAct). Progressive schema loading (`defer_loading` family) is **SHIPPED on A1/A2** via `unified_turn_progressive_schemas` + `search_catalog_tools` (`progressive_tool_schemas.py`). A5d extension chat shares LIVE `execute_task_streaming` — inherits A1 progressive once LIVE serves that path. Typed workflows / direct invokes remain N/A.

**Named risk G5-RISK-UNNARROWED-FALLTHROUGH — CLOSED:** Agent jobs already narrowed (evidence: `test_agent_job_react_path_narrows_under_cap`). Standing guard `NarrowedTools` + `assert_tools_narrowed` in `react_engine._chat_with_tools` and unified-turn attach; static AST CI forbids new `chat.completions.create(tools=)` sites outside allowlist. Salesforce `salesforce_update_record` visibility no longer pins solely to `leads.update` (wrong-action class, F6 rigor).

### G.5.2 Architectural comparison: Gravitre narrowing vs Anthropic Tool Search

| Dimension | Gravitre today | Anthropic Tool Search Tool |
|-----------|----------------|----------------------------|
| Selection | Keyword score (+ optional embedding top-k) **before** the reasoning call | Model (or search tool) selects which defs to load **during** the turn |
| What is sent | Full schemas for the entire narrowed set (≤ `max_tools`) every turn | Lightweight stubs / deferred tools + search; full defs for 3–5 hits on demand |
| Failure mode | Wrong tools in the top-k still fully described → model can call them | Deferred tools invisible until searched → lower accidental selection |
| Catalog access | Soft-capped: tools outside top-k are invisible that turn | Full library remains searchable |
| Implementation | `agent_platform_optimizer.narrow_tools_for_turn`, `unified_turn_tool_retrieval.embed_narrow_tools_for_turn` | `defer_loading` + dedicated search tool |

**Resemblance:** **Partial / keyword-narrow family** — same goal (don’t send 689 schemas), different mechanics. Gravitre is **narrow-then-send-all-narrowed**, not **defer-until-needed**.

**Meaningful upgrade — SHIPPED (A1/A2):** 

1. Keyword/embedding remain the **candidate generator** (unchanged).
2. Attach **name + one-line stub** + `search_catalog_tools`; full `input_schema` loads on search (flag `UNIFIED_TURN_PROGRESSIVE_SCHEMAS`, default on).
3. Write-authority **after** full schema load — CI `test_write_using_only_stub_is_rejected_until_full_schema_loaded`.
4. Before/after payload probe: `docs/delivery/g5-progressive-schemas-probe.json` (same TTFT probe set).

### G.5.3 Cloudflare Code Mode — feasibility vs governance-first fit

**Pattern:** Replace N tool definitions with a typed SDK; model writes code that calls the SDK.

| Governance requirement | Code Mode impact |
|------------------------|------------------|
| Inspectable action boundary per call (`vendor.resource.verb`) | **At risk** — authority moves into generated code paths; harder to gate each invoke as one catalog action |
| `catalog_write_authority` / approve-first writes | **Complicated** — need a sandboxed SDK that only exposes pre-authorized actions, or a re-parse of emitted calls back into ActionSpecs (second planner) |
| Audit `tool.invoke.*` + BusinessOutcome verified-output | **Preservable only if** every SDK call maps 1:1 to `invoke_tool` with the same finalize path |
| Population verify / effect honesty (F6) | Same — only if SDK bottoms out in existing executors |

**Recommendation:** **Explicitly decline as default architecture** for Gravitre’s governed connector surface. Reason: write-authority and approve-first need a **clear, inspectable action id per call**; Code Mode optimizes for token compression in open-ended coding agents, not for dual-path LIVE/classical governance. A **limited feasibility spike** is acceptable only for read-only research/sandbox surfaces that never hit mutating `invoke_tool` — not for chat/TRY/extension writes.

### G.5.4 BFCL evaluation shape — “correctly withholds”

BFCL V4 scores tool-calling accuracy **including declining when no right tool exists**. That is exactly the TRY-chip failure class (classical fabricated a plan instead of retrieving or clarifying).

| Status | Evidence |
|--------|----------|
| **CLOSED** | All three `withhold_no_tool` categories in `test_routing_nl_variance_battery.py` + combined pass-rate gate |
| Cat 1 | `test_withhold_fabrication_on_ambiguous_enrich` — F1 clarify / `block_fabrication` |
| Cat 2 | `test_withhold_no_matching_action_connected_vendor` — no invented wiki/pages tool |
| Cat 3 | `test_withhold_explicit_advise_only_mentions_vendor` — mapper `ADVISE_ONLY_NO_TOOL` → zero tool; pack-common withheld |
| Pass rate | `test_withhold_no_tool_combined_pass_rate` asserts **3/3 = 100%** |

### G.5.5 Disposition summary

| Technique | Resembles Gravitre today? | Disposition |
|-----------|---------------------------|-------------|
| Anthropic Tool Search / `defer_loading` | **Shipped** on A1/A2 progressive stubs + `search_catalog_tools` | **CLOSED** — evidence in progressive CI + payload probe; A5d inherits LIVE path |
| Cloudflare Code Mode | No | **Decline** for governed writes; optional read-only spike only |
| Anthropic code-exec + MCP filesystem | No | **Decline** as primary chat architecture (same governance boundary issue); MCP connector *servers* remain fine as catalog-backed tools |
| BFCL “correctly withholds” | **Shipped** 3-category battery | **CLOSED** — `withhold_no_tool` 3/3 CI |
| Current keyword/embedding narrow | Native | **Keep** as candidate generator under progressive stubs |
| G5-RISK-UNNARROWED-FALLTHROUGH | Was UNKNOWN for A4 | **CLOSED** — agent jobs narrow; standing NarrowedTools CI guard |

---

## Appendix — Code anchors

| Topic | Path |
|-------|------|
| LIVE entry | `backend/app/services/unified_turn_reasoning_service.py` → `apply_unified_turn_live` |
| Classical defer bag | `backend/app/services/unified_turn_classical_fallback.py` |
| Pack-common | `backend/app/services/pack_common_intent_defaults.py` |
| Orchestration intent | `backend/app/services/chat_orchestration_service.py` → `is_orchestration_intent` |
| NL mapper | `backend/app/services/chat_action_mapper.py` |
| Streaming chat | `backend/app/operators/agent_intelligence.py` → `execute_task_streaming` |
| Chat proxy | `apps/web/app/api/chat/route.ts` |
| TRY prompts | `apps/web/app/ai/_components/ai-mode-config.ts` |
| Extension API | `backend/app/routers/extension.py` |
| Agent jobs | `backend/app/operators/agent_jobs.py` |
| Effect honesty | `backend/app/services/connector_outcome_effects.py` |
| Outcomes UI | `apps/web/components/gravitre/business-outcome/business-outcome-view.tsx` |
| Catalog models | `backend/app/connectors/action_catalog/models.py` |
| Tool narrowing (keyword) | `backend/app/services/agent_platform_optimizer.py` → `narrow_tools_for_turn` |
| Tool narrowing (embedding) | `backend/app/services/unified_turn_tool_retrieval.py` → `embed_narrow_tools_for_turn` |
| Schema standard | `docs/engineering/connector-action-schema-standard.md` |
| Withhold battery | `backend/tests/services/test_routing_nl_variance_battery.py` |

## Appendix — Probe reproducibility

```text
cd backend
set PYTHONPATH=.
python ../scripts/probe-routing-decision-map.py
```

NL variance + withhold assertions also live in CI via `test_routing_nl_variance_battery.py`.

---

## Change log

| Date | Change |
|------|--------|
| 2026-08-05 | Initial standing map Parts A–G from code traces + unit NL/schema probe. Diagnosis only. |
| 2026-08-05 | Phases 1–5 closure updates in Part F; G.4 standard adopted. |
| 2026-08-05 | **G.5** added — progressive disclosure vs Tool Search / Code Mode / BFCL withhold; entry-point narrowing inventory. |
| 2026-08-05 | **G.5 closeout** — UNNARROWED risk CLOSED; progressive schemas on A1/A2; withhold_no_tool 3/3 CI. |
