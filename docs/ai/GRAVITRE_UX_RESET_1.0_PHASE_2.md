# GRAVITRE UX RESET 1.0 — Phase 2 report

**Slice:** visual simplification of the canonical AI workspace + context indicator + header Ask entries. **No product-wide Agents/Relationships/Settings IA reskin.** **No production deploy.** **Phase 3 not started.**

Pass language: **PASS / FAIL / NOT PROVEN / BLOCKED**.

---

## Added

- Customer-facing context lines from existing provider state (`Talking with …` / `Using {type}: {label}`) in compact, expanded, fullscreen, mobile sheet, and helper subtitle.
- `AskGravitreSummonButton` on Agents, Workflows, Connectors, Performance, Approvals, and Activity (canonical Runs/outcomes surface; `/runs` redirects there). Text control; page primary actions unchanged.
- Selection clear (`×`) on the indicator; does not start a new thread.
- Helper subtitle: live presence (listening / thinking / executing / needs_approval / error) wins over object/agent context.

## Changed

- Empty `/ai` landing: identity, composer, four text suggestions. Removed decorative “One surface, three modes” pill, mode-chip row, and suggestion **card grid**.
- Ask Gravitre entry: no nested card, icon tile, or suggestion pills.
- Expanded/fullscreen **default** history and context rails **collapsed** (still available via existing toggles). Compact still has no rails.
- User message bubble: no drop shadow.
- In-thread example chips: text, not bordered tiles.
- Fullscreen kill-switch page header: removed “Answer · Search · Execute” metadata span; shows context indicator.
- Avatar fallback: `suppressHydrationWarning` to reduce shots overlay (D vs DW).
- `minimizeToHelper` only closes the float; it does not stop voice (continue the same session).

## Removed (from this chrome)

- Landing mode dashboard.
- Duplicate Ask Gravitre heading stack.
- Permanent expanded/fullscreen inspector/history as the default layout.

**Not removed:** conversation sidebar implementation, task panel, research cascade, ChatSessionControls, kill-switch XOR, marketing isolation, Meson.

---

## A. Executive result

Phase 2 **visual slice is implemented** on the proven Phase 1 runtime. Context is **visible without reconstructing** backend state. Broader page IA (connectors catalog cards, settings rows, relationship graph chrome) is **deferred**.

Voice minimize choice: **continue the same session**. Minimize does not stop STT/TTS; helper already shows listening/thinking presence. Unit proof: `minimizeToHelper` keeps the voice snapshot. Live mic hardware: **NOT PROVEN**.

---

## B. Context indicator

**PASS** — compact selected-object (`Using … Acme`), agent-chat `Talking with Inbound Lead Triage` (`e2e/canonical-ai-workspace.spec.ts` 2026-09-17). Helper live-status copy **PASS** (unit `gravitreHelperStatusCopy`).

State source: `GravitreAIWorkspaceProvider` (`agentScope`, `pageContext.selected`). Formatter: `lib/gravitre-ai-context-label.ts`.

---

## C. Compact chrome

Still header + thread + composer. No history/activity rails in float. Context line sits under the title.

---

## D. Empty / landing

Composer-first. Suggestions are text. Modes are not first-class empty-state chrome (`AI_MODES` is already a single Unified engine).

---

## E. Messages / sources / artifacts

Assistant replies were already unboxed (`CHAT_ASSISTANT_BUBBLE_CLASS`). User shadow removed. Sources/execution still expand in-turn via existing transcript panels — not a permanent column.

---

## F. Remaining product Ask entries

Intelligence already had Ask Gravitre. Header **Ask Gravitre** (summon compact, not a second `useChat`) on:

- `/agents`
- `/workflows`
- `/connectors`
- `/intelligence/performance`
- `/approvals`
- `/activity` (canonical Runs/outcomes)

Playwright click-through **PASS** on shots Agents, Activity, Workflows, Connectors, Approvals (`data-ask-gravitre-summon` → one compact runtime). Performance header is source-asserted; no `/e2e/shots/performance` harness page.

---

## G. Voice minimize

**Decision:** continue. Do not start a second capture session. Unit **PASS**. Hardware **NOT PROVEN**.

---

## H. Tests

Vitest: context-label (including helper live-status), Phase 2 source assertions (landing, Ask not a card, rails collapsed, header Ask on six pages), `clearSelectedEntity`, minimize keeps voice snapshot.

Playwright helper: `page.waitForFunction` now passes `{ timeout }` as **options** (third arg). Passing it as the second argument previously waited until the whole test budget expired.

---

## I. Suites

| Check | Result |
| --- | --- |
| `pnpm test` (`apps/web`) | **PASS** — 119 files / 790 tests (2026-09-17). Gap re-run: 3 files / 23 tests **PASS** after header Ask source expansion. |
| `pnpm typecheck` | **PASS** (after truncated `.next/dev/types/routes.d.ts` from concurrent Playwright was deleted) |
| Playwright `e2e/canonical-ai-workspace.spec.ts` | **PASS** — 26 tests, 2.1m (2026-09-17), `E2E_SKIP_FIXTURE_SEED=1` `PLAYWRIGHT_SKIP_BACKEND=1` (shots do not need FastAPI `/health`; HF Hub warmup previously **BLOCKED** that webServer). Chromium via `npx playwright install chromium`. |
| Production build | **PASS** — `pnpm build` in `apps/web` exit 0 (~272s) 2026-09-17 |
| Deploy | not done |

Shots Playwright is harness proof, not production chat. Live `/ai`, tools, voice hardware, AuthGate logout remain **NOT PROVEN** (Phase 1C).

---

## J. Out of scope (later)

Original plan items 6–7: Agents/Relationships/Performance/Settings/Connectors **page IA**, Motion polish between presentation states. **Not started.**

---

## Customer-facing claims

No new prices, badges, Enable toggles, or certifications.
