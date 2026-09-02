# CRAG program — Phase 0: pre-flight, architecture audit, and reachability

**Date:** 2026-09-02 · **Tip:** `ba554f53` (local == `origin/main`)
**Artifacts:** `crag-phase0-reachability.json`, `crag-phase0-saturation.json`,
`crag-phase0-corpus.json`, `crag-phase0-platform.json`, `crag-phase0-realturns.json`

**Headline: STOP BEFORE BUILDING.** Three of the five requested phases already
exist in production code, and the path all five would extend has carried **zero
real evidence-dependent traffic in 30 days**. Lesson 4 says measure reachability
before investing a fix-and-prove cycle. Measured, it says don't.

---

## Pre-flight regression battery — GREEN

| Suite | Result |
|---|---|
| Named battery (`withhold_no_tool`, NL-variance, F-label routing/fallthrough enum, dormant-call guards, narrowed-tools scan, audit-actor guard, tool-aware grounding validator, finalize wiring, grounding reach) | **124 passed, 0 failed** |
| Full backend suite | **5053 passed, 16 failed, 3 skipped** (606s) |

The 16 failures are the same pre-existing set confirmed during the
`unnarrowed_tool_attach_blocked` work (e2e chat scenario dry-runs, an
unguarded-dict lint test, MSP enrichment aliases, agent-memory embedding,
connector output contracts, workspace memory, v10 detectors, temporal
workflows). None touch retrieval, the sufficiency loop, or the critic. Not
counted as green; counted as **unchanged**.

F1–F10 note: there is no pytest-level F1–F10 battery. Those labels refer to live
probe checks in `gravitre-routing-decision-map.md`; the pytest coverage that
carries F-labels is `test_routing_nl_variance_battery.py` and
`test_unified_turn_fallthrough_enum.py`, both green above.

---

## Phase 0.1 — Are retrieval decisions made once, upfront?

**No. An iterative, sufficiency-gated retrieval loop already exists.**

`build_unified_turn_knowledge_context`
(`backend/app/services/unified_turn_knowledge_context.py:300`) runs a first pass
(knowledge packs → org RAG → conditional internet), then assesses sufficiency
and escalates:

- `ESCALATION_ORDER = (internet, business_graph)` (line 48)
- `MAX_ADDITIONAL_ROUNDS_CEILING = 3` (line 50), `evidence_sufficiency_max_rounds`
  default **2**, clamped at the call site
- `stopped_because` ∈ `{assessor_unavailable, no_untried_source, max_rounds_reached}`

So the premise "retrieval happens once, upfront" is **already false**. The
requested Phase 2 is substantially built.

## Phase 0.2 — Does an "insufficient evidence" finding do anything?

**Split answer, and the distinction matters.**

| Mechanism | Insufficient evidence causes… |
|---|---|
| **Pre-answer sufficiency loop** (`unified_turn_knowledge_context`) | **Real additional retrieval** from an untried source, then an honest `EVIDENCE SUFFICIENCY WARNING` in the prompt if still short |
| **Post-answer critic** (`verification_critic_service`) + reflection (`reflection_loop_service`) | **Wording only.** `reflection_loop_service:51` emits a `retrieve_more` action and **nothing consumes it**. `ModelRouter.should_retrieve_more_context` (`model_router.py:1014`) has **no call sites**. |

Also relevant to lesson 5: the sufficiency assessor **already fails closed and
announces it**. On assessor error it returns `sufficient=False`,
`assessor="assessor_error"`, `gaps=["assessor_unavailable"]`, the loop stops with
`stopped_because="assessor_unavailable"`, and the prompt carries
`EVIDENCE SUFFICIENCY UNVERIFIED` — deliberately distinct from
`EVIDENCE SUFFICIENCY WARNING`. That requirement is already met.

## Phase 0.3 — Real reachability (the blocking finding)

The loop lives on exactly one path: `apply_unified_turn_live` →
`run_unified_turn_shadow` → `build_unified_turn_knowledge_context`
(`unified_turn_reasoning_service.py:733`). The classical ReAct / fallthrough
pipeline never calls it.

**30-day production census:**

| | events | loop ran |
|---|---|---|
| `Gravitre Isolated Conversation Smoke` (probe org) | 1034 completed + 511 fallthrough | **256** |
| `Cesar Bohorquez Jr.'s Workspace` (real) | 27 completed + 7 fallthrough | **0** |
| `testuser…20260807's Workspace` (real) | 2 completed | **0** |

**Every one of the 256 loop executions was probe traffic that this program's own
scripts generated.** The loop has never run on a real user turn.

Fallthrough reasons (518 events): `outcome_error` 146,
`pending_family_classical_resume` 136, `defer_classical_tool_sse` 122,
`read_tool_classical` 114.

### The corpus it would correct retrieval over

| Metric | Value |
|---|---|
| Organizations | **229** |
| `rag_documents`, all orgs | **1** |
| `rag_chunks`, all orgs | **1** |
| Orgs with any corpus | **1** — `Acme Corp`, the seed org |
| Unified-turn traffic from `Acme Corp` | **0** |

The single chunk platform-wide is "Gravitre Operator Sample Playbook"
(env `production`, created 2026-06-22) in the one org that sends no turns.

### What real traffic actually asks for

36 real turns in 30 days. 31 carried **no knowledge block at all**.

| `outcome_kind` | count |
|---|---|
| `conversational_reply` | 21 |
| `clarifying_question` | 8 |
| `connector_tool_proposal` | 2 |
| `error` | 2 |
| `skipped` | 2 |
| `confirmation_request` | 1 |

**Zero knowledge-grounded research answers.** Real usage is conversational,
clarifying, and tool-shaped. CRAG corrects retrieval for evidence-dependent
research questions, which real users are not asking.

### Instrument credibility (lesson 2)

The reachability numbers were cross-checked rather than trusted:

- The probe searches for `evidenceSufficiency` **anywhere** in the payload tree
  instead of a fixed path, so a renamed nesting reads as a miss, not a zero.
- Structural presence is reported separately: 678 events carried a knowledge
  block, 157 of those a sufficiency block. A zero is only called dormancy when
  the surrounding structure is present.
- Independent cross-check: `additional_rounds_used > 0` must coincide with an
  escalation source in `sources_tried` (computed by different code).
  **156 consistent / 0 inconsistent.** The instrument is sound.
- `rag_chunks`/`rag_documents` confirmed as the tables retrieval actually reads
  (`rag_service.py:399,411`) before the count of 1 was believed.

### A real, saturated verdict — and why it is not a defect

`final_sufficient=False` on **255 of 256** loop runs, with
`org_rag_chunk_count = 0` on **256 of 256**. That looked like a live retrieval
failure. It is not: all 256 came from the probe org, which has zero documents.
The gate is judging correctly on genuinely empty evidence. Reported because the
aggregate, unsegmented, would have been read as a customer-facing defect —
the same mistake the `outcome_error` trace nearly made (140 of 142 probe).

## Phase 0.4 — Real insertion point

If the program proceeds: `build_unified_turn_knowledge_context`
(`unified_turn_knowledge_context.py:424-547`), extending the existing loop and
`evidence_sufficiency_service.assess_evidence_sufficiency`. No second system is
needed or wanted.

---

## Phase 3 audit — retrieval quality baseline (done early, since it gates 1/2)

Against Anthropic's four published layers:

| Layer | Verdict | Evidence |
|---|---|---|
| **1. Contextual chunk enrichment** | **ABSENT** | `get_embedding(content, settings)` on raw chunk text (`backend/app/rag/ingest.py:461`). No LLM situating blurb, no title/section prepended. Knowledge Fabric same (`knowledge_fabric/ingest.py:134-138`). |
| **2. Contextual BM25 / keyword index** | **PARTIAL** | Org RAG: real BM25Okapi but **in-memory over a 500-row fetch** (`rag/hybrid_rerank.py:65-88`, `rag/retrieval.py:78`), **no `tsvector`/GIN on `rag_chunks`**. Knowledge Fabric: real Postgres FTS (`content_tsv` + GIN, migration `20260811180000:100-106`). `ilike` is only a dimension-mismatch fallback, not the normal arm. |
| **3. Hybrid search** | **PRESENT** | pgvector `rag_search` RPC + BM25 arm in parallel, fused by **RRF, k=60** (`rag_service.py:187-210`, `hybrid_rerank.py:91-119`). `rag_hybrid_candidate_k=20` per arm, merge `2k`, final `top_k=8`. |
| **4. Reranking** | **PRESENT** | Cross-encoder `ms-marco-MiniLM-L-6-v2`, threshold `0.3`, lexical-overlap fallback (`hybrid_rerank.py:122-218`). |

The production log `rag_rerank … method=none candidates=0` decoded: `method=none`
means `rerank_rows` got **zero rows** (`hybrid_rerank.py:129`), i.e. both arms
returned nothing — consistent with an empty corpus, **not** a broken reranker.

**Anthropic's own framing is that Layer 1 alone is worth ~35% fewer retrieval
failures, and all four together up to ~67%.** Gravitre has 3 and 4, half of 2,
and none of 1. So Layer 1 is the genuine, highest-value retrieval gap — but its
benefit is **unmeasurable at one chunk**, and a 35% reduction in failures on a
corpus of one document is not a real result.

---

## Recommendation

The architectural requirement (extend, don't duplicate) is satisfied by
*not building*: Phase 2's bounded loop exists, Phase 4's contradiction detection
exists (`evidence_contradiction_service.py`, default on, resolving by
supersession → freshness → authority → org precedence), and Phase 1's only real
deltas are (a) binary → three-way and (b) evidence *refinement*, which is
genuinely absent — rows are never filtered, only judged.

Proceeding through Phases 1–5 as written would produce mechanisms provable only
against probe traffic, over a one-chunk corpus, on a path real users reach for
conversational and tool turns rather than research. That is the precise failure
lesson 4 exists to prevent, so it is put to Cesar rather than decided here.

**One item is worth doing regardless of that decision:** the sufficiency loop has
**no named audit action**. `evidence.sufficiency.assessed` returns 0 events; the
verdict is buried inside `latency_breakdown.unifiedTurnKnowledge` on
`unified_turn.*` events. Every other governed mechanism in this program earned a
first-class action string, and this one is a live gate whose verdict currently
cannot be queried directly.
