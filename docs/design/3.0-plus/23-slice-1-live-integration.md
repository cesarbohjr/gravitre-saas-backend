# Slice 1 — live integration gate (signed-in `/ai` against production backend)

Date: 2026-09-24. Branch `feat/gravitre-3.0-plus-frontend`. Evidence: `slice-1-live/`.

## Environment (authorized by Cesar in-conversation)

- Local Slice 1 frontend (`next dev --webpack`, `127.0.0.1:3010`) with `FASTAPI_BASE_URL=https://api.gravitre.app` and production Supabase. `/api/chat` is the existing thin proxy — no second runtime, provider, or SSE subscription.
- Account: owner (`cesar.bohorquez.jr@gmail.com`), signed in by Cesar in a persistent browser profile; the agent never handled credentials. Org `cbbf993b-b22f-41ce-964b-1fc25e0dd9ea`.
- A local **production build** could not hold a session: `lib/supabase/url.ts` routes production auth through the `/auth/v1` rewrite on the app host, which only exists on the deployed domain. Environment-specific, not a Slice 1 defect; it is why this gate ran in dev mode.
- Dev-mode artifacts that affect timing only: on-demand route compilation (20–70 s first hit), HTTP/1.1 six-connection limit per host, React dev double-fetching. Timings below are therefore **not** production latency.

## Backend baseline

| When | Live SHA (`/health` `git_sha`) | CI | Deploy |
| --- | --- | --- | --- |
| Desktop chat walk (turn persisted 21:28:25Z) | `491ed409` | [36055800269](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36055800269) success | Railway [36055800350](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36055800350) success |
| Viewport / focus / history walks (from ~21:50Z) | `f7d13fba` (confirmed 22:26:24Z) | [36063508675](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36063508675) success | Railway [36063508736](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36063508736) success |

`d30d3a4a` (22:07Z) is docs-only with no Railway run; production stays `f7d13fba`.

SSE contract re-verified directly on `f7d13fba`: request `ade055aa-82ae-43b3-85d9-beb017e4e808`, HTTP 200, events `start → start-step → data-intelligence* → text-start → text-delta → text-end → finish-step → finish → data-suggestions → [DONE]` (`backend-direct-1790288999978.json`). Same contract as `491ed409` (request `418934f2-5494-460b-8eee-f1027aeba753`). Slice 1 touches no API/SSE/conversation contract, so the combination is compatible.

## Host seam

Sufficient with **no protected-file edit**. The float bridge, shell bridge and mobile sheet bridge route every presentation change through `GravitreAIWorkspaceProvider`; `ai-workspace.tsx` owns the one `useChat` instance and is unchanged.

Optional coordinated one-liner (not applied): in `app/ai/_components/ai-workspace.tsx` the shell's expand/fullscreen handlers call `setPresentationMode` (applied, not remembered) rather than `choosePresentationMode`. Effect today: entering fullscreen/expanded from the shell is not remembered as the WM preference, while dock/undock/minimize are. Harmless; only worth changing with the core-agent owner.

The shared `GravitreInspector` is not mounted in the live host (fixture-only); live inspector focus-return is therefore not exercisable yet.

## Live results (signed-in, real browser)

Desktop 1440 (`live-desktop.json`, `live-viewports-all.json`, `live-focus-escape.json`):

| Check | Result | Evidence |
| --- | --- | --- |
| No hydration errors (`/home`, reload with docked preference, `/ai`) | PASS | 0 hydration errors, 0 page errors |
| Launcher opens canonical workspace at contextual default | PASS | placement `window`, 1 surface; `L01` |
| Send → exactly one `/api/chat` POST, streamed reply rendered | PASS | 1 POST; `streaming` observed; `L02`, `L03` |
| Turn terminal state in UI | INCONCLUSIVE | UI ended `failed`; backend persisted user `019f83ac-2ac7-4c29-9ace-26f9d4643099` + assistant `5d639bab-9fa8-4920-a04a-ee1c96cb4a28` in `6657dbdb-676a-430b-a198-ab12edee6150` at 21:28:25Z. Direct backend runs finish cleanly; suspected local dev stream delivery. Re-verify on a Preview deployment. |
| Dock reserves page space | PASS | settles to 420 px = body `padding-right` 420 px within 400 ms (`L04b`); the earlier 468 px was a mid-animation sample |
| Undock releases page space | PASS | `padding-right` 0 |
| Expand / composition options | PASS | Conversation enabled; Work/Split disabled with no work objects |
| Fullscreen: `aria-modal`, Exit + Reduce, focus trap, Escape → expanded | PASS | 0 trap escapes over 25 Tabs (warm run); `L06` |
| Minimize → restore returns to prior mode | PASS | docked → helper → docked |
| Refresh keeps conversation + preference | PASS | `L07` |
| `/ai` opens the canonical workspace fullscreen, exitable | PASS | 1 shell surface, `Exit fullscreen` present; `L08` |
| Identity across dock/undock/expand/fullscreen/reduce/minimize/restore/refresh | PASS | conversation `6657dbdb…`, identical message ids, 1 surface, 0 duplicate nodes at every step |
| Existing conversation resume | PASS | `efccc7cd-ee81-48ce-877e-619d9fe23152`: 10 persisted messages rendered, 0 duplicates, 0 chat POSTs (`L09`, `live-artifact.json`). First attempt blank because `/messages` took 55–59 s through the dev proxy — latency, not loss |
| Existing artifact inspection | NOT RUN | No conversation in this workspace exposes live work objects (Work stays disabled); inspector not mounted live |

Narrow 1024, tablet 834, mobile 390 — reduced motion on (`live-viewports-all.json`, `V-*`, `F-390-*`):

| Check | 1024 | 834 | 390 |
| --- | --- | --- | --- |
| Surface on screen, one surface | PASS (docked) | PASS (expanded) | PASS (sheet; vaul translates a viewport-tall panel and pads the hidden part — composer fully visible) |
| Composer reachable + keyboard focus | PASS | PASS | PASS (791–827 of 844) |
| Fullscreen exitable | PASS | PASS | PASS (Exit button; Escape exits after first Escape dismisses the focused button's tooltip — standard Radix layering) |
| Minimize / restore identity | PASS | PASS | PASS |
| Focus returns to launcher after minimize | FAIL → fixed → PASS | FAIL → fixed | FAIL → fixed → PASS |
| Refresh keeps conversation id | PASS | PASS | PASS |
| No page errors, no chat POSTs from window ops | PASS | PASS | PASS |

## Defect found and fixed in this gate

Minimizing to the launcher left focus on `<body>` at every width: the pressed control unmounts with the workspace and nothing received focus. Pre-existing (launcher unchanged by Slice 1), but minimize/restore is Slice 1 scope.

Fix: `GravitreAIWorkspaceProvider.takeHelperFocusRequest()` — set whenever the workspace closes to the launcher, consumed once by the launcher's mount ref. Never set on first load (verified live: focus stays on `<body>` on page load). Live after fix: `F-1440-minimized-focus.png`, `F-390-minimized-focus.png` — focus on "Open AI Chat — Ready", Enter restores. Unit test added; full suite 939/939, `tsc` clean.

## Runtime-state fidelity

- `completed`: observed live when the stream finishes.
- `failed`: observed live and faithful to what the client received (see INCONCLUSIVE turn above) — the UI did not invent completion.
- `awaiting approval` / `blocked` / `partial`: NOT RUN live. The org has **no HITL policies** (`GET /api/settings/hitl-policies` → `{"policies":[]}`), and `hitl_policy_service.resolve` auto-runs writes when none exist. Any "approval-gated" request would execute, so the authorized `reject_after` test cannot be done without a production policy change. Needs Cesar's explicit choice.
- `resumed`: stays fixture-only; no backend signal exists, none was fabricated.

## Backend dependencies (not hidden by the frontend)

1. **Interrupted-stream persistence.** Conversation rows and turns persist only when a stream completes (the client mints the id — `ensureConversation`). An interrupted first turn leaves the client pointing at an id the backend 404s (`04310635-2332-4b3b-9452-22faebc5f8ae`) and loses the user's message. The core's 404 path clears it only once history loads.
2. **No `resumed` lifecycle event.**
3. **Time to first text.** Direct run on `f7d13fba`: headers 4.3 s, first text 29.9 s (25 s in context/memory review) for a trivial prompt.
4. **Approval testability.** No HITL policy means no approval state to validate.

## Merge / deploy sequence (not executed)

1. Push `feat/gravitre-3.0-plus-frontend`; required CI (`apps/web` lint, `tsc`, vitest) green.
2. Vercel Preview of the branch; signed-in re-run on the Preview (HTTP/2, production build, real `/auth/v1` rewrite) of: send/stream terminal state, dock/fullscreen/minimize, 390 sheet. This closes the INCONCLUSIVE turn.
3. Merge to `main` → Vercel production (frontend only; backend unchanged at `f7d13fba`, contract verified).
4. Live prod chat trace with request id after deploy.

## Rollback

- Vercel instant rollback to the previous production deployment, or `git revert` of the merge commit.
- Kill switch without a code change: set `NEXT_PUBLIC_AI_FLOAT_ENABLED=false` in Vercel and rebuild (inlined at build time); returns `/ai` to the pre-Phase-5 embed and hides the launcher.
- No migrations, no backend changes, no stored-data changes — rollback is frontend-only.

## Acceptance

Slice 1: **PARTIAL.** Window management, identity, responsive, keyboard and resume are live-verified; terminal-state delivery is INCONCLUSIVE pending a Preview run; approval/blocked/partial and live artifact inspection are NOT RUN for the reasons above. Slice 2 not started.
