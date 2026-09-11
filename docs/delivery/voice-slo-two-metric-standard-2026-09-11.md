# Standing two-metric voice latency standard

**Status:** standing definition as of 2026-09-11.  
**Supersedes:** any single-number “voice latency” / blended TTFA+completion target, including the pre-STA-343 P50&lt;500ms bar applied to operator-task *completion*.

This is the permanent definition of voice latency for this program. Intent Gateway, Cognitive Loop Controller, Response Composer, and STA-343 loop-stage narration are unchanged; this document formalizes measurement and the one safe OBSERVE optimization.

## Why two metrics

Current academic benchmarking and published production measurements: **no real production voice system, including Gemini Live 3.1 and GPT-Realtime, holds a sub-500ms SLO on genuine tool-calling / operator-shaped completion**.

- [Full-Duplex-Bench-v3](https://arxiv.org/abs/2604.04847) (Lin, Chen, Chen, Lee, 2026): Gemini Live 3.1 fastest task-completion **4.25s**; first-word / tool-call / completion = 3.95s / 2.21s / 4.25s. GPT-Realtime completion **6.89s**.
- [EVA-Bench](https://arxiv.org/abs/2605.13841) (ServiceNow): tool-call turns use a separate latency curve from no-tool turns (sweet spot 500–3000ms, hard-late 5s). Blending the two categories is explicitly the wrong methodology.

Metric B’s P50 &lt;5s / P95 &lt;8s is matched to that published best-in-class band, not an internal compromise.

Blending “time to first sound” with “operator task finished” produces a number that is unfair to both: it makes first-audio look worse than every competitor’s first-speech SLO, and it makes completion look better than the real tool-calling bar.

## Metric A — Time to First Honest Response

- **Clock:** end of user speech → first genuine, composed, loop-state-sourced audio (STA-343 narration on operator turns; otherwise the composed answer).
- **Hard target:** P50 &lt; **500ms**, P95 &lt; **800ms**.
- **Applies to:** every spoken turn, simple or operator-shaped. No exceptions.
- **Audit action:** `voice.slo.metric_a`
- **Alert:** `voice_slo_metric_a_p50>500ms` / `voice_slo_metric_a_p95>800ms`

STA-343 option 1 is the speech mechanism: PERCEIVE / RETRIEVE / PLAN / ACT / OBSERVE drafts through Response Composer (`kind=progress`). LEARN is not spoken. Fast-path stays silent.

## Metric B — Operator-Task Completion Latency

- **Clock:** end of user speech → final composed answer on genuinely tool-using / multi-stage turns.
- **Target:** P50 &lt; **5s**, P95 &lt; **8s** (matched to published best-in-class, not an internal compromise).
- **Does not apply** to simple chitchat.
- **Audit action:** `voice.slo.metric_b`
- **Alert:** `voice_slo_metric_b_p50>5000ms` / `voice_slo_metric_b_p95>8000ms`

## What must never happen

- A golden-signals headline named “voice latency” or “voice reply speed” that mixes A and B.
- Lowering `INTENT_GATEWAY_THRESHOLD`.
- Skipping the six-stage loop for speed.
- Claiming a write complete before real verification.

## OBSERVE verification (Phase 3)

| Turn shape | Critic / write verification |
|---|---|
| Genuine mutating write this turn (`execution_verified` or successful mutating tool) | **Blocks** spoken final claim |
| Legal / financial high-risk read | **Blocks** (existing governance) |
| Plan staging (`awaiting_plan_confirm`) | **Async** — does not wait |
| Ordinary reads | **Async** |

Catalog write-success follow-up reads were already fire-and-forget (`schedule_write_success_verification`). That contract is unchanged.

## Where it is reported

- Admin golden signals: `voice_slo.metric_a` and `voice_slo.metric_b` separately (`golden_signals_service._voice_slo_two_metric_signals`).
- Internal Flux stage timings remain under `voice_turn_latency` and are labeled **not the SLO**.
- CI: `.github/workflows/voice-slo-gates.yml` (daily) + `scripts/check-voice-slo-alerts.py`.

## Linear

Companion to [STA-343](https://linear.app/staqbot/issue/STA-343/six-stage-loop-vs-spoken-first-audio-option-1-loop-stage-speech) (option 1 closed). This standard is the remaining latency contract.
