# GRAVITRE UX RESET 1.0 — Phase 1A report

**Slice:** AI runtime convergence foundation only. No Phase 2 visual simplification. No product IA reskin.

**Evidence class:** unit tests (vitest). Production PASS is **not** claimed. Screenshots of the four presentation modes: **NOT PROVEN** (no live authenticated session in this slice).

---

## A. Files changed

- `apps/web/lib/gravitre-ai-presentation.ts` (new)
- `apps/web/lib/gravitre-ai-runtime.ts` (new)
- `apps/web/lib/chat-window-state.ts`
- `apps/web/components/gravitre/ai-workspace-provider.tsx`
- `apps/web/components/gravitre/ai-workspace-host.tsx`
- `apps/web/app/ai/_components/ai-workspace.tsx`
- `apps/web/components/intelligence/ask-gravitre-composer.tsx`
- `apps/web/components/intelligence/shell/intelligence-command-bar.tsx`
- `apps/web/components/intelligence/shell/intelligence-ask-command-surface.tsx`
- `apps/web/app/intelligence/page.tsx`
- `apps/web/app/agents/[id]/chat/page.tsx`
- `.cursor/rules/gravitre-ux.mdc`
- tests under `apps/web/__tests__/lib/` and `apps/web/__tests__/gravitre/`

## B. Runtime owner before / after

| Before | After |
| --- | --- |
| `AiWorkspace.useChat` (root host) | **Same — canonical owner** (`canonical-ai-workspace` registry id) |
| `AskGravitreComposer.useChat` | **Removed** |
| `AgentChatPage.useChat` | **Removed**; route summons canonical workspace with `agentScope` |
| Flag-off `/ai` page-local `AiWorkspace` | **Still exists** as kill-switch path (`GRAVITRE_AI_FLOAT_ENABLED=false`) |

## C. Presentation-state mapping

Canonical `minimized | compact | expanded | fullscreen` maps to shipped `helper | float | expanded | fullscreen`. React state still stores legacy names. `canonicalPresentation` is derived (`floatWorkspaceOpen === false` ⇒ minimized).

## D. Ask Gravitre

`AskGravitreComposer` is an entry: `summonWorkspace({ presentation: "compact", composerText, submit, selected, agentScope: null })`. No `useChat`. Intelligence map selection is passed as `pageContext.selected`.

## E. Agent-chat migration

Route kept. Page loads agent, sets `agentScope`, summons **fullscreen**. Canonical transport sends `agent_id` + `mode: "agent"` + `surface: "agent_chat"` when scoped. Agent-local `localStorage` thread cache from the old page is **not** migrated in this slice.

## F. `/ai` behavior

Direct `/ai` auto-opens the canonical workspace as **fullscreen** (same `useChat`). Navigating onto `/ai` no longer closes the overlay to drop into a second embed layout; it sets fullscreen and keeps the same instance. Query params `prompt`/`q`/`c`/`conversation`/`m`/`mode` still apply on the `/ai` route.

## G. `/assistant`

Unchanged redirect to `/ai`.

## H. pageContext

Still pathname + params. Now also `selected`. Captured on Ask Gravitre summon. Backend `AssistantChatRequest` has `extra="ignore"`; selected entity is **not** a first-class API field yet. `research_scope` is used as a temporary carrier when a selection exists.

## I. Thread persistence

Same `AiWorkspace` conversation id / cache as before when using the host. **NOT PROVEN** across a live compact→route change in the browser in this slice. Unit coverage: provider instanceId survives simulated navigation.

## J. Voice persistence

Voice hooks remain inside `AiWorkspace` only. **NOT PROVEN** live (no STT/TTS session exercised). Architecture: presentation change does not remount `AiWorkspace` once the host is armed.

## K. Tool / execution persistence

Approvals/execution state remain in `AiWorkspace`. **NOT PROVEN** live across minimize/expand.

## L. AuthGate

Unchanged.

## M. Marketing isolation

Unchanged. Source test asserts host does not import marketing chat.

## N. Meson

Unchanged. Not folded into chat.

## O. Deep links

`/ai` query params preserved. `/assistant` redirect preserved. `/agents/[id]/chat` preserved as a scoped summon.

## P. Tests added

- `gravitre-ai-presentation.test.ts`
- `gravitre-ai-runtime.test.ts`
- `phase-1a-runtime-convergence.test.ts` (static: no `useChat` in Ask / agent chat)
- provider: compact mapping, summonWorkspace, `/ai` fullscreen

## Q. Tests run

See delivery message for vitest invocation.

## R. Failures

Recorded in delivery message.

## S. Unproven claims

- Four presentation-mode screenshots
- Playwright / live one-runtime instrumentation in a browser
- Voice session continuity
- In-flight tool continuity
- Backend using `pageContext.selected` as structured context (temporary `research_scope` only)
- Old agent-chat `localStorage` history continuity
- `NEXT_PUBLIC_AI_FLOAT_ENABLED=false` dual-mount path removed

## T. Remaining duplicate runtime paths

- Kill-switch: `/ai` still mounts `AiWorkspace` when the float flag is off
- Host is lazy-armed: first compact summon is the first `useChat` mount (one owner, delayed)
- Dev `ai-workspace-preview` prototype (not product)

## U. Screenshots

**NOT PROVEN** this slice.

---

**Stop.** Do not start Phase 2 until Cesar reviews.
