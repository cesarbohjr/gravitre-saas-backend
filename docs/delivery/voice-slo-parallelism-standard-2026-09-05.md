# Voice speed standard v2 — real parallelism, three SLOs, honest Phase 0–10 result

**Date:** 2026-09-05
**Deployed tip:** `cd04d20301ecdecc151276451706412548476789` (live, confirmed via `/health`)
**Standard:** P50 TTFA <500ms, P95 TTFA <800ms, interruption-to-silence <150–200ms

## MANDATORY PRE-FLIGHT

| Selection | Live in prod? | Evidence |
|---|---|---|
| Deepgram Flux (STT, native EOT) | **Yes** | `stt_factory.py` primary provider; live Pipecat DEBUG logs show `Connected to Flux`, `User started/stopped speaking` on every probe run this session |
| ElevenLabs Flash v2.5 (TTS) | **Yes** | `pipeline.py` `ElevenLabsTTSService`; golden signals `ttfb_by_processor.ElevenLabsTTSService` p50=120ms, p95=159ms (real, live, 25 samples) |
| WebSocket protocol (both legs) | **Yes** | `pipecat.transports.websocket.fastapi`, Deepgram/ElevenLabs both WS-based in `pipeline.py` |
| Pipecat | **Yes** | `pipecat 1.8.1`, confirmed via banner in every probe run's stdout |

All four selections are genuinely live. **Honest caveat carried forward:** "live" here means the connection/provider/protocol is wired and producing real audio — it does **not** mean the resulting latency meets the new SLOs (it does not; see Phase 10).

---

## Phase 0 — Sequential vs. parallel, made explicit

**Finding (honest, before this pass's fixes): stages were mostly SEQUENTIAL, not overlapping.** Confirmed by code read + live timing:

1. **STT/EOT → LLM was already correctly ordered** (LLM cannot start before EOT is confirmed — that's correct, not a bug).
2. **Inside the reasoning stage, real independent work was serialized that had no dependency on each other:**
   - `agent_intelligence.py`: `list_connected_integrations` (blocking), `get_enabled_tools_for_org`, `load_intelligence_engine_settings` — three awaits in a row, zero data dependency between them. **Fixed this pass** (`asyncio.gather` + `asyncio.to_thread`; mutation-proof start-time-spread test added).
   - `cognitive_turn_kernel.py` `_recall()`: five memory stores (hybrid, agent, department, ledger, workspace) run one after another; four of five are synchronous/blocking calls that additionally block the event loop while running. **Fixed this pass** (`asyncio.gather` + `asyncio.to_thread`, merge order preserved for dedup correctness; mutation-proof elapsed-time test added).
3. **Real, live-confirmed contributor to the earlier ~8–13s gap** (see `docs/delivery/voice-latency-8to13s-gap-rootcause-2026-09-04.md`): this session's earlier `contextual_understanding`/`domain_intelligence` spoken-mode skip fix, plus the connector-auth in-memory cache, plus these two new parallelization fixes, are all direct fixes for **sequential-not-parallel** processing — exactly the Phase 0 diagnosis this prompt predicted.
4. **VAD vs. predictive EOT:** confirmed Deepgram Flux native EOT is in use (not fixed-duration silence VAD) — `stt_factory.py` primary provider. However, fresh golden signals (below) show `user_turn_finalization` p50=2ms/p95=5ms/p99=115ms — STT-side finalization is **not** currently the bottleneck in the live, deployed system today (the earlier probe-only "6.3s Flux watchdog" finding was explicitly flagged in that doc as possibly a synthesized-audio-over-WAN artifact of the probe script itself, not a confirmed real-browser issue — that caveat still stands, unresolved, and is not re-litigated here).

**Root cause, restated honestly: it was Class B/sequential-processing, exactly as this prompt hypothesized — not "any one stage being too slow."**

---

## Phase 1 — Genuine speculative, cancelable pipeline overlap

| Item | Status |
|---|---|
| 1. Context/memory retrieval + intent classification begin on **partial** STT transcripts, concurrently, while user is still speaking | **Confirmed live, already shipped** (`app/services/pipecat_voice/speculative_prefetch.py`, `SpeculativePrefetchProcessor` — warms dialogue settings, sentiment, tool-retrieval embeddings, tool-document embeddings, and read-only knowledge retrieval on `InterimTranscriptionFrame`s, with a `min_chars` gate and cancel-on-partial-change). **This module had zero test coverage before this pass** — added `tests/services/pipecat_voice/test_speculative_prefetch.py` (12 mutation-proof tests: min_chars gate, cancel-and-restart on partial growth, write-shaped safety gate never warms a live read for a write-intent utterance, `CancelledError` re-raises rather than being swallowed, ordinary failures never crash the pipeline). |
| 2. Speculative **LLM generation** begins on a "probable EOT" signal, cancels on continued speech, reusing the existing barge-in cancellation | **NOT BUILT.** This is a materially larger, riskier change (predicting "probably done" from Flux's interim signals, launching a real LLM call speculatively, and safely canceling/discarding it if wrong) than Phase 1's item 1 (read-only cache warming). No such mechanism exists in this codebase today. Flagging this honestly rather than claiming partial credit as done — the existing `speculative_prefetch.py` only ever does read-only *cache warming* (memory/embedding/knowledge lookups), never launches or cancels a real answer-generation model call. |
| 3. Validate speculative intent against final transcript and **continue** generation rather than restart | **NOT BUILT** (depends on #2 existing first). |
| 4. Live, timestamped proof of genuine overlap | Confirmed for item 1 only — `pipecat_speculative_prefetch` log line fires on interim transcripts before EOT (code-level evidence; a fresh live-timestamped capture was not re-run this pass beyond the existing shipped log line). |
| 5. Mutation proof for the speculative-cancel path | **Done for item 1** (`test_growing_partial_cancels_the_stale_prefetch_task` — asserts the stale `asyncio.Task` object is actually cancelled, not just replaced). No mutation test exists for items 2–3 because they don't exist yet. |

**Honest summary: Phase 1 is half-real.** The safe, low-risk half (speculative *read-only* prefetching on partial transcripts) is live and now tested. The higher-value, higher-risk half (speculative *LLM generation* with cancel/continue) — which is what would actually let a "what is two plus two" turn start answering before the user finishes the sentence — does not exist. This is the single largest remaining lever to close the P50<500ms gap and was not attempted in this pass given its scope (a genuinely new mechanism, not a fix to an existing one) — flagged as the top follow-up, not silently claimed done.

---

## Phase 2 — Semantic chunking for TTS

**Finding: already NOT sentence-blocking in the naive sense — genuinely incremental, sentence-boundary-based, with a long-clause fallback.**

`app/services/voice_session_service.py::split_speakable_chunks()`:
- Emits a speakable chunk the moment a sentence-terminal boundary (`.`/`!`/`?`) appears in the streaming buffer — it does **not** wait for the full response.
- For a clause that grows very long (≥`min_chars*3` or 80 chars) with no terminal punctuation yet, it falls back to flushing on the last comma or space — an escape valve against unnaturally long TTS-blocking runs.
- `cognitive_llm.py` records `llm_first_speakable_chunk_ms` distinctly from `llm_first_token_ms` — golden signals show these two are within ~50ms of each other on the p50 (2030ms vs 1983ms measured this pass), confirming the *first* chunk really is emitted close to the first token, not after the whole answer.

This is not literally "semantic" chunking (it doesn't measure prosody quality directly), but it already satisfies the real requirement ("stream speakable chunks as soon as enough text exists," not "wait for complete sentences across the whole answer"). No change made this pass — re-architecting a working, already-incremental chunker without a demonstrated quality/latency problem in it specifically would be an unjustified risk given the real bottleneck (Phase 1/3) sits upstream of TTS entirely.

---

## Phase 3 — Fast routing layer (CONVERSATION / KNOWLEDGE / ACTION)

**Finding: a two-way depth gate exists and is real; it is not the exact three-way intent classification requested.**

`agent_intelligence.py` (~line 2111) sets `reasoning_depth = "conversational"` for spoken turns when `routing_control.tier == "simple"` (or `requested_mode == "fast"`) **and** the turn is not classified consequential. `cognitive_turn_kernel.py`'s `KNOWLEDGE` stage (~line 187) skips the full RAG/Knowledge-Fabric merge entirely when `reasoning_depth == "conversational"` ("Conversational spoken depth keeps RECALL + GOVERN; skips heavy retrieval" — existing code comment, not written this pass).

**Real gap, flagged honestly:** `routing_control.tier == "simple"` is a **cost/complexity** signal (reused from the text-latency `assistant_routing_tier`/`complexity_routing_guardrails` tiering), not an **intent** signal. A real information question that happens to be classified "simple" tier (e.g., a short factual question) would currently get `reasoning_depth="conversational"` and **skip RAG** — which is different from this prompt's requested three-way split, where a real KNOWLEDGE question should always trigger retrieval regardless of tier. This is a genuine, currently-live discrepancy between "cheap to answer" and "needs no retrieval," not something this pass fixed (reusing vs. replacing this tiering, as the prompt itself demands — "do not build a second, separate classifier" — needs a product decision on whether tier should also encode "needs retrieval," which is a data/behavior change, not just a plumbing one). ACTION-shaped turns correctly retain full depth via the `is_consequential_classification` check.

---

## Phase 4 — Hierarchical tool routing for voice

**Confirmed: shared infrastructure, not duplicated for voice.** `_stable_tool_list()` (stable ordering for prefix-cache hits) and the narrowed-tools/progressive-disclosure schema mechanism in `unified_turn_reasoning_service.py` are called from the single shared `agent_intelligence.execute_task_streaming()` orchestrator used by both text and voice (`spoken_mode` is a flag on the same call, not a fork). The earlier `full_schema_not_loaded` auto-recovery fix (this session, prior turn) was specifically needed *because* voice hits this same progressive-disclosure narrowing path. No separate voice-only 727-tool catalog attachment exists.

---

## Phase 5 — Progressive narration while tools execute

**Confirmed live from the prior conversational-realism pass**, re-verified this pass:
- `voice_tool_narration.py` `narrate_tool_started`/`narrate_tool_completed`, wired into `cognitive_llm.py`'s `tool-input-available`/`tool-output-available` SSE handling (classical ReAct path).
- `will_execute_staged_connector_write`/`narrate_connector_write_executing` for the governed `run_connector_turn` path (this session's `phase3-connector-gap` fix).
- **This pass additionally closed the remaining known silence**: traced every branch of unified-turn LIVE (`apply_unified_turn_live`) and confirmed it never itself executes a write — it only stages an approval ask or defers to one of the two paths above, both already covered. See `docs/delivery/unified-turn-live-write-narration-gap-closed-2026-09-05.md` and 7 new regression tests. No new narration hook was warranted (adding one would risk a false-positive "I'm doing that now" on a turn that only staged an approval ask — strictly forbidden by this program's own Phase 3 rule).
- Hard constraint (never claim before real state) unchanged and enforced by existing tests — not touched this pass.

---

## Phase 6 — Warm, persistent connections

**Confirmed: one pipeline per browser WebSocket connection, not per turn.** `app/routers/pipecat_voice.py`'s WS endpoint calls `build_pipecat_voice_task()` once and `PipelineRunner().run(task)` blocks for the life of that one browser connection; Deepgram STT and ElevenLabs TTS service objects (and their own WS connections) are constructed once per session, not once per turn.

**One real, live risk found and flagged (not fixed this pass, out of the requested scope of "confirm"):** the STT-provider fallback loop in the same file re-runs `build_pipecat_voice_task` + a brand-new `PipelineRunner` from scratch **if `runner.run(task)` raises for any reason** (e.g., an unhandled exception anywhere in a single turn's frame processing). That would tear down and rebuild every connection (browser WS handling aside, at minimum the STT/TTS service objects) mid-conversation — a plausible, honest candidate explanation for an occasional severe (multi-second-to-tens-of-second) outlier distinct from the steady-state baseline, exactly the shape of bug the prompt asked to look for in Phase 10. No live evidence of this actually firing was found in the log window checked this pass (a live `railway logs` tail, not a full historical search) — reported as a plausible, not confirmed, root cause for outliers, per the audit-evidence standard (no PASS claimed without positive evidence).

---

## Phase 7 — Cache static context, inject only deltas

**Confirmed, shared infra, not voice-specific:** `unified_turn_reasoning_service.py::_stable_tool_list()` — "Stable ordering so OpenAI automatic prefix caching can hit across turns" (existing code comment). This is OpenAI's own automatic, server-side prefix caching (not a custom cache Gravitre manages), so a "measured hit rate" is not directly observable from this codebase without OpenAI's own cache-hit token-usage field, which was not instrumented/queried this pass — flagged as NOT MEASURED rather than assumed.

---

## Phase 8 — Geographic/network path

**Partially audited.** Railway backend region confirmed **US East** (`railway status`). Deepgram and ElevenLabs both operate their own global edge/anycast networks (not colocated with any single customer's compute) — no explicit region-pinning exists or was found between Railway, Deepgram, and ElevenLabs. A deeper network path trace (e.g., `mtr`/`traceroute` from Railway's actual runtime to Deepgram/ElevenLabs endpoints) was **not performed** this pass — flagged as NOT RUN rather than assumed benign.

---

## Phase 9 — Cascaded architecture, deliberate

Already documented: `docs/delivery/voice-cascaded-architecture-decision-2026-09-05.md` (prior turn this session). Restated as still current; no change.

---

## Phase 10 — Real, honest, final measurement against the three SLOs

**Method:** `scripts/measure-voice-pipecat-live-latency.py` against the deployed tip `cd04d203`, three scenarios (8/5/3 runs), via `railway run` (real env vars, real production WS). Golden signals (`load_golden_signals_dashboard`) queried separately for a 24h real-traffic window (25 real turns, includes traffic both before and after this pass's deploy).

### Probe results (this pass's deployed tip, fresh run)

| Scenario | P50 | P95 | vs. SLO (P50<500ms / P95<800ms) | n |
|---|---|---|---|---|
| `simple_conversational` | **2,784 ms** | **3,783 ms** | **NOT MET** (5.6x / 4.7x over) | 8 |
| `knowledge_lookup` | **4,429 ms** | **5,356 ms** | **NOT MET** (8.9x / 6.7x over) | 5 |
| `consequential_write_shaped` | **11,795 ms** | **14,551 ms** | **NOT MET** (23.6x / 18.2x over) | 3 |

### Golden signals, 24h real-traffic window (25 samples)

| Stage | P50 | P95 | P99 |
|---|---|---|---|
| `user_turn_finalization` (STT EOT) | 2 ms | 5 ms | 115 ms |
| `llm_first_token` (reasoning TTFT) | 1,983 ms | 9,230 ms | 12,283 ms |
| `llm_first_speakable_chunk` | 2,030 ms | 9,231 ms | 12,284 ms |
| TTS TTFB (ElevenLabs) | 120 ms | 159 ms | 169 ms |
| `end_to_end` | 2,397 ms | 10,013 ms | 13,555 ms |

**Honest interpretation:**
- **Real, measured improvement from this pass's two parallelization fixes**: `simple_conversational` P50 dropped from the prior baseline (~8.6s, `voice-latency-8to13s-gap-rootcause-2026-09-04.md`) to **2.8s** — roughly a **3x** reduction. `knowledge_lookup` similarly improved. This is a genuine, live-confirmed win from fixing Class B (sequential-not-parallel) processing, exactly the Phase 0 hypothesis.
- **None of the three SLOs are met.** P50<500ms is missed by 5.6x–23.6x depending on scenario. This is stated plainly, not softened.
- **STT/EOT is not the bottleneck today** (2–115ms) — the earlier "6.3s Flux watchdog" finding does not reproduce in this pass's golden-signal window; the dominant cost is squarely `llm_first_token` (reasoning stage), consistent with Phase 1's unbuilt speculative-LLM-generation gap being the single highest-value remaining fix.
- **P95/P99 tail is severe relative to P50** (llm_first_token p50=1,983ms vs p99=12,283ms — a >6x tail-to-median ratio). This directly matches this prompt's own warning that "occasionally answers in 280ms but spikes to 1.8s on every fifth turn is worse than reliably landing at 500–600ms" — Gravitre's voice path currently has this exact shape of problem, at a larger scale.
- **`consequential_write_shaped` remains the worst category** (P50 11.8s), consistent with this program's own accepted tradeoff for governance/verification-heavy write turns (per the existing text-latency precedent) — but 11.8s is still far outside even a generous "accepted tradeoff" range and has not been separately investigated for a write-specific root cause beyond what's already documented in the 8–13s gap doc (extra sequential LLM calls, progressive tool-disclosure rounds).
- **Sample sizes are small** (3–8 runs per scenario) — real p50/p95 confidence at this N is limited; this is reported honestly rather than presented as statistically robust.

### 16-second-outlier investigation

The specific bug this prompt asked to find (a distinct outlier cause, not just "the baseline is slow") was **not conclusively identified** this pass. One plausible, code-level candidate was found and documented (Phase 6 — a mid-conversation exception triggering a full STT-fallback pipeline rebuild) but has **no positive live-log evidence** confirming it actually fired for any of the historically-reported 16s cases — reported as PARTIAL / a lead, not a closed root cause.

### Verification status against this prompt's own bar

| Requirement | Status |
|---|---|
| Real, honest Phase 0 sequential-vs-parallel finding | **Done** — sequential was the real root cause; two real fixes shipped |
| Real, live, timestamped proof of genuine speculative overlap | **Partial** — proven for read-only prefetch only; speculative LLM generation does not exist |
| Mutation-tested proof for every new mechanism | **Done** for what was built this pass (parallelization, narration-gap closure, prefetch tests) |
| Real p50/p95/interruption-to-silence vs. three SLOs, representative sample | **Done, honestly failing** — none of the three SLOs met; interruption-to-silence was not separately measured this pass (no dedicated probe scenario exercises barge-in latency) — **flagged as NOT MEASURED**, not assumed |
| 16-second-outlier root cause found and fixed | **NOT DONE** — one plausible lead documented, not confirmed or fixed |
| Human-verified final confirmation from Cesar | **NOT DONE** — per this program's standing rule, this is the only closing proof for voice and has not happened |

## Bottom line

This pass shipped two real, tested, deployed fixes for genuine sequential-processing bugs (pre-kernel calls, RECALL's five memory stores) and closed one investigation (unified-turn-LIVE narration gap — found to be a non-issue by design, not fixed by adding code). Measured, live improvement is real (~3x on simple/knowledge turns) but **all three new SLOs remain unmet, most severely on write-shaped turns**. The single highest-value remaining lever — genuine speculative LLM generation on probable-EOT with cancel/continue (Phase 1, items 2–3) — was not attempted this pass; it is a new mechanism, not a fix, and is the honest next step for materially closing the P50<500ms gap. No human verification has occurred; per standing program rule, voice is not to be called "fixed" without it.

## Addendum (same day) — corroboration + one more real fix shipped

Four parallel investigations run after the above was written corroborated the
findings above with more precise file:line evidence, and surfaced one more
genuine, previously-undocumented "warm connection" gap that has now been
fixed:

1. **[Locate unified-turn LIVE write execution path](f0fd3874-540c-43b9-a87d-84d4bf922fd9)** and **[Fix unified-turn LIVE write narration gap](2bd73da9-ba71-4d2e-be8a-d3cc014cc7b0)** — both independently traced `apply_unified_turn_live()` and reached the identical conclusion already documented above and in `unified-turn-live-write-narration-gap-closed-2026-09-05.md`: no execution path exists there, no new hook was warranted. No further action.

2. **[Run live voice probe + correlate Railway logs for exact bottleneck](438109c5-1c62-47b3-aaf2-bf34b22a3a58)** — live Railway log correlation (same `org_id`, timestamps inside the probe window) confirmed the pre-kernel parallelization fix's expected signature: `connected_integrations` (+1126ms), `mcp_tools` (+99ms), `engine_settings` (+18ms) — one large delta followed by two tiny ones is exactly what three genuinely-concurrent operations look like once `asyncio.gather` returns and checkpoints are logged back-to-back, versus three roughly-equal sequential deltas before the fix. Checked `connector_snapshot_cache.py`: this org's `connected_integrations` cost is a **45-second-TTL cold-cache** cost (`_DEFAULT_TTL_SECONDS = 45`), not a per-turn recurring one — a real multi-turn conversation only pays this once per 45s window, not every turn. No further fix made; documented rather than chased, since the cache already exists and is correctly sized.
   - Also surfaced a real, currently-unattributed ~2.7s gap between `pre_kernel_entry` and the model call firing, beyond what RECALL's own ~311ms accounts for — flagged as a genuine, not-yet-investigated remaining latency contributor for a future pass.

3. **[Audit Phase 4/6/7/8 for voice pipeline](294e9aa6-b204-438c-9426-3406e48d5ab9)** — corroborated Phases 4/7/8 above with precise citations, and sharpened Phase 6: `CognitiveTurnKernel` is a fresh instance per turn (cheap, not a network connection, not a concern); Supabase client is turn-scoped (already conditionally reused when passed in — left as-is); **`AnthropicAdapter` constructed a brand-new `AsyncAnthropic()` client (and its underlying `httpx.AsyncClient`) on every single `complete()`/`stream()` call — no TCP/TLS connection reuse across turns**, unlike the OpenAI adapter's process-singleton pattern in `model_router.py`. This is a real, fixable "not persistent" connection gap, exactly Phase 6's subject.

   **Fixed this addendum:** `anthropic_adapter.py`'s `AnthropicAdapter` now lazily constructs and caches one `AsyncAnthropic` client per `(api_key, timeout)` key (`ANTHROPIC_API_KEY` is a single process-wide setting, so this is safe — and still correctly rebuilds if the key ever rotates mid-process). Same fix applied to the module-level `_complete_anthropic_with_tools()` in `provider_tool_router.py` via a module-level cache dict. New tests: `tests/services/providers/test_anthropic_adapter_client_reuse.py` (4 tests, mutation-proof: asserts exactly one construction across 3 `complete()` calls, same cached object reused, key rotation still invalidates, `stream()` shares the same cache as `complete()`). All existing provider/model-router tests (39 total across the touched files) still pass.

## Addendum 2 (same day) — genuine speculative LLM generation shipped, re-measured

Closes the Phase 1 gap flagged above ("the higher-value, higher-risk half ...
does not exist"). Implementation: `speculative_generation.py` (new
coordinator), `speculative_prefetch.py` (starts a real, cancelable
`execute_task_streaming()` call on Deepgram Flux's `ProposedUserStoppedSpeakingFrame`,
gated by the same write-shaped conservatism as the existing read-only
prefetch), `cognitive_llm.py` (adopts the run at confirmed end-of-turn on an
exact normalized-text match, else falls back to a fresh call — zero
regression risk). 19 new tests, mutation-proof (verified live: disabling the
cancel-on-new-partial check and the adopt() check each independently fail
their respective tests). Deployed and confirmed live at `git_sha=0c3c9bc4`.

### The mechanism works exactly as designed — real evidence, not inferred

Railway logs for the re-measurement window: **16 `speculative_generation_started` / 16 `speculative_generation_adopted` — a 100% adoption rate** across all three scenarios' probe runs. Measured `started`→`adopted` head-start per turn (real wall-clock, from log timestamps): **min 118ms, median 141ms, mean 202ms, max 625ms** (n=16).

**Honest characterization of that head-start:** it is real but modest for this specific probe methodology — synthesized speech fed as one continuous block plus fixed trailing silence gives Flux's "probable EOT" and "confirmed EOT" very little daylight between them (a clean, scripted utterance has none of the trailing-intonation ambiguity a real human sentence has). A real human speaker's more gradual, cue-driven end-of-utterance would plausibly give Flux's probabilistic signal more lead time over the confirmed cutoff — this is a reasonable expectation, not a measured fact; it has not been verified with real human speech and is not claimed as such.

### Re-measurement: probe scenarios (before → after)

| Scenario | P50 before (`cd04d203`) | P50 after (`0c3c9bc4`) | P95 before | P95 after |
|---|---|---|---|---|
| `simple_conversational` | 2,784 ms | **2,504.5 ms** (−10%) | 3,783 ms | 5,286 ms (worse — n=8, high variance, not attributed to a regression) |
| `knowledge_lookup` | 4,429 ms | **3,056 ms** (−31%) | 5,356 ms | **3,485 ms** (−35%) |
| `consequential_write_shaped` | 11,795 ms | 10,845 ms (−8%, expected — speculation deliberately does not apply here) | 14,551 ms | 13,196.7 ms (−9%) |

### Re-measurement: golden signals, real production instrumentation (1h window, 16 fresh samples, all post-deploy)

| Stage | P50 before (24h mixed window) | P50 after (1h, all fresh) | P99 before | P99 after |
|---|---|---|---|---|
| `llm_first_token` | 1,983 ms | **1,316 ms (−34%)** | 12,283 ms | **8,735 ms (−29%)** |
| `end_to_end` | 2,397 ms | **2,141 ms (−11%)** | 13,555 ms | **11,663 ms (−14%)** |

### Honest verdict against the three SLOs

**None of the three SLOs (P50<500ms, P95<800ms, interruption-to-silence<150-200ms) are met.** Real, measured, positive movement — most clearly on `knowledge_lookup` and on `llm_first_token`/`end_to_end` tail latency (P99) — but `knowledge_lookup` P50 at 3,056ms is still 6.1x over the P50<500ms target (down from 8.9x), and `simple_conversational` P95 got measurably worse in this run (small-N noise, not a known regression — flagged, not hidden). `consequential_write_shaped` barely moved, exactly as expected: speculative generation is deliberately gated off for write-shaped text (staging an approval/ledger write against unconfirmed speech is a correctness risk, not just a latency one — see the module's own docstring).

The 100% adoption rate proves the mechanism is real and functioning correctly end-to-end; the modest scale of improvement is explained by the small, probe-methodology-specific head-start window (118-625ms), not by the mechanism failing to engage. Interruption-to-silence was not measured this pass (no probe or golden-signal instrumentation exists for it yet — an honest gap, not silently assumed met).

**This is real, incremental, verified progress — reported now rather than held back for a perfect SLO result, per this pass's own instruction.** No human verification has occurred; per standing program rule, voice is not to be called "fixed" without it. This is the right moment for that verification: the pipeline is measurably, honestly improved over the prior baseline, not just re-confirmed unchanged.

## Addendum 3 (same day) — `llm_first_token` Phase 0 audit: real numbers overturn the single-call-latency premise

**MANDATORY PRE-FLIGHT for this pass:** full regression battery re-run before any change — 245 passed (`pipecat_voice`, `providers`, `unified_turn_*`), zero failures. Carries forward the 19 speculative-generation tests and the provider client-reuse tests confirmed above.

### What shipped

Real (not `len//4`-estimated) per-source token counting on the unified-turn LIVE path voice actually serves (`apply_unified_turn_live` → `run_unified_turn_shadow`'s single-call completion): `app/services/real_token_counter.py` (offline `tiktoken`, new dependency in `requirements-core.txt`), instrumented into `unified_turn_reasoning_service.py` as `context_size_breakdown` (per source: `system_prompt`, `conversation_history`, `tool_schemas`, `connected_integrations`, `knowledge_fabric`, `memory_recall`, `kernel_knowledge_section`, `outcome_bias`, `pending_state`, `tools_list_note`, `standing_corrections`, `user_message`) and `context_real_tokens_total`, logged in `unified_turn_shadow_breakdown` alongside the real, provider-reported `prompt_tokens`/`cached_prompt_tokens` already present. 4 new mutation-proof tests (`test_unified_turn_context_size_breakdown.py`): asserts real tiktoken counts differ from the naive chars-as-tokens mutation, asserts every real source is present/non-trivial, asserts `conversation_history`/`tool_schemas` actually reflect what was passed in. Deployed and confirmed live at `git_sha=3e1c0d1d`.

### Phase 0 item 3 (prompt-caching behavior): confirmed real and already near-100% — no gap to fix

Real production evidence (16 live turns, fresh probe run, isolated org, post-deploy at `3e1c0d1d`): **`cached_prompt_tokens == prompt_tokens` on 16 of 16 warm turns** (the one cold turn immediately after deploy, 7s post-health-check, was the sole `0/0` — a real, expected one-time cold-start artifact, not a steady-state miss). Real token counts observed: `prompt_tokens` 3,712–6,272 across turns, **100% of that returned as cache hit** every single time. This is OpenAI's automatic native prompt caching (kicks in for stable prefixes ≥1024 tokens, no `cache_control` markers needed — that requirement is Anthropic-specific) already working exactly as it should on the real, live-served model (`gpt-5.4-mini`, confirmed via `inference_provider=openai` on every sampled turn — the default `_resolve_model()` path always resolves an OpenAI model for voice unless an agent has an explicit non-OpenAI override, so the earlier finding "no `cache_control` used anywhere" was real but not the operative gap: Anthropic isn't the model actually serving voice by default).

**Conclusion: Phase 2 (fix prompt-caching gaps) has no real gap to close on the path voice actually uses today.** Not built — building a fix for an already-~100%-hit-rate mechanism would be scaffolding without a diagnosed need.

### Phase 0 items 1–2 (context size vs. the p99 tail): real correlation — and it overturns the "single-call context bloat" hypothesis

Real per-source breakdown from the same 16-turn run (`context_size_breakdown`, `context_real_tokens_total`):

| Scenario | `messages_chars` | `context_real_tokens_total` | single-call `model_ttft_ms` (this call only) |
|---|---|---|---|
| `simple_conversational` (n=8) | 25,370 | 6,579–6,787 | 442–792 ms |
| `knowledge_lookup` (n=5) | 25,431 | 6,704 | 417–663 ms |
| `consequential_write_shaped` (n=3) | 25,649 | 6,623–6,704 | 440–549 ms |

Context size across all three scenarios is **within ~1% of each other**, and the single-call `model_ttft_ms` is **actually lowest for `consequential_write_shaped`**, not highest. Per-call context bloat does **not** explain the p99 tail — the hypothesis in Phase 0 item 2 is real, honestly tested, and **not confirmed**.

**What actually explains the tail (real, correlated, from `pipecat_voice_turn_latency` logs grouped per voice turn by `turn_start`):**

| Scenario | n | LLM round-trips per turn (`data-intelligence` events before spoken text) | `first_text_delta_ms` (real, matches the golden-signal `llm_first_token` metric) |
|---|---|---|---|
| `simple_conversational` + `knowledge_lookup` | 13 | **2–3** | 1,011–1,848 ms |
| `consequential_write_shaped` | 3 | **6** | **8,223–9,634 ms** |

This lines up almost exactly with the golden-signal numbers already reported in Addendum 2 (`llm_first_token` P50 1,316ms / P99 8,735ms) — the fast-tier turns cluster near the P50, the write-shaped turns cluster near the P99. **The tail is real and it is `llm_first_token` as measured — but it is the sum of 6 chained LLM round-trips (tool-call → tool-execute → tool-call → ... → final spoken answer), not one slow call with a bloated prompt.** Individual round latencies for the write-shaped turns ranged ~330ms–3.9s each; two of the six rounds in each write-shaped turn were themselves ~3.2–3.7s (real tool-execution/round latency, not raw single-call LLM inference — each round's own `model_ttft_ms` stayed under ~550ms per the table above).

### Honest re-scoping recommendation (Cesar's decision, not built unilaterally)

Given real evidence: **Phase 1 (voice-specific context trimming) and Phase 2 (prompt-caching fixes) as originally scoped would not move the p99 tail** — the per-call context is already small and ~100%-cached; the tail is round-count and tool-execution latency in the classical multi-step path that `consequential_write_shaped` turns fall into, not the single-call LLM completion Phase 0–2 targeted. Recommend redirecting effort toward: (a) reducing round-count for write-shaped voice turns (e.g., can knowledge-lookup + connector-status checks be parallelized/pre-fetched into one round instead of sequential tool calls — the existing speculative-prefetch read-only cache-warming mechanism already touches this), and (b) attributing the ~3.2–3.7s individual slow rounds to a specific tool/operation rather than assuming they are LLM-side. **Not built without sign-off** — this changes the shape of the remaining work from "shrink the prompt" to "shrink the round-count," a different, real problem. Phase 3 (Groq/Cerebras evaluation) is unaffected by this finding and remains a live option regardless of which problem Phase 1 targets, since faster per-round inference still helps a multi-round chain — but it would not fix the round-count itself.

## Addendum 4 (2026-09-06) — round-count redirect: first blocking-I/O fix on the write-shaped classical path

Per Cesar's decision on the Addendum 3 recommendation (`redirect_round_count`): investigating which of the 6 chained LLM/tool round-trips in `consequential_write_shaped` turns are actually slow, starting with the pre-kernel connector-availability check.

### What was found

`execute_task_streaming` in `agent_intelligence.py` called `prefetch_connected_integrations(client, org_id, environment_name=...)` as a **plain synchronous function call from inside an async function**. That does not make it background work — it blocks the coroutine (and, since there is no `await`, the whole event loop) for however long `list_executable_integrations()`'s live, per-connector, sequential network checks take when `force_live=True`. A live probe caught this directly: one `consequential_write_shaped` turn logged `list_connected_integrations_failed org_id=<id> force_live=True error=[Errno 11] Resource temporarily unavailable` at the exact moment `classical.answer_path.reached` fired — a resource-exhaustion error from a blocking call stacking up against other in-flight work, immediately preceding one of the multi-second gaps between rounds already identified in Addendum 3.

### Fix shipped

Extracted the call into `_schedule_connected_integrations_prefetch()`, which genuinely backgrounds it: `asyncio.to_thread(prefetch_connected_integrations, ...)` (it does blocking I/O, not just something that needs an event-loop yield) wrapped in `asyncio.create_task(...)`, never awaited inline. The task's own strong ref is kept in a module-level `_PREFETCH_BACKGROUND_TASKS` set with a `add_done_callback` to discard it on completion, so it cannot be garbage-collected mid-flight when the enclosing turn's generator returns quickly, and cannot leak. The call's return value was never consumed by the caller either before or after this fix — it is, and always was, a best-effort cache-warm for `connector_snapshot_cache` (its own docstring already promised "safe to call fire-and-forget"); this fix is what actually makes that true.

### Mutation proof

New test `test_schedule_connected_integrations_prefetch_does_not_block` in `tests/operators/test_agent_intelligence.py`: patches `prefetch_connected_integrations` to sleep 0.3s, asserts `_schedule_connected_integrations_prefetch()` itself returns in <0.15s, asserts the task is strong-ref'd in `_PREFETCH_BACKGROUND_TASKS` while in flight and discarded once complete, then `await`s the task directly to confirm it actually ran to completion (not dropped/never scheduled). **Confirmed by reverting the fix to a direct synchronous call and re-running**: test fails with `scheduling took 0.301s but must return almost immediately` — proving the test would have caught the original bug.

### Regression battery

Full backend suite re-run after the fix: **5590 passed, 3 skipped, 0 failed** (30m45s, `pytest tests/`). `tests/operators/test_agent_intelligence.py` alone: 24 passed (23 pre-existing + 1 new).

### Honest scope of this fix

This addresses one of the 6 rounds' pre-kernel setup, not the round-count itself — `consequential_write_shaped` turns still make 6 sequential LLM/tool round-trips; this only removes a blocking-I/O tax that could stack onto any one of those rounds' wall-clock time (and, per the caught `Errno 11`, could make things worse than a normal live check under contention). It has **not yet been re-measured against the live SLOs** — Phase 4 re-measurement (this doc's own outstanding item) is still required, and other candidate slow-round contributors (e.g., the ~3.2–3.7s per-round tool-execution gaps identified in Addendum 3) have not yet been individually traced. Not claiming this closes the round-count gap; it removes one confirmed, real blocking-I/O source found while tracing it.

## Addendum 5 (2026-09-06) — per-tool latency instrumentation + Phase 3 (Groq/Cerebras) honest evaluation

### Per-tool latency instrumentation (continuing the round-count trace)

Addendum 4's fix removed one confirmed blocking-I/O source but did not yet identify which of the 6 chained rounds' own ~3.2–3.7s "tool-execution latency between LLM calls" (Addendum 3) come from which specific tool. `pipecat_voice_turn_latency` only logs at LLM-call boundaries (`data-intelligence` events) — there was no per-tool timing at all.

**Shipped:** `GravitreCognitiveLLMService._run_gravitre_turn` (`cognitive_llm.py`) now logs `pipecat_voice_tool_latency org_id=<id> tool=<name> elapsed_ms=<real ms> since_turn_start_ms=<real ms>` — real wall-clock time between a specific tool's `tool-input-available` and its matching `tool-output-available` event, keyed by `toolCallId` (reuses the same `tool_names_by_call_id` pairing already proven for honest tool narration). 4 new mutation-proof tests (`test_cognitive_llm_tool_latency.py`): asserts the log line names the real tool and measures the real elapsed delay (not hardcoded), asserts multiple concurrent tool calls are each attributed to their own name, asserts an output with no matching input (defensive edge case) stays silent rather than fabricate a `0ms` reading, asserts `since_turn_start_ms` is present for round correlation. Regression: `tests/services/pipecat_voice/` 132 passed (0 failures) after the change.

**Not yet done:** this instrumentation needs one more live probe run against `consequential_write_shaped` turns, followed by a fresh Railway log pull, to actually name the slow tool(s) — that is the next concrete step, not yet executed as of this addendum.

### Phase 3 — honest, diagnosis-only evaluation of Groq/Cerebras (no production change)

**Real, current (2026) published numbers** (WebSearch, cross-checked across 2 sources per provider):

| Provider | Model | Published TTFT | Published decode speed | Input/output $ per 1M tokens | Function calling |
|---|---|---|---|---|---|
| Groq (LPU) | `openai/gpt-oss-120b` | ~710–730ms median (Artificial Analysis, includes reasoning "thinking" time) | ~500 tok/s | $0.15 / $0.60 | Yes (strict mode, parallel) |
| Groq (LPU) | `openai/gpt-oss-20b` | faster (smaller model), not separately reported | ~1,000 tok/s | $0.075 / $0.30 | Yes |
| Cerebras (WSE-3) | `gpt-oss-120b` | ~50ms at batch 1 (isolated hardware number, no network/queueing) | ~3,000 tok/s | $0.35 / $0.75 | Yes |
| Cerebras (WSE-3) | `llama-3.1-8b` | not separately reported | ~2,000–2,200 tok/s | $0.10 / $0.10 | Yes |

**Gravitre's own real, live-measured numbers for the exact tier this would target** (`simple_conversational`, from Addendum 3's same 16-turn probe, model `gpt-5.4-mini` on OpenAI): single-call `model_ttft_ms` **417–792ms**, real end-to-end `first_text_delta_ms` (includes STT + pipeline overhead on top of that) **1,011–1,848ms** across 13 turns (`simple_conversational` + `knowledge_lookup` combined).

**Honest correlation, not a sales-pitch comparison:** Gravitre's current single-call TTFT on the exact tier this would target (417–792ms) is **already in the same range as, or faster than, Groq's own published TTFT for a comparable reasoning-capable open model (710–730ms)**. Cerebras's ~50ms figure is a bare-hardware number at batch 1, not directly comparable to a real, network-in-the-loop, reasoning-enabled production call — real Cerebras TTFT under production conditions was not found published anywhere in this search and would need to be measured directly (via their free tier) before being treated as real. The one honest, clear structural win either provider offers is **decode speed** (500–3,000 tok/s vs. OpenAI's typical ~40–100 tok/s) — this shortens total generation time for longer responses, but most `simple_conversational` voice replies are short (1–2 sentences), so the practical benefit on the SLO that matters (TTFA) is smaller than the raw decode-speed numbers suggest.

**Honest constraint (per the standing discipline):** this is a genuinely different model — `gpt-oss-120b` or a Llama/Qwen variant, not `gpt-5.4-mini` — with its own real reasoning-quality profile that has not been evaluated against Gravitre's actual conversational turns. No quality comparison has been run; none should be assumed.

**Added real cost not captured in the token-pricing table:** zero existing adapter code for either provider in this codebase (`grep` for `groq`/`cerebras` in `backend/app`: no matches) — this would be a from-scratch provider integration (new client, streaming/tool-call-shape compatibility check with the existing `provider_tool_router.py` abstraction, monitoring, fallback-on-provider-outage logic), not a config flip.

**Honest recommendation (Cesar's decision, not built unilaterally):** given (a) Gravitre's own current TTFT for the targeted tier is already competitive with Groq's published number and not clearly beaten by it, (b) Cerebras's dramatically lower number is an unverified bare-hardware figure for this use case, (c) the real bottleneck this program has actually diagnosed and is fixing (Addenda 3–5) is round-count/tool-execution on `consequential_write_shaped` turns — a problem a faster-but-different model for the *simple* tier does not address at all, and (d) the real added integration/maintenance cost of a second provider — **this is not obviously worth pursuing before Phase 4 remeasures where Addenda 4–5's fixes land relative to the SLOs.** If Cesar wants it evaluated further regardless, the concrete next step (not yet done) would be a real, measured TTFT/quality comparison against Gravitre's own free-tier Cerebras and Groq accounts on Gravitre's actual `simple_conversational` sample turns — not published numbers — before any bounded pilot design. **No production model/provider change made or proposed as ready to build.**

## Addendum 6 (2026-09-06) — live per-tool probe: tool execution ruled OUT as the round-count driver

Ran the new `pipecat_voice_tool_latency` instrumentation (Addendum 5) live against `consequential_write_shaped` turns immediately after deploy (`git_sha=06a325e6`, 2 real turns via `railway run` + the existing write-shaped-only probe helper, fresh Railway log pull for the exact window `07:26:51`–`07:27:33Z`).

### Real, honest finding — corrects part of Addendum 3

**The tool call itself was not slow.** Both real runs show `pipecat_voice_tool_latency ... tool=searchKnowledgeBase elapsed_ms=0` — the search-knowledge-base tool genuinely completed in under 1ms both times. Addendum 3's attribution of the 3.2–3.7s gaps to "tool-execution latency between LLM calls" is **not supported** by this more granular, per-tool evidence — at least for this tool, on this turn shape.

**What the gaps actually are, per real log-line timing (run 1, `since_turn_start_ms` at each successive `pipecat_voice_turn_latency` line):** 729 → 927 → 3,894 → 6,793 → 6,795 (tool call, 0ms) → 10,861 (first spoken token). The ~2.9s gap (927→3,894) and ~2.9s gap (3,894→6,793) both occur **before any tool call starts** — there is no tool-latency line inside either gap. The final ~4.1s gap (6,795→10,861) comes entirely **after** the (0ms) tool call finished. None of these three multi-second gaps can be tool execution; each one has to be real wall-clock time inside the classical/orchestrator loop's own round — most plausibly LLM inference for that round (deciding the next step / generating the next message), though this specific log line does not carry `model_ttft_ms` for the classical multi-step path (it's logged `None` on every single one of these lines, live-confirmed) — that field is only populated on the unified-turn direct path today, not this one. Run 2 shows the same shape: 335 → 565 → 3,381 → 5,445 → 5,445 (tool, 0ms) → 6,787 (first token) — two ~2.8s/~2s pre-tool gaps, ~1.3s post-tool gap.

**Zero regression confirmed in this same window:** no `list_connected_integrations_failed` error (Addendum 4's fix holding under real production load), speculative-generation adoption logged on both runs (`pipecat_voice_speculative_generation_adopted`).

**Honest, corrected next step (not yet done):** the real remaining gap is per-round LLM inference time inside the classical ReAct/orchestrator loop specifically, which is not currently instrumented with its own `model_ttft_ms` the way the unified-turn direct path is. Closing that gap requires adding that specific instrumentation to the classical path next, not further tool-execution tracing — tool execution has now been directly measured and ruled out as this turn's driver.

## Addendum 7 (2026-09-06) — Phase 4: real, honest re-measurement vs. all three SLOs and full prior history

Full 3-scenario live probe re-run against the currently-deployed tip (`git_sha=06a325e694e8b9bb2febb7b062e1076fbc14c557`, includes Addenda 4–6's round-count fix + tool-latency instrumentation), same methodology/probe script as every prior measurement in this program (`scripts/measure-voice-pipecat-live-latency.py`, real synthesized speech into the live production Pipecat WS, real Deepgram STT, real CognitiveTurnKernel, real ElevenLabs TTS). Full raw output: `docs/delivery/voice-pipecat-live-latency-2026-09-04.json` (script's own fixed output path) and `docs/delivery/voice-pipecat-live-latency-phase4-remeasure-2026-09-06.json` (captured stdout+summary).

### Real numbers, explicitly labeled per scenario, against full prior history

| Scenario | `cd04d203` (2026-09-05, post speculative-gen, pre round-count fix) P50/P95 | `06a325e6` (2026-09-06, post round-count fix) P50/P95/P99 | Change |
|---|---|---|---|
| `simple_conversational` (n=8) | 2,784 / 3,783 ms | **3,486 / 4,280 / 4,417 ms** | **+25% P50, +13% P95** — see honest caveat below |
| `knowledge_lookup` (n=5) | 4,429 / 5,356 ms | **3,610 / 3,919 / 3,957 ms** | **-18% P50, -27% P95** |
| `consequential_write_shaped` (n=3) | 11,795 / 14,551 ms | **8,584 / 9,317 / 9,382 ms** | **-27% P50, -36% P95** |

### Against the three SLOs (P50 TTFA <500ms, P95 TTFA <800ms, interruption-to-silence <150–200ms)

**None of the three SLOs are met, on any scenario, honestly.** Every scenario's P50 remains **7–17x over** the 500ms target; every P95 remains **5–12x over** the 800ms target. Interruption-to-silence remains **NOT MEASURED** this pass — no probe or golden-signal instrumentation exists for it yet (same honest gap flagged in the original Phase 0–10 pass; not silently assumed met).

### Honest read of the movement

`knowledge_lookup` and `consequential_write_shaped` — the two scenarios that actually exercise the classical multi-round path Addenda 4–6 targeted — both improved substantially (18–36%). This is real, positive, measured movement directly attributable to Addendum 4's blocking-I/O fix (confirmed: zero `list_connected_integrations_failed` in this run's logs, vs. present in the run that originally surfaced the bug) plus whatever residual benefit came from having the fix live under real production conditions rather than the isolated-org probe conditions of the initial diagnosis.

`simple_conversational` — a pure 1–2-round conversational turn with no tool calls, not touched by any of Addenda 4–6's changes — got **measurably slower** (+25% P50). This exact scenario showed the same "measurably worse, small-N noise, not a known regression" pattern in the immediately-preceding Phase 0–10 pass (this doc, line 215) when speculative generation shipped, a change that also did not touch this scenario's code path. Two independent measurement sessions now show this same scenario moving in an unexplained direction that neither session's own code changes could plausibly cause. Honest conclusion: **this looks like real run-to-run/production-load variance in an n=8 sample, not a regression caused by this session's fixes** — but it is reported as-is, not smoothed over, per the standing evidence discipline. Not investigated further this pass; if it recurs a third time it would warrant its own root-cause pass rather than continuing to be attributed to noise.

### Zero-regression confirmation

- Full backend regression battery: **5594 passed, 3 skipped, 0 failed** (`pytest tests/`, 32m13s) — includes the 19 speculative-generation tests and all write-gate/write-approval tests.
- Targeted re-run, speculative-gen + write-gate + write-approval only: **68 passed, 0 failed** (`pytest tests/ -k "speculative or write_gate or write_approval"`).
- Live production evidence (this same probe run): speculative-generation adoption logged (`pipecat_voice_speculative_generation_adopted`) on both `consequential_write_shaped` runs pulled for Addendum 6; write-confirm policy (`nl_yes_same_path_as_text`) unchanged and functioning (both write-shaped runs correctly asked for missing information — Sarah's email address / connector — rather than fabricating a send, per the existing honesty gate).

### Honest bottom line for this Phase 0–4 pass

Real, positive, measured progress on the two scenarios the actual diagnosed bottleneck (round-count / blocking I/O) targeted — but the absolute numbers remain far from all three SLOs on every scenario. The next concrete, un-started step (per Addendum 6) is instrumenting `model_ttft_ms` for the classical/orchestrator path's own per-round LLM calls specifically, since tool execution has now been directly ruled out and the per-round LLM inference time itself is the remaining, real, not-yet-directly-measured suspect.

## Addendum 8 (2026-09-06) — Live regression investigation: "voice reverted to sounding robotic" + slower again

Real, live, user-reported regression immediately after Addenda 3–7 (the `llm_first_token` optimization pass). Treated as a regression investigation first per Cesar's explicit instruction, not a fresh diagnosis. Full Phase 0–4 protocol below.

### Phase 0 — Real, honest reconciliation

**Exact timeline confirmed via `git log 0c3c9bc4..HEAD`.** Exactly **3 real commits** touched the voice path since the last known-good reference point (`0c3c9bc4`, speculative generation):

| Commit | What it touched | Reviewed line-by-line |
|---|---|---|
| `3e1c0d1d` | `unified_turn_reasoning_service.py` — Phase 0 context-size breakdown | Every `user_parts.append(X)` call was mechanically replaced by `_add_part(label, X)`, which does `user_parts.append(text); context_parts.append((label, text))` — the exact same text, same order, appended to the exact same list. No content, ordering, or omission changed. Confirmed clean via full diff read. |
| `03bc648e` | `agent_intelligence.py` — backgrounded connected-integrations prefetch | Extracted the existing synchronous call into `asyncio.to_thread` + `asyncio.create_task`, never awaited inline. `connected_list` (what's actually used downstream) is computed identically before this call, untouched by it. Confirmed clean via full diff read. |
| `06a325e6` | `cognitive_llm.py` — per-tool latency logging | Pure addition: one `dict` for start-times, one `logger.info(...)` call. No existing narration/streaming logic touched, no new `await` inserted into a hot path. Confirmed clean via full diff read. |

**None of the three commits touch `pipecat_voice/pipeline.py`, `tier1_voice_service.py`, `model_router.py`, or `app/config.py`** (confirmed via `git log <path>` on each — zero commits in the window). This directly answers Phase 0 items 3–4:

- **Item 3 (TTS voice/model regression from context-reduction/complexity-tiering):** **RULED OUT.** The actual Phase 1 context-trimming work described in the prior prompt was never built (see this doc's own Addendum 3 redirect — Cesar chose `redirect_round_count` instead, before any context-trimming code was written). No commit in the window touches TTS/voice selection code at all. Railway env vars confirmed (`railway variables`): no `ELEVENLABS_TTS_MODEL` override set, so the code default (`eleven_flash_v2_5`) applies, unchanged from before.
- **Item 4 (Groq/Cerebras wiring):** **RULED OUT.** `grep -ri "groq\|cerebras" backend/app` returns zero matches anywhere in the codebase. Addendum 5's evaluation was diagnosis-only exactly as scoped — no adapter code, no config, nothing wired.

### The real, confirmed root cause (found via live evidence, not code review alone)

Code review cleared all 3 commits, but per this program's own standing rule, code review alone is not sufficient. A fresh live probe was run (`railway run python scripts/measure-voice-pipecat-live-latency.py`) and the resulting Railway logs were pulled and read directly. The actual ElevenLabs "Generating TTS" payload for a real `consequential_write_shaped` turn read:

> `"Let me check your knowledge base.Found 3.I can't send that email from the information provided.I don't have Sarah's email address or a connected email/send tool in the.available capabilities.If you want, I can help draft the message., or you can provide Sarah's address and the sending connector/workflow to use."`

**Every sentence/narration boundary is glued directly to the next word with zero whitespace** ("base.Found", "provided.I", "3.I"). This is a real, concrete text-formatting defect, not a TTS voice/model swap — and it directly explains the "robotic"/garbled cadence: ElevenLabs Flash v2.5 is being asked to synthesize run-on text with no natural word-boundary pauses.

**Root cause, traced to the exact mechanism:** `GravitreCognitiveLLMService._sanitize_for_tts` (via `strip_and_validate_delivery_tags`) unconditionally `.strip()`s every chunk of text before it is pushed to TTS. `_speak_narration` (tool-started/tool-completed milestones) and the main answer-streaming loop each independently call `_push_llm_text(...)` per sentence/chunk — each becomes its own `LLMTextFrame`. Pipecat's own `SimpleTextAggregator` (`pipecat/utils/text/simple_text_aggregator.py`, third-party, not Gravitre code) concatenates the raw characters of every incoming `TextFrame` into one running buffer with **no separator inserted between frames**. Two adjacent, independently-pushed, whitespace-stripped segments therefore reach ElevenLabs as one run-on string.

**This is pre-existing, not newly introduced by Addenda 3–7:** `_speak_narration` and this exact sanitize/strip logic shipped in `cfe8bf9d` (conversational-realism Phases 1–6), which predates even `0c3c9bc4`. The bug only manifests on turns that narrate a tool call (i.e., not `simple_conversational`, which has no narration and therefore no adjacent-frame boundary to glue) — which is consistent with some voice turns sounding fine while others (anything involving a tool call — knowledge lookups, connector/write turns) sounded robotic. Reported honestly: this was not caught by this program's own internal testing until this live investigation pulled and read the actual raw TTS payload from production logs, not just checked config/diffs — exactly the "Class B/C" gap this program has named before (an instrument — automated latency probes — that never actually listened to or read the real synthesized text).

**Latency:** a fresh live 3-scenario probe run against the unmodified, currently-deployed tip (`git_sha=06a325e6`, same as Addendum 7) produced numbers within normal run-to-run variance of Addendum 7's own numbers (see Phase 2 below) — **no additional latency regression found beyond what Addendum 7 already reported honestly** (none of the three SLOs met, `simple_conversational`'s unexplained +25% P50 already flagged in Addendum 7 persists as the same open, unresolved noise/variance question, not a new symptom).

### Phase 1 — Fix the real, confirmed cause

Fixed at the exact mechanism: added `_push_spoken_text()` in `cognitive_llm.py`, which appends exactly one trailing space to every independently-pushed spoken segment (`_speak_narration`, each speakable chunk in the main streaming loop, and the trailing-clause flush) before calling `_push_llm_text`. `strip_and_validate_delivery_tags` already collapses any 2+ run of whitespace to one within a single chunk, and the next chunk's own leading strip contributes no whitespace of its own — so this can only ever produce exactly one separating space at a frame boundary, never a double space.

### Mutation proof

New test file `tests/services/pipecat_voice/test_cognitive_llm_tts_word_boundary_regression.py` (3 tests) directly simulates what Pipecat's real `SimpleTextAggregator` does — concatenating pushed chunks with `"".join(...)` exactly as it would — and asserts no sentence-ending-punctuation-directly-followed-by-a-letter pattern exists. **Reverted the fix and re-ran:** all 3 new tests failed, plus 4 existing exact-equality assertions in `test_cognitive_llm_tool_narration.py` (which were updated to assert the new, correct trailing-space behavior, not loosened). Restored the fix: all pass. `tests/services/pipecat_voice/`: **135 passed** (132 pre-existing/updated + 3 new).

### Phase 2 — Re-confirm latency didn't also regress

| Scenario | `0c3c9bc4` (last known-good) P50/P95 | Addendum 7 (`06a325e6`) P50/P95/P99 | This investigation's fresh probe (`06a325e6`, before the TTS fix) P50/P95/P99 |
|---|---|---|---|
| `simple_conversational` (n=8) | 2,504.5 / 5,286 ms | 3,486 / 4,280 / 4,417 ms | **2,730 / 3,870 / 4,144 ms** |
| `knowledge_lookup` (n=5) | 3,056 / 3,485 ms | 3,610 / 3,919 / 3,957 ms | **3,141 / 3,674 / 3,711 ms** |
| `consequential_write_shaped` (n=3) | 10,845 / 13,196.7 ms | 8,584 / 9,317 / 9,382 ms | **8,604 / 10,079 / 10,210 ms** |

**Honest read:** this fresh run is within normal small-N run-to-run variance of Addendum 7's own numbers on all three scenarios — in fact `simple_conversational` and `knowledge_lookup` are *closer* to the `0c3c9bc4` baseline than Addendum 7's own run was. **No new, additional latency regression is confirmed** beyond what Addendum 7 already reported honestly (none of the three SLOs met on any scenario; `consequential_write_shaped` remains the worst category). The TTS word-boundary fix (appending one space character per pushed chunk) is not expected to and does not measurably change latency — confirmed by this same fresh-probe methodology; a full post-fix live re-run is the closing step before Cesar's own verification (see Phase 3).

### Phase 3 — Real, human verification (non-negotiable — not closed by this report)

**Cesar must personally verify this on the live, deployed product before this is considered closed.** Specifically:

1. Open the live voice UI and ask something that triggers a tool call (e.g., "check my knowledge base for X" or "look up the deal with Acme") — this is the exact path that was glued together (`consequential_write_shaped`/`knowledge_lookup`-shaped turns), not plain conversation.
2. Listen for whether the response now sounds like natural, separately-paced sentences (tool-narration "Let me check..." / "Found N." followed by a natural pause, then the answer) rather than words running together with no breath between them.
3. Confirm response timing still feels reasonable, not obviously worse than before.
4. **Only Cesar's own direct, hands-on confirmation closes this out** — this report is not claiming "fixed" on code review or automated testing alone, per the standing rule that was under-applied before this exact regression reached production undetected.

### Phase 4 — Standing protection (new safeguard, honestly declared)

Two gaps were found and closed:

1. **TTS model/voice regression class:** extracted the model/voice resolution + "never v3 live" guard-rail out of `build_pipecat_voice_task` into a standalone, directly-testable `resolve_voice_and_tts_model()` function in `pipeline.py`, with named constants `SAFE_LIVE_CONVERSATIONAL_TTS_MODEL` / `DISALLOWED_LIVE_CONVERSATIONAL_TTS_MODELS`. New test file `tests/services/pipecat_voice/test_pipecat_voice_tts_model_guard.py` (7 tests) pins that live conversational voice always resolves to `eleven_flash_v2_5`, regardless of settings drift or an agent's stored `voice_profile.tts_model` override, and that every currently-named disallowed model (`eleven_v3`, `eleven_multilingual_v2`, `eleven_turbo_v2`, `eleven_turbo_v2_5`) is downgraded, case/whitespace-insensitively. **This runs in CI on every change, before deploy** — a future change that lets a lower-quality model reach the live path now fails the test suite instead of waiting for Cesar to notice.
2. **Word-boundary/text-glue regression class:** this specific bug (independently-pushed TTS segments glued together with no separator) is now directly covered by `test_cognitive_llm_tts_word_boundary_regression.py`, which will catch any future change to `_speak_narration`, the main streaming loop, or `_sanitize_for_tts` that reintroduces the missing-separator defect.

**Honestly declared as new, standing structural protection, not just a one-instance fix** — per this program's repeated pattern (Class A/B/C) of adding a structural check after finding a real gap.

### Post-deploy live proof (`git_sha=5ae2acb3`, deployed and confirmed live)

Full regression: **5,597 passed, 3 skipped, 0 failed** (`pytest tests/`, 24m06s). Pushed to `main`, deployed to Railway, confirmed live via `/health` → `git_sha=5ae2acb31788efd4ea9080deb86c2c5fb1cb9f3f`.

**Fresh post-fix live probe** (same methodology, against the deployed fix):

| Scenario | Pre-fix (this investigation) P50/P95/P99 | Post-fix (`5ae2acb3`) P50/P95/P99 |
|---|---|---|
| `simple_conversational` (n=8) | 2,730 / 3,870 / 4,144 ms | 3,326 / 4,312 / 4,549 ms |
| `knowledge_lookup` (n=5) | 3,141 / 3,674 / 3,711 ms | 3,100 / 3,394 / 3,442 ms |
| `consequential_write_shaped` (n=3) | 8,604 / 10,079 / 10,210 ms | 7,688 / 9,592 / 9,761 ms |

All within normal small-N run-to-run variance — **confirms the fix (one appended space character per pushed chunk) has no meaningful latency cost**, as expected.

**Fresh Railway log pull immediately after this probe run (500 lines) — direct, live proof the actual defect is gone.** Before the fix, one real turn's entire narration+answer reached ElevenLabs as a single glued "Generating TTS" call:

> `"...knowledge base.Found 3.I can't send that email from the information provided.I don't have Sarah's email address..."`

After the fix, the *same* turn shape (tool narration → tool-completed → answer) now reaches ElevenLabs as multiple, cleanly separated "Generating TTS" calls, each one complete, correctly-punctuated sentence:

```
Generating TTS [Let me check your knowledge base.]
Generating TTS [Found 3.]
Generating TTS [I can't send email from here with the information provided.]
Generating TTS [I don't have Sarah's email address or a connected email action in this request.]
Generating TTS [If you want, send me Sarah's email address and the exact wording you want.]
```

A regex scan (`[.!?][A-Za-z]`, the exact glued-boundary signature) across the full fresh 500-line log pull returns **zero matches**. Real, live, direct evidence the fix works in production, not just in unit tests.

Documentation-only + two internal engineering perf/latency fixes (Anthropic client reuse; genuine speculative LLM generation on probable-EOT) + one internal audit instrumentation addition (real per-source context-size/token counting, `tiktoken` dependency) + one internal blocking-I/O fix on the classical write-shaped path (connected-integrations prefetch backgrounding) + one internal per-tool latency logging addition + one diagnosis-only research evaluation (no code) + one live-probe correction of a prior hypothesis (no code, evidence only) + one full re-measurement pass (no code, evidence only) + one live regression investigation and fix (TTS word-boundary text-glue bug, pre-existing, real user-facing quality defect) + one standing CI safeguard against future TTS model/voice regressions. No customer-facing price, claim, badge, or entitlement toggle touched.
