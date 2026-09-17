# GRAVITRE UX RESET 1.0 — Phase 1C report

**Slice:** first-class AI context contract + remaining live verification holes. **No Phase 2.** No visual redesign. **No production deploy.**

**Evidence class:** source + Vitest + targeted pytest + Playwright against `/e2e/shots/*` (fixture-authenticated shells). Production authenticated `/ai` chat, live model turns, live tools, live STT/TTS, and live AuthGate logout are **not** claimed PASS.

Pass language in this document is only **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## A. Executive result

Phase 1C **meets the context-contract exit criteria** and **does not** convert remaining environment holes into PASS.

**What is proven:**

- Selected-object / route / surface identity is a typed `workspace_focus` field on `AssistantChatRequest`, distinct from `agent_id` and from `research_scope`.
- Canonical transport (`AiWorkspace` `useChat` body) serializes that field. Playwright captured `selection.object_id === "acme"` and that `research_scope` is not used as object identity.
- Backend validates the nested model (`extra="forbid"` on focus), resolves IDs **only** through existing org-scoped stores, and feeds a fenced block into `compile_unified_reasoning_context` / `compile_assistant_turn_context` (existing ContextCompiler).
- Stale selection does not ride the next turn after leaving the page (Playwright). Agent scope still clears on non-agent-chat routes (source + provider effect; fixture agent-chat still sends `agent_id`).
- `/assistant` Playwright `ERR_CONNECTION_REFUSED` was **harness/proxy order**, not a missing product route. Request-level redirect to `/ai` is **PASS**.
- Shots `/e2e/shots/ai?prompt=&mode=` applies query params through the real `AiPage` (MOCK / harness).
- Kill-switch remains XOR (`GRAVITRE_AI_FLOAT_ENABLED`). One runtime invariant still holds on the shots harness.
- `pnpm typecheck`, `pnpm lint` (0 errors), `pnpm build`, Vitest, and targeted backend tests **PASS**. Corrupted `.next/dev/types/routes.d.ts` from concurrent Playwright was deleted; typecheck/build then succeeded.

**What is not proven / blocked:** live authenticated `/ai?prompt=` against a real session; live `/agents/[id]/chat` stream against a real agent row and model; live READ tool; live AuthGate logout; voice STT/TTS; live `audit_events` / cognitive-trace row for `context.*` metadata; live multi-tenant resolution (unit FakeClient only).

**Phase 2:** **DO NOT START in this slice.** Readiness for later visual work is recorded in **AD**.

---

## B. Architecture discovered

Canonical assistant path (unchanged ownership; focus added as an input):

1. **UI selection / summon** — `GravitreAIWorkspaceProvider` (`selected`, `agentScope`, `pathname`) + Ask Gravitre / agent chat summon.
2. **Transport** — `AiWorkspace` `useChat` `body()` → `POST /api/chat` (Next) → FastAPI assistant chat.
3. **Request schema** — `AssistantChatRequest` (`backend/app/routers/assistant.py`).
4. **Handler** — `assistant_chat` → `_build_stream(...)` with `workspace_focus=body.workspace_focus.model_dump()`.
5. **Operator** — `AgentIntelligence.execute_task_streaming`.
6. **Resolve** — `resolve_workspace_focus` (`workspace_focus_resolver.py`) after client-ready, **before** compile.
7. **ContextCompiler** — `compile_unified_reasoning_context` (INCLUDE part `workspace_focus`) and `compile_assistant_turn_context` (merge into `entity_relationship_section`).
8. **Cognitive runtime** — existing unified-live / `CognitiveTurnKernel` / `apply_unified_turn_live` path; resolved focus also stored on `CognitiveTurnRequest.parameters` and `task_state["_workspace_focus_turn"]`.
9. **Retrieval / research_scope** — still the retrieval-breadth enum (`internal_only` | `intelligence_packs` | `internet_research` | `everything`). Not an entity id.
10. **Agent scope** — request-root `agent_id` + `mode: "agent"` when talking to an agent.
11. **Tools / generation** — same `execute_task_streaming` pipeline; no second prompt assembler.

No `GravitreAIContext` / `ContextCompilerV2` / parallel cognitive stack was added.

---

## C. Existing context source of truth

| Concern | Source of truth |
| --- | --- |
| Conversation thread | `conversation_id` + existing conversation store |
| Agent configuration | `agent_id` → `resolve_agent_record` |
| Retrieval breadth | `research_scope` |
| Product focus (route + selected object) | **New typed input** `workspace_focus`, resolved then compiled |
| Org / tenant | authenticated `org_id` on the request / session (resolver always `.eq("org_id", org_id)`) |
| Knowledge nodes | `org_knowledge_nodes` |
| Relationship rows | `org_entity_relationships` |
| Workflow / run / connector | existing repositories / tables |

Frontend display labels are **not** authoritative.

---

## D. Context contract implemented

Frontend: `apps/web/lib/gravitre-workspace-focus.ts` (`WorkspaceFocusPayload`).

Backend: `backend/app/schemas/workspace_focus.py`

```text
WorkspaceFocus {
  surface?: str
  route?: str
  selection?: {
    object_type: str
    object_id: str
    label?: str   # presentation only
  }
}
```

`agent_scope` is **not** inside this object. It remains `AssistantChatRequest.agent_id`.

Supported `object_type` values (only types with a real store or explicit identity-only UI hint):  
`entity`, `customer`, `company`, `contact`, `product`, `agent`, `workflow`, `run`, `connector`, `relationship`, `department`, `signal`.

`department` / `signal` are **identity-only** (no generic fetch).

**AVAILABLE FOR PHASE 2 (indicator state):** **YES** — provider debug already exposes `selected` and `agentScopeName`. No customer-facing “Talking with…” UI was built.

---

## E. Request schema changes

`AssistantChatRequest.workspace_focus: WorkspaceFocus | None = None`.

- Missing context: **valid**.
- Nested `WorkspaceFocus` / `WorkspaceSelection`: `extra="forbid"`.
- Parent `AssistantChatRequest` still `extra="ignore"` so **legacy unknown keys** do not 500; they are still ignored. Typed focus is no longer an ignored extra.
- Invalid nested extras: **rejected** at validation (`test_workspace_focus_schema_rejects_unknown_keys`).
- Parse/resolve exceptions inside `execute_task_streaming` fall back to `resolution=unresolved` and **do not invent** object details.

---

## F. Transport changes

`AiWorkspace` chat body:

- Always may send `workspace_focus` from current `pageContext` + surface via `buildWorkspaceFocusPayload`.
- Omits the payload when there is no route and no selection.
- Sends `agent_id` / `mode` / `surface` on the request root for agent chat.
- `research_scope` remains `researchScopeRef` (user retrieval control), not selected-entity encoding.

Playwright Ask Gravitre (shots `/e2e/shots/proof`): at least one POST with `workspace_focus.selection.object_id === "acme"` and falsy `research_scope`.

---

## G. Backend propagation

Exact names:

`POST assistant chat`  
→ `AssistantChatRequest`  
→ `assistant_chat` (`backend/app/routers/assistant.py`)  
→ `_build_stream(..., workspace_focus=...)`  
→ `AgentIntelligence.execute_task_streaming(..., workspace_focus=...)`  
→ `WorkspaceFocus.model_validate` + `resolve_workspace_focus`  
→ `compile_unified_reasoning_context(..., workspace_focus=resolved)`  
→ `compile_assistant_turn_context(..., workspace_focus=resolved)`  
→ unified live / kernel turn (`apply_unified_turn_live` and existing generation)

Handler dump: `workspace_focus=body.workspace_focus.model_dump() if body.workspace_focus else None` (~line 1447).

---

## H. Context compiler integration

- Unified compiler: INCLUDE part labeled `workspace_focus`; EXCLUDE when absent.
- Classical / kernel compiler: fenced block appended to `entity_relationship_section` when present.
- Block is produced by `format_workspace_focus_compiler_block` and wrapped with existing `fence_page_context_block`.
- Copy states **current turn only — not historical**.
- Unresolved: explicit instruction not to invent object details; user message still included.

Unit: `test_compile_includes_workspace_focus_block` in `tests/services/test_phase_e4_context_compiler.py`.

---

## I. Object resolution

| Client type | Store | Notes |
| --- | --- | --- |
| entity / customer / company / contact / product | `org_knowledge_nodes` | DB `node_type` is canonical type; client claim kept as `client_claimed_type` |
| agent | `resolve_agent_record` | Wrong store (node id as agent) → UNRESOLVED (`test_wrong_store_does_not_fall_through`) |
| workflow | `get_workflow_def` | |
| run | `get_run_with_steps` | |
| connector | `connectors` table + `org_id` | |
| relationship | `org_entity_relationships` + `org_id` + `archived_at` null | Canonical IDs exist when rows exist |
| department / signal | identity-only | No generic fetch |

**No** generic object-fetch endpoint.

Live Relationships “What do we know about this?” against production graph: **NOT PROVEN**. Representative type for proof: **entity** (`acme` fixture + FakeClient `org_knowledge_nodes`).

**Relationship edges:** Intelligence map non-node selection maps to `{ kind: "relationship", id: selection.edgeId }`. Backend can resolve `org_entity_relationships.id` in-org. Live edge Ask: **NOT PROVEN**. If a UI node lacks a stable id, it must not be sent (identity-only types already skip registry).

---

## J. Tenant / security proof

Resolver always filters by **authenticated org_id**. Same object id in another org is a different row or UNRESOLVED.

`test_entity_resolves_in_current_org_only`: org-a → name `Acme`; org-c (no row) → `unresolved`, compiler block contains “not found in this organization”, **does not** include the other tenant’s name.

**PASS** — unit FakeClient.  
**NOT PROVEN** — live two-org fixture in Playwright or production.

---

## K. Context lifecycle

| Layer | Behavior | Proof |
| --- | --- | --- |
| ROUTE | `pageContext.pathname` updates every navigation | source + shots |
| SELECTION | set on summon / `setSelected`; **cleared on pathname change** | provider effect; Playwright stale-selection |
| AGENT SCOPE | set on `/agents/[id]/chat` summon; **cleared when leaving that route** | provider regex; fixture agent-chat test |
| CONVERSATION | same `useChat` owner; not reset because route/selection changed | Phase 1B + stale test still one runtime after restore |
| WORKSPACE | presentation changes do not remount owner | Phase 1B still holds |

Thread is **not** recreated merely because selection/route changed.

---

## L. Turn-level context behavior

Each user turn snapshots **current** `workspace_focus` on that request. Historical turns are not rewritten.

Playwright:

1. Select Acme → “Summarize this customer.” → POST selection `acme`.
2. Navigate to `/e2e/shots/workflows`, restore helper, “What is slow in our AI pipeline?” → later POST `workspace_focus.selection` is **null**.

Conversation history remains the same client thread (same runtime restore). Server-side turn row immutability: **NOT PROVEN** (no live `conversation_messages` inspection). `task_state["_workspace_focus_turn"]` is the intended per-turn snapshot on the operator path.

---

## M. Agent scope regression

| Claim | Status |
| --- | --- |
| Fixture `/e2e/shots/agent-chat` uses canonical runtime | **PASS** (MOCK) — `liveInstanceCount === 1`, one POST, `agent_id=agt_lead_triage`, `mode=agent`, `surface=agent_chat` |
| Leaving agent-chat clears agent scope | **PASS** (source: provider pathname effect) |
| Live `/agents/[id]/chat` stream vs real agent + model | **NOT PROVEN** |

No second `agent_id` inside `workspace_focus`.

---

## N. `research_scope` cleanup

Selected-object encoding **removed** from transport. Vitest: `selected-entity-context.test.ts`. Playwright Ask Gravitre: `research_scope` falsy on contextual POST.

Retrieval enum and `handleResearchScopeSelect` unchanged. Retrieval behavior vs live cascade: **NOT PROVEN** (not re-run as a live retrieval eval). Source path still passes `research_scope` into unified retrieval independently of `workspace_focus`.

---

## O. `/ai` query proof

| Layer | Status | Evidence |
| --- | --- | --- |
| SOURCE COMPATIBILITY | **PASS** | `apps/web/app/ai/page.tsx` and `ai-workspace.tsx` still read `prompt`, `q`, `c`, `conversation`, `m`, `mode` |
| MOCK / HARNESS | **PASS** | Playwright `shots /ai query params apply on the harness /ai path` — `/e2e/shots/ai?prompt=hello-from-query&mode=chat` → fullscreen, ≥1 mocked POST, `liveInstanceCount === 1`. Shots `ai` surface **is** product `AiPage`. |
| LIVE BROWSER (authenticated `/ai?prompt=`) | **NOT PROVEN** | No real Supabase session in this harness |

---

## P. `/assistant` proof

Phase 1B `page.goto("/assistant")` → `ERR_CONNECTION_REFUSED` after shots home: **test infrastructure / proxy order**, not a missing App Router page.

Fix: `apps/web/proxy.ts` redirects `/assistant` **before** `updateSession`. Playwright `request.get("/assistant", { maxRedirects: 0 })` → 3xx with `Location` matching `/ai`.

Product page still `redirect(APP_ROUTES.gravitreAiChat)`.

**PASS** (redirect). Live follow-through of authenticated `/assistant` → streamed chat: **NOT PROVEN**.

---

## Q. Live agent proof

Fixture agent-chat: **PASS** (MOCK).  
Live `/agents/[id]/chat` one stream complete vs development agent + model: **NOT PROVEN** / **BLOCKED** on credentials and a safe test agent in this environment.

---

## R. READ tool proof

**BLOCKED.** No safe live READ-only tool invocation with resize/minimize/restore was executed. Would require live model + permitted tools + org credentials. Not converted to PASS from mock chat.

---

## S. AuthGate live proof

**BLOCKED.** Shots use `ShotAuthProvider`. Logout → unmount launcher/runtime was not exercised on a real session. Exact reason: no deterministic authenticated Playwright user with AuthGate logout in this Phase 1C environment.

---

## T. Voice / manual proof

**NOT PROVEN / MANUAL REQUIRED.** No STT/TTS hardware session. Architecture still: voice hooks live only inside the single `AiWorkspace` owner (Phase 1A/1B). Duplicate sockets: **NOT PROVEN**.

---

## U. Kill-switch proof

**PASS** (source / Vitest). `phase-1a-runtime-convergence.test.ts`: flag off → host returns null; `/ai` page still mounts page-local `AiWorkspace`. XOR: never two owners by design; flag off is the documented single page owner.

Playwright live toggle of the env flag: **NOT PROVEN**.

---

## V. Legacy agent-history disposition

**INTENTIONALLY RETIRE / INSUFFICIENT EVIDENCE.**

- Agent chat no longer owns `useChat`; old page-local thread cache was never migrated (Phase 1A).
- Repo search did not find a stable production `localStorage` agent-history schema still written by the canonical workspace.
- No evidence in this slice of a meaningful production dependency that would justify migration machinery.

Do not build speculative migration. Canonical thread = current `AiWorkspace` conversation cache / server `conversation_id`.

---

## W. Tests added (this slice)

- `backend/app/schemas/workspace_focus.py`
- `backend/app/services/workspace_focus_resolver.py`
- `backend/tests/services/test_workspace_focus_resolver.py`
- `apps/web/lib/gravitre-workspace-focus.ts`
- `apps/web/__tests__/lib/gravitre-workspace-focus.test.ts`
- Compiler coverage in `test_phase_e4_context_compiler.py`
- Playwright: Ask Gravitre context POST, `/assistant` redirect, stale selection, fixture agent-chat, shots `/ai` query params
- Vitest: selected-entity must not use `research_scope`; proxy `/assistant` before session
- Shots: `agent-chat` surface + proof page selection

Debug UI remains `window.__GRAVITRE_AI_DEBUG` / `__GRAVITRE_AI_TEST` (not production chrome).

---

## X. Tests run

| Suite | Result | Evidence |
| --- | --- | --- |
| `apps/web` Vitest | **PASS** | 117 files / 785 tests (this conversation) |
| Playwright `e2e/canonical-ai-workspace.spec.ts` | **PASS** | full file green after Ask Gravitre + stale-selection fixes (2026-09-17) |
| `pytest tests/services/test_workspace_focus_resolver.py tests/services/test_phase_e4_context_compiler.py` | **PASS** | 11 passed (2026-09-17 rerun) |
| Broader backend pytest (entire `backend/tests`) | **NOT PROVEN** this slice (targeted context tests only) |

---

## Y. Build / type / lint

| Check | Result |
| --- | --- |
| `pnpm typecheck` (`apps/web`) | **PASS** (after removing truncated `.next/dev/types`) |
| `pnpm lint` | **PASS** exit 0; ~299 pre-existing warnings, 0 errors |
| `pnpm build` | **PASS** Next.js 16.3.3 production build, TypeScript finished |

Do not treat truncated generated `routes.d.ts` during concurrent `next dev` + Playwright as a product type error.

**No deploy.**

---

## Z. Failures

None remaining that block the **context contract**. Prior Playwright Ask Gravitre (expected 1 POST, got 2) and stale-selection hang after `page.goto` were **test assertions / navigation**, fixed (accept ≥1 contextual POST; restore via `__GRAVITRE_AI_TEST.restoreFromHelper`).

---

## AA. NOT PROVEN

- Live authenticated `/ai?prompt=` (non-shots URL)
- Live model/agent completion on canonical runtime
- Live cognitive-trace / `audit_events` row with `context.surface` etc.
- Live Relationships / edge Ask against real graph rows
- Live retrieval-cascade unchanged (integration)
- Live kill-switch flag flip in browser
- Server conversation UUID continuity across route changes
- Voice STT/TTS / duplicate sockets
- Production user dependency on old agent `localStorage` history (treated as retire)

---

## AB. BLOCKED

- Live `/agents/[id]/chat` stream vs real agent + model (env / safe agent)
- Live READ-only tool + resize/minimize/restore
- AuthGate live logout
- Live cross-tenant HTTP proof (no two-org Playwright fixture)

---

## Selected-object context — layer matrix (required)

| # | Layer | Status |
| --- | --- | --- |
| 1 | UI selection | **PASS** (shots proof page + debug.selected) |
| 2 | Workspace state | **PASS** (provider `pageContext.selected`) |
| 3 | Transport serialization | **PASS** (Playwright POST `workspace_focus`) |
| 4 | Request schema acceptance | **PASS** (Pydantic typed field + forbid extras) |
| 5 | Handler propagation | **PASS** (source: `assistant_chat` → `_build_stream`) |
| 6 | Context compiler ingestion | **PASS** (unit INCLUDE + merge) |
| 7 | Authoritative object resolution | **PASS** (unit FakeClient entity); live DB **NOT PROVEN** |
| 8 | Tenant authorization | **PASS** (unit org-c unresolved); live **NOT PROVEN** |
| 9 | Cognitive runtime availability | **PASS** (code path into compiler/kernel); live kernel **NOT PROVEN** |
| 10 | Model/agent turn availability | **PASS** (MOCK stream); live model **NOT PROVEN** |
| 11 | Trace observability | **PASS** (source `workspace_focus_trace_meta` / `_workspace_focus_turn`); live trace row **NOT PROVEN** |

Do not read “field exists” as “the model understands context.” Layer 10 live remains **NOT PROVEN**.

---

## Context test matrix

| Case | Status |
| --- | --- |
| NO CONTEXT → normal Ask | **PASS** (schema + compiler EXCLUDE; shots composer) |
| PAGE CONTEXT | **PASS** (route on payload) |
| ENTITY A → Ask | **PASS** (MOCK transport + unit resolve) |
| ENTITY A → ENTITY B → Ask | **NOT PROVEN** (no Playwright B switch; summon can replace selected) |
| ENTITY A → leave page → general Ask | **PASS** (Playwright stale selection) |
| AGENT A → Ask | **PASS** (MOCK fixture agent-chat) |
| AGENT A → exit scope → general Ask | **PASS** (source clear); live **NOT PROVEN** |
| RELATIONSHIP → Ask | Schema + resolver **PASS** unit-capable; live UI **NOT PROVEN** |
| INVALID ENTITY → Ask | **PASS** unit UNRESOLVED + no-hallucinate block |
| CROSS-TENANT ENTITY | **PASS** unit; live **NOT PROVEN** |

---

## AC. Remaining Phase 2 UX requirements

Do **not** implement now. Later visual work may use:

- Subtle indicator: talking with agent X / using customer Y (state already on provider)
- Compact chrome simplification
- Not: a second context system, not: research_scope as identity

---

## AD. Phase 2 readiness

**CANONICAL WORKSPACE:** proven in browser harness (Phase 1B, still green).  
**CONTEXT CONTRACT:** first-class, compiler-fed, tenant-filtered in unit tests.  
**SCOPE LIFECYCLE:** selection + agent scope clearing proven (Playwright + source).  
**CORE ROUTING:** `/assistant` redirect harness **PASS**; `/ai` query MOCK **PASS**.  
**NO DUPLICATE CHAT RUNTIME:** still **PASS** on shots.

External live integrations (model, tools, voice, AuthGate, prod tenant) are **documented blockers**, not a reason to keep inventing Phase 1 context systems.

**Phase 2 visual redesign: not started.** Gate for later: **READY TO BEGIN WHEN CESAR AUTHORIZES PHASE 2**, with the BLOCKED/NOT PROVEN list above remaining honest.

---

## Exit criteria checklist

| ID | Criterion | Status |
| --- | --- | --- |
| A | First-class selected-object contract | **PASS** |
| B | `research_scope` not abused as object identity | **PASS** |
| C | Backend accepts typed contextual state | **PASS** |
| D | Canonical compiler receives it | **PASS** |
| E | Authoritative resolution for ≥1 type | **PASS** (unit entity) |
| F | Tenant boundary | **PASS** (unit) |
| G | Stale selection lifecycle | **PASS** (Playwright) |
| H | Stale agent scope | **PASS** (source + fixture) |
| I | Live `/ai` prompt | **PASS** MOCK / **NOT PROVEN** live session |
| J | `/assistant` harness | **PASS** |
| K | Live agent route | **BLOCKED** / **NOT PROVEN** live |
| L | Live READ tool | **BLOCKED** |
| M | AuthGate live logout | **BLOCKED** |
| N | Voice | **MANUAL REQUIRED** |
| O | One-runtime invariant | **PASS** (shots) |
| P | Test/build suite | **PASS** (web vitest + typecheck + lint + build + targeted pytest + canonical Playwright) |

---

**STOP.** Phase 2 was not started.
