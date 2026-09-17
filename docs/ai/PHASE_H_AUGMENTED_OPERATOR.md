# Phase H — Augmented operator (platform-wide)

**Status:** H1–H4 in this increment (local). Live PASS not claimed. E6 GA4 remains **human reconnect** (`EXTERNAL_BLOCKED` until smoke-org Google Analytics is re-authorized). Writes stay confirm-gated.

This phase is the named follow-on to F (conversation control) and G (operator-act on vague prompts). It is **not** a marketing claim of ChatGPT-level intelligence. It hardens Intelligence Hub G8 UI, GA4 OAuth honesty, ReAct/voice cancel, and chat execution-plan surfaces so rationale, reasoning, latency, personality, and connector usage share one SoT.

## Why this exists

F closed stop / honesty / typed parts / replay / prefix cache / continue. G injects reachable connectors. Remaining deficits:

| Track | Gap |
|---|---|
| G8 UI | Map `aria-controls` had no matching canvas `id`; Overview “What Gravitre learned” rows did not deep-link to the map |
| GA4 | Refresh failures were opaque HTTP text; docs still listed a per-product callback |
| ReAct / voice | Classical ReAct polls `chat:stop`; unified-live and Pipecat could keep ACT after Stop |
| Chat plan UI | Side/progress panels still hung on `pending_task.params.steps`, not ExecutionPlan summary / step rationale |

## Constraints

- Do not invent prices, badges, Enable toggles, or “live ChatGPT-level” claims.
- Do not seed fake learnings to force G8 PASS.
- Do not set `prompt=consent` on the shared Google OAuth client.
- Dual paths: `/ai`, `/agents/[id]/chat`, and spoken `execute_task_streaming` honor the same stop key.
- `policy.silent_writes = false`.

## Increments

### H1 — G8 UI (this increment)

`id="intelligence-map-canvas"` on the graph stage so lens tabs’ `aria-controls` resolve. Overview learning rows that already exist in canonical state use `buildLearningInsightMapHref` (same contract as Learning hub cards). Empty state stays honest.

**Done when:** axe no longer flags the lens `aria-controls` orphan; a real learning row on Overview opens Overview with `lens=learns&focus=learning:…`. Prod click-through still **NOT RUN** until an org has promoted learnings.

### H2 — Voice / unified-turn consume Stop (this increment)

`is_stop_requested` before unified-live tool rounds and before/during Pipecat `execute_task_streaming` event consumption. ReAct already polls.

**Done when:** Stop during a spoken or LIVE tool turn leaves no further tool invoke (audit/log). Live **NOT RUN**.

### H3 — GA4 architecture hygiene (this increment)

Parse Google `invalid_grant` on token refresh; mark connector reconnect-required with an honest message. Align `GOOGLE_ANALYTICS.md` redirect with shared `/api/connectors/oauth/google/callback`.

**Does not** complete E6. Smoke-org reconnect is still human.

### H4 — Execution plan on the chat surface (this increment)

`project_pending_task_from_plan` copies `plan_summary`, `plan_rationale`, and `plan_steps` (title, kind, connector, status, optional `meta.rationale`). Progress derivation falls back to those steps. Research plan panel shows summary + rationale when present.

Personality remains gravitre_voice / spoken register — not a new badge.

### H5 — Later (not this increment)

- Bidirectional map → Learning hub highlight
- Unified-live / CognitiveTurnKernel consume ExecutionPlan identity (not only pending_task)
- Voice barge-in POSTing `/api/chat/stop` in addition to local interrupt
- Latency: surface `cached_tokens` on the operator chat status (no invented SLO)

## Out of scope

- Silent writes
- Invented TRAINED / certified / live-GA4-healthy badges
- Expanding Google OAuth product surfaces
