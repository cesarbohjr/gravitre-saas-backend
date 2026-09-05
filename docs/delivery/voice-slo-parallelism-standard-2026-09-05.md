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

## Scaffold/authorization note

Documentation-only + one internal engineering perf fix (Anthropic client reuse). No customer-facing price, claim, badge, or entitlement toggle touched.
