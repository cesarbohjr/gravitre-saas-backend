# Slice 1 — Preview release gate (2026-09-24/25)

Branch `feat/gravitre-3.0-plus-frontend`. Not merged. Not deployed to production. Authority: `GRAVITRE_3_0_PLUS_MASTER_SPEC.md`, `20-g-struct-decision-package.md`, `23-slice-1-live-integration.md`.

## Release artifacts

| Item | Value |
| --- | --- |
| Slice 1 foundation commit | `c348f164` (pushed) |
| Inspector integration commit | `6cfa3be7` (pushed) |
| Preview (foundation) | Vercel deployment `7PGN5nsLcANLVj7m8A3Sr3d15DFp`, SSO-protected, branch alias |
| Preview (release candidate) | `dpl_5oHdTi15mFMZQqngHLniWEGHJWeE` (`6cfa3be7`, Ready, 2026-09-25T07:21Z), SSO-protected |
| Web CI (foundation) | [run 36080582337](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36080582337): Web lint+typecheck+build success, Backend pytest success, Integration smoke success, Shared runtime gate success, Dependency audit success, Billing E2E **cancelled** after 20 min (step "Run billing Playwright suite") — not a pass |
| Web CI (release candidate) | [run 36107438501](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36107438501) on `6cfa3be7`: same five jobs success; Billing E2E **cancelled** at its 20-min `timeout-minutes`. That job runs only on `workflow_dispatch` (skipped on every `main` push), so it has no recent baseline — not a pass |
| Live backend | `d04c4e26` (`/health` at 2026-09-25T07:17:38Z); Railway was deploying `378a45f9` at 07:25Z (public-browser READ matching only). Delta from `f7d13fba` touches no chat router, SSE emission or conversation persistence; contract additions (`work_artifacts[] kind=table`, `computer_browser_read`) are additive |
| Env change | `FASTAPI_BASE_URL=https://api.gravitre.app` added to Vercel **Preview, this branch only** (authorized in-session). Production env untouched |

## Signed-in Preview walk — BLOCKED_EXTERNAL

- Preview auth goes to `gravitre.app/auth/v1` (`NEXT_PUBLIC_APP_URL`) and Google OAuth returns to `gravitre.app`; Preview hosts cannot complete OAuth themselves. Approach used: sign in on `gravitre.app` in the headed test browser, then copy the session to the Preview host only if the account is the owner.
- The headed sign-in returned `cesar@gravitre.app` (Google auto-select). That session was copied once, the org returned 402 on conversations/assistant, **no chat turn was sent**, and the cookies were removed. Owner guard added so this cannot recur.
- Owner-only window (20 min) timed out without `cesar.bohorquez.jr@gmail.com`. The clear step also removed the owner session saved in the local test profile; any further live run needs a fresh owner sign-in.
- Consequence: desktop/mobile walk, identity, inspector live interaction, stream trace and frontend latency on Preview are **NOT RUN**. Harness ready: `live-preview-stream.mjs` (fetch tee with `performance.now()` per SSE chunk, submit→request, request→first event, first text→DOM, runtime-state transitions, persisted GET), `live-owner-capture.mjs` (direct backend capture + replay through the app's AI SDK `readUIMessageStream`).

## Stream completion mismatch — root cause NOT CONFIRMED

Observed (local gate, `23`): UI `failed`; backend persisted user `019f83ac…` + assistant `5d639bab…` in `6657dbdb…`.

What the UI shows as failed is exactly `useChat` status `"error"` (`deriveAiRuntimeState`). AI SDK 6.0.194 sets it on transport failure **or** on a `UIMessageStreamError` thrown by its stream processor for inconsistent chunks: `tool-output-available` for an unknown `toolCallId`, `text-delta`/`text-end` without `text-start`, `reasoning-*` without start, `tool-input-delta` without start, approval for an unknown tool call. The local turn rendered text and a stuck "Running 1 tool" indicator before erroring, which fits an inconsistent tool chunk as well as a dropped connection. Direct backend runs without tools finished cleanly.

Current handling in the core (`ai-workspace.tsx` `onError` → `recoverCompletedChatTurn`) refills text only when the last assistant text is empty and never clears `"error"`. Bridges cannot see canonical truth, so the UI cannot reconcile to completed without a core change. HTTP 200 is not treated as completion anywhere in Slice 1.

Dependencies:

- **FE-core-1** (core owner, `ai-workspace.tsx`): after `onError`, reconcile against persisted truth (`/api/chat/replay` or `/conversations/{id}/messages` containing the assistant message for this user message id) and expose `turnRecovered: "completed" | "not_found"` to bridges. Slice 1 then shows completed only on `completed`.
- **BE-SSE-1** (core agent, if capture shows it): every `tool-output-*` preceded by `tool-input-start`/`tool-input-available` with the same `toolCallId` in the same message; every `text-delta`/`text-end` inside `text-start`; `finish` then `[DONE]` on all paths including composer shortcuts.
- Discriminating evidence still required: one owner turn captured through `live-preview-stream.mjs` on Preview, replayed through `readUIMessageStream`.

## Interrupted first turn — ownership established

Lifecycle (code: `ai-workspace.tsx` `ensureConversation`; backend `assistant.py:1255–1264`, `conversation_state_service.py:313`, `_persist_conversation_turn` `assistant.py:379–476`):

1. Client mints the conversation UUID and stores it in localStorage. **Identity owner: client.**
2. Backend `ensure_owned_conversation` inserts the row with that id at turn start (`message_count` 0).
3. User and assistant messages persist only after `finish`.
4. Interruption before `finish` → empty row, user message lost (`4e94ffa3…`, `message_count` 0). Request never reached backend → no row → GET 404 (`04310635…`); the core 404 path clears the id and local messages.
5. If the row is missing at persist time, `_persist_conversation_turn` inserts without `id` → a **server-minted** id diverging from the client's.

Slice 1 does not create a replacement conversation or claim recovery. Dependencies:

- **BE-CONV-1**: persist the user message at turn start (with the client message id).
- **BE-CONV-2**: complete and persist the turn when the client disconnects.
- **BE-CONV-3**: `_persist_conversation_turn` always inserts with the request's `conversation_id`.
- **FE-core-2**: on 404 for a pending (never-persisted) id, keep unsent local messages and offer resend instead of clearing.

## Inspector — FIXTURE / UNIT ONLY

Seam: `GravitreAIRuntimeDetails` wraps the existing `GravitreAIRuntimeStatus` (new optional `action` slot) in the float, shell and mobile-sheet bridges. A "Details" button appears only for settled states (completed, failed, partial, needs_approval, blocked) and opens the existing `GravitreInspector` (right; bottom on mobile). Fields come only from props the bridges already hold (`conversationId`, `messages`, `executionResult`, `pendingTask`); absent fields are omitted, an unsaved conversation reads "Not saved yet". No new store, no fetch, no action buttons ("Approve or reject in the conversation. Nothing runs from this panel.").

Evidence: `__tests__/gravitre/ai-runtime-details.test.ts` (6), full suite 946/946, `tsc` clean, chat-surface drift guard clean. Open/close, Escape, focus return and placement use the `GravitreInspector` primitive already validated in Slice 0; live interaction on Preview **NOT RUN**. Not LIVE_UI_PROVEN.

## Approval / blocked / partial

| State | Class | Status |
| --- | --- | --- |
| needs_approval | A fixture; B NOT RUN | Org has 0 HITL policies, so writes auto-run; no policy change or consequential WRITE made to manufacture one (owner choice `leave_not_run`) |
| blocked | A fixture; B NOT RUN | No production signal reachable without policy change |
| partial | A fixture; C dependency | Needs `execution_result.steps` with mixed outcomes from the kernel; no live example observed |
| resumed | C dependency | No production signal exists |

## Latency

- Backend (direct, `f7d13fba`, `23`): headers 4.3 s, first text 29.9 s for a trivial prompt, ~25 s in context/memory review. Handed to core agent as **BE-LAT-1** with the prompt and conversation `6657dbdb…`.
- Frontend segments (submit→request, request→first event, first text→render, paint, window transition) on Preview: **NOT RUN** (sign-in blocked). Local dev timings are not representative (on-demand compile, HTTP/1.1 limit).
- The window manager is not claimed to meet the end-to-end SLO.

## Merge and rollback package (awaiting Cesar's approval)

- Merge: fast-forward/merge `feat/gravitre-3.0-plus-frontend` into `main` only after an owner-signed Preview walk and a green Billing E2E rerun. `main` has no `apps/web` overlap with this branch at time of writing.
- Rollback: Vercel instant rollback to the prior production deployment, or `git revert` of the merge; kill switch `NEXT_PUBLIC_AI_FLOAT_ENABLED=false` + rebuild disables the floating workspace; optional removal of the branch-scoped Preview `FASTAPI_BASE_URL`.
- No backend, billing, entitlement, approval-policy or pricing change in this branch. No new customer-facing price, claim, badge or toggle.
