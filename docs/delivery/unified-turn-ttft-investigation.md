# Unified turn TTFT investigation (200ms gate)

Updated: 2026-07-23  
Status: **instrumented live re-measure complete; 200ms gate remains MISS**

Artifact: [`unified-turn-ttft-breakdown-live.json`](unified-turn-ttft-breakdown-live.json)  
Tip: `6457ba7c…` · `/health` live=true @ `2026-07-23T05:14:31Z`

## 1) Where the ~481ms goes (instrumented)

`first_token_proxy_ms` previously mixed assembly + model. New `latency_breakdown` splits them.

| Message | wall TTFT | `model_ttft_ms` | `pre_model_ms` | Evidence |
|---------|----------:|----------------:|---------------:|----------|
| Hey | 494 | **492** | 0 | `unified_turn.live.completed` @ `2026-07-23T05:14:35.04788Z` conv `0df67710…` |
| Thank you | 749 | **746** | 1 | @ `05:14:45.059866Z` conv `d0b64a27…` |
| What's on your plate? | 546 | **545** | 0 | @ `05:14:51.268529Z` conv `2ef23add…` |

**Verdict:** p50 wall ≈ **546ms**; nearly 100% is **OpenAI stream TTFT** (`model_ttft_ms`). Context assembly / keyword narrow / registry are **≤1ms**. Not network residual inside our process (`pre_first_token_overhead_ms` 2–3ms).

Also in audits: `system_prompt_chars≈8811`, `messages_chars≈9232`, `tools_payload_bytes=4965`.

## 2) Full 600+ catalog every call?

**No. Rejected.**

| Check | Result |
|-------|--------|
| Retrieval | `keyword_narrow_tools_for_turn` — **not** embedding (`embedding_tool_retrieval=false`) |
| Live tools | `totalTools=26` → `visibleTools=13` (Apollo-focused) |
| Payload | **4965** bytes sent vs **14367** bytes full connected set (still not 600+) |
| Phase 0 | Embedding retrieval listed as Future; keyword narrow chosen now |

Large-catalog-every-call is **not** the cause. Remaining model cost is a tool-aware call with ~13 compressed schemas + ~8.8k Module D system prompt.

## 3) Fair baseline (classical vs unified)

Same tip-class social queries on classical conversational path:

| Message | Classical path | Classical total |
|---------|----------------|----------------:|
| Hey | heuristic + **phrase bank**, no LLM | **~0–20ms** |
| Thank you | same | **~0ms** |
| What's on your plate? | task_shaped (not social bank) | classify may use LLM (~0.9s on operator host) — different class |

**Explicit tradeoff:** Unified LIVE always runs a streamed tool-aware model call, even for greetings. Classical social was a local bank (no tools, usually no LLM). The ~500ms+ is largely “unified does real model reasoning with tools”; classical social did less. That is a product tradeoff, not silent infra debt.

## 4) Option A pre-approval answers (2026-07-23) — **do not ship A**

Criteria from product review: Option A may proceed only if (1) social replies use Module D’s **full voice generation** (registers / drift / no-repeat), not phrase-bank fallback, and (2) any “is social?” step is proven live not to misfire on mixed messages (exact conversational-path battery cases). If either fails → **do not do A**; accept social ~500–750ms; pursue **C/D** for task-shaped latency.

### 4.1 Voice path: full Module D vs phrase bank?

| Path | Mechanism | Module D full spec? |
|------|-----------|---------------------|
| **Unified LIVE (current)** | `build_module_d_unified_system_prompt` → model generates reply; registers, knowledge boundaries, imperfect-input, drift (“check history, not a rotation counter”) | **Yes** — system instruction, not a bank |
| **Classical conversational / proposed Option A short-circuit** | `generate_conversational_reply` → `phrase_for_conversational_category` → `pick_expression` (`voice_expression_last` rotation) | **No** — bank-first; doc’d as classical until cutover |

Evidence:
- `module_d_unified_voice_spec.py` header: *“not a post-hoc phrase bank. Classical … continue to use gravitree_voice / voice_expression_range until cutover.”*
- `conversational_reply_service.py`: priority categories are **bank-first**; model path reserved for rare `other`.
- Phrase-variety pass fixed identical “Hey” / “Doing well” **inside the bank** ([`conversational-phrase-variety.md`](conversational-phrase-variety.md)) — that is rotation, not the unified register/drift system.

**Answer:** Option A as previously sketched (reuse classical social path) **falls back to the phrase bank**. That reopens the wrong architecture for the register where variety matters most (even with a larger bank). A variant that “uses Module D” via a **no-tools model call** still pays model TTFT (likely still hundreds of ms) and is not the cheap short-circuit that made A attractive.

→ **Fails criterion 1** for the only A that buys large TTFT wins.

### 4.2 Who decides “social — skip reasoning”? Mixed-message risk?

Today under LIVE: **no** social classifier sits in front of the reasoning call. Order in `agent_intelligence.py`: `apply_unified_turn_live` **before** `classify_turn_shape` / conversational gate. One call owns social + task + mixed.

Option A would reintroduce a front-door decision. The only existing mechanism is the old gate:

- `heuristic_turn_shape` / `classify_turn_shape` → `should_offer_conversational_path` (**true only if `shape == conversational`**)
- `mixed` is a separate shape: social ack + task continues — **not** pure conversational short-circuit by design

That **is** classify-then-route, scoped to one category — the pattern unified-turn exists to remove.

Mixed battery cases already built (`verify-conversational-path-live.py`): e.g. `mixed_hey_apollo` (“hey — also create an Apollo contact list…”), `mixed_thanks_search`, `mixed_banter_gmail`, `mixed_slack`, `mixed_hubspot_list`. Classical gate *aims* to keep these out of pure conversational short-circuit; live history shows mixed cases are sensitive (Phase 2 artifacts have both PASS and FAIL streaks depending on tip/path).

**Answer:** There is **no** proven LIVE short-circuit under the unified architecture that has been re-tested against that mixed battery as a *pre-unified* gate. Shipping A without that live proof would reintroduce misfire risk (social-only reply that drops the embedded task).

→ **Fails criterion 2** until/unless a new design is proven — and any new front-door classifier still conflicts with the single-call architecture goal.

### 4.3 Is 500–750ms for “hey” worth the compromise?

| Source | Finding |
|--------|---------|
| Brief / Phase 2–3 docs | TTFT &lt;200ms cited as streaming target; general perceived-intelligence threshold language |
| Gravitree user complaints / subjective study | **None found** in delivery docs tying greeting latency to reported UX pain |
| Instrumented cost | Social turns: `model_ttft_ms` ~492–746ms; assembly ~0ms — honest cost of one tool-aware Module D call |
| What unified correctly buys vs bank | Memory/pending context, disambiguation, imperfect-input rule, honest knowledge boundary, write proposal staging — same call |

**Answer:** Treat **200ms as a brief-cited research threshold, not a Gravitree-measured greeting pain point.** No evidence that ~500–750ms for “hey” is costing real users enough to justify reintroducing classify-then-route or phrase-bank social. For **task-shaped** turns (user waiting on a real action), latency has a clearer product cost → prefer **C/D** there.

### 4.4 Decision

| Option | Decision |
|--------|----------|
| **A. Social short-circuit** | **Do not pursue** — cannot satisfy both hard criteria without either phrase-bank regression or a still-expensive Module D model call plus a front-door classifier |
| **B. tools=[] on social** | Optional micro-optimization only if measured; does not restore bank speed; still needs a social decision → same architecture smell |
| **C. Embedding tool retrieval** | **Pursue for task-shaped** relevance/latency at catalog scale |
| **D. Model tier** | **Pursue for task-shaped** (and optionally all unified turns) as direct `model_ttft_ms` lever |

**Accepted cost:** ~500–750ms social TTFT under one coherent reasoning + Module D full voice architecture.

**Revised gate:** Do not chase social &lt;200ms via Option A. Keep reporting honest `model_ttft_ms`. Revisit social target only if live subjective/product evidence appears. Optimize task-shaped turns via C/D; re-measure with `verify-unified-turn-ttft-breakdown-live.py` on action-bearing prompts.

## Gate status

| Gate | Status |
|------|--------|
| TTFT &lt;200ms (social) | **MISS accepted for now** — not worth Option A compromise |
| Full-catalog hypothesis | **REJECTED** |
| Classical fair compare | **Documented** — bank ≪ unified; bank is not Module D full voice |
| Option A | **REJECTED** (voice + architecture criteria) |
| Next latency work | **C/D on task-shaped** |
| Instrumentation | **PASS** — tip `6457ba7c` emits `latency_breakdown` |

Rollback (cutover, unrelated): `UNIFIED_TURN_LIVE_ENABLED=false` + redeploy.
