# Output preview fidelity — Phase 0 inventory + Phase 1 confirm

Date: 2026-08-03  
Canvas: `canvases/output-preview-fidelity-phase0.canvas.tsx`  
Related: `docs/delivery/chat-progress-ux-phase0-2026-08-03.md`

## Principle

Preview fidelity must match **what is technically renderable** and **what Gravitree actually produces**. Claude’s live Preview/Code pane fits web-native code; Cowork/Manus file chips fit Office blobs. Gravitree’s dominant outputs are **connector writes / BusinessOutcomes** — verified vendor evidence, not generated code or hosted Office files.

## Phase 0 — Real inventory

| Output type | Exists? | Format | Surface | Matched preview |
|-------------|---------|--------|---------|-----------------|
| Connector write BusinessOutcome | **Yes (dominant)** | DTO: summary, evidence links, verification, timeline | Chat `density=chat`, Activity, Runs | Evidence card |
| `generate_document` | **Yes (Phase 2)** | Hosted md/docx/pdf/csv/html + signed download | Chat file chips + Preview/Code | File-reference chip |
| Artifact registry cards | Yes | Metadata + short preview | Chat fallback when no BO | Link/preview |
| Lite deliverables | Yes (side) | JSON download | `/lite/deliverables` | Download |
| Assignments | Yes (side) | Client `.txt` | Assignments UI | Text + download |
| Admin / metrics CSV | Yes (ops) | CSV | Admin pages | Not assistant output |
| CodeAct | Yes | Text `repr` preview | Artifact report kind | Text only |
| Chat-generated chart / HTML / SVG / React | **Yes (Phase 3)** | previewHtml + Code tab (SVG charts from analytics/CodeAct; md/html docs) | Chat Preview/Code pane | Preview · Code |
| Dashboard charts | Yes (product UI) | **recharts** | Home / metrics / CS / intelligence | Not task artifacts |
| In-app PDF/DOCX viewer | **Partial** | Download chips for generated PDF/DOCX; no full Office WYSIWYG editor | Chat file chips | Download (not Office embed) |

## Phase decisions

| Phase | Decision | Rationale |
|-------|----------|-----------|
| **1 Confirm BusinessOutcome** | **DONE — no rebuild** | Already the correct preview for connector outcomes |
| **2 File-reference chip** | **BUILT** | `chat_hosted_file_service` persists md/docx/pdf/csv/html; `FileReferenceChip` in tool results + execution panel |
| **3 Live Preview/Code** | **BUILT** | `PreviewCodePane` (Preview iframe / markdown + Code tab) for documents, analytics SVG charts, CodeAct HTML |

## Phase 1 confirmation (evidence)

### Code path (no change)

- Success + failure: `ChatExecutionPanel` → `BusinessOutcomeView` `density="chat"` when `business_outcome` present  
  (`apps/web/components/gravitre/assistant/chat-execution-panel.tsx`)
- Shared renderer: `apps/web/components/gravitre/business-outcome/business-outcome-view.tsx`  
  (summary, evidence link buttons, verification, timeline)
- Activity: `apps/web/app/activity/page.tsx` (`density="timeline"`)
- Runs: `apps/web/app/runs/[id]/page.tsx`

### Prod data (14d sample)

Runs with `verified_output` (Module A substrate for BO projection), including:

- `50a34d4c-…` — `assistant_chat` / Search contacts / completed / `verified_output` present (2026-08-03)
- `56640bf3-…` — `assistant_chat` / Search contacts / completed / `verified_output` present
- `626aba58-…` — `browser_extension` / completed / `verified_output` present

### Explicit non-goals

- No fake live preview of PDFs or Office files  
- No new charting dependency for chat  
- No speculative file generation just to demo chips  
- ~~Browser extension still uses status text (not BO card)~~ — **closed** (see Gap closeout)

## Verification

| Check | Result |
|-------|--------|
| Phase 0 inventory reported before design | PASS — this doc + canvas |
| Phase 1 BO path intact (code) | PASS — early-return to `BusinessOutcomeView` |
| Phase 2 file chip built | **PASS (code)** — hosted_file artifacts + e2e `hosted_files` |
| Phase 3 live render built | **PASS (code)** — PreviewCodePane + e2e `preview_code` |
| Mismatched preview mechanisms added | PASS — none |
| Product code redeploy required | **No** — documentation-only ship |

## Live verification append (2026-08-03)

### Matched preview for connector outcomes

| Surface | Result | Evidence |
|---------|--------|----------|
| Prod substrate (Module A `verified_output`) | **PASS** | Run `50a34d4c-56eb-4178-aa44-242bd20c2c79` status `completed`, label `Search contacts`, `parameters.verified_output` with Apollo `external_url` + summary + `result_url` (queried 2026-08-03) |
| Cohort (14d completed chat/ext-ish) | **PASS** | 20/39 completed rows carry `parameters.verified_output` |
| Chat render path | **PASS (code)** | `ChatExecutionPanel` success + failure → `BusinessOutcomeView` `density="chat"` |
| Activity / Runs render path | **PASS (code)** | `activity/page.tsx` + `runs/[id]/page.tsx` → `density="timeline"` |
| Authenticated UI screenshot (chat/Activity) | **PASS (harness)** / prod login **NOT RUN** | E2E harness `business_outcome` + screenshot artifact; gravitre.app still needs operator session |
| Browser extension | **PASS — gap closed** | Overlay renders BO evidence card when `businessOutcome` present (see Gap closeout) |

### Deploy tip

- Docs tip: `e60f3128` (fidelity decision) + this append commit
- Live API `/health` `git_sha` at verify time: `b64add73…` (BusinessOutcome already on tip; docs-only fidelity ship does not require Railway tip move)

## Deploy note

No application code changes. Tip deploy confirmation is the currently live Railway `/health` `git_sha` (BusinessOutcome already on tip from prior Module A work). This commit records the fidelity decision only.

## Reconfirm under preview-fidelity prompt (2026-08-04)

Re-ran Phase 0 inventory + Phase 1 live BO API check against tip `b64add73…`:

| Check | Result | Evidence |
|-------|--------|----------|
| Phase 0 inventory unchanged | **PASS** | Connector BO dominant; durable files **no**; chat charts/HTML **no** |
| Phase 1 BO GET + export identity | **PASS** | Outcome `95137db3-c760-4334-9b69-277e599351e0` — `projection=business_outcome`, sections include `evidence` + `verification`, GET/export identical @ `2026-08-04T00:08:57Z` |
| Phase 2 / Phase 3 | **SKIP** | No first-class file or web-renderable chat artifacts |
| Chat / Activity code path | **PASS (code)** | Unchanged early-return to `BusinessOutcomeView` |
| Extension BO card | **PASS** | Gap closed — see below |
| UI screenshot | **PASS (harness)** | Login gate bypassed via `/e2e/execution-result` |
| Canvas | Phase 0 inventory | `canvases/output-preview-fidelity-phase0.canvas.tsx` |

Artifact: `docs/delivery/output-preview-fidelity-live.json`

## Gap closeout (2026-08-03)

Closed open gaps from Phase 1 / reconfirm — matched preview now covers chat harness UI + extension overlay.

| Gap | Result | Evidence |
|-----|--------|----------|
| Extension BO renderer | **PASS (code + fixture)** | `apps/extension/content/shared.js` `renderBusinessOutcomeCard` / `showExecuteResult`; CSS `.gvt-outcome*`; backend projects DTO via `_project_extension_business_outcome` on confirmed action + confirmed workflow; URLs → `/runs/{id}` + `/activity` |
| Extension visual | **PASS (fixture screenshot)** | `docs/delivery/_artifacts/extension-bo-overlay-fixture.png` via `docs/delivery/fixtures/extension-business-outcome-overlay.html` @ `2026-08-03` |
| Chat UI screenshot (login gate) | **PASS (e2e harness)** | Playwright `business_outcome` scenario — harness `/e2e/execution-result?scenario=business_outcome` renders `[data-projection=business_outcome]` id `run-bo-fixture`; screenshot `docs/delivery/_artifacts/bo-chat-harness-business-outcome.png` |
| Unit coverage | **PASS** | `pytest tests/services/test_extension_business_outcome_preview.py` (2); vitest `resolve-business-outcome.test.ts` (2); e2e business_outcome (1) |
| Authenticated prod chat screenshot | **NOT RUN** | Still needs operator session on gravitre.app — harness proves shared `BusinessOutcomeView` path without login |
| Prod tip includes gap closeout | **PASS** | `/health` `git_sha=e40bf9fe…` @ `2026-08-04T00:55:17Z` — tip ancestor includes commit `6bfa0417` |

### Scope adds

- E2E harness scenario `business_outcome` in `apps/web/app/e2e/execution-result/harness.tsx`
- Playwright assertion + artifact screenshot in `e2e/execution-result-navigation.spec.ts`
- Export `resolveBusinessOutcome` for unit test
- Extension overlay API exports `renderBusinessOutcomeCard` / `showExecuteResult` for fixture/reuse
- v0 IA handoff prompt expanded (`frontend-ia-v0-handoff-prompt.md`)

## Phase 2 + 3 implementation (2026-08-03)

**Ship commit:** `32a9ced3` (feature contents; message on that SHA was mistitled — this section is the source of truth).

| Phase | Surface | Evidence |
|-------|---------|----------|
| 2 File chips | `generate_document` → storage bucket `chat-artifacts` (md/docx/pdf/html + csv when table present) | `backend/app/services/chat_hosted_file_service.py`; UI `file-reference-chip.tsx` |
| 2 File chips | Analytics chart HTML hosted | `tool_analytics` attaches `hostedFiles` |
| 3 Preview/Code | Document / chart / CodeAct | `preview-code-pane.tsx` in tool chips + `ChatExecutionPanel` |
| E2E | Harness scenarios | `hosted_files`, `preview_code` in `e2e/execution-result-navigation.spec.ts` |
| Config | `CHAT_ARTIFACTS_BUCKET` / `chat_artifacts_bucket` (default `chat-artifacts`), `chat_store_hosted_files` | Create private Supabase bucket in prod for signed downloads |

**Honesty notes:** PDF is text-only (minimal writer, not print-quality). No Claude-style arbitrary React sandbox — Preview is sandboxed `srcDoc` HTML/SVG + markdown. Durable downloads require Supabase Storage bucket provisioning; without it, Preview/Code still works from inline `previewHtml`/`code`.

## Production wiring + live UI proof (2026-08-04)

| Item | Result | Evidence |
|------|--------|----------|
| Supabase bucket `chat-artifacts` | **PASS** | Migration applied on prod `smyeexlrqdpymwjmgzqu`; SQL confirms private bucket 5MB |
| Upload + signed download | **PASS** | `scripts/verify-preview-fidelity-phase23-live.py` — 5 durable files (md/html/docx/pdf/csv) @ `2026-08-04T02:30:27Z` |
| UI harness screenshots | **PASS** | `docs/delivery/_artifacts/phase2-hosted-files-harness.png`, `phase3-preview-code-harness.png` |
| Railway tip includes Phase 2/3 | **PASS** | `/health` `git_sha=e432a8b5…` @ `2026-08-04T07:18:36Z` (ancestor of `32a9ced3`) |
| Live chat `generate_document` on tip | **PASS** | Isolated org `f07e57c0…` — SSE includes `hostedFiles` + `previewHtml` via `generateDocument` @ `2026-08-04T07:18:36Z` |

Artifact: `docs/delivery/output-preview-fidelity-phase23-live.json` — **overall PASS**
