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

---

# Decision and outcome (2026-09-02)

**Cesar's decision: stop the CRAG build.** Close the instrument gap now; revisit
CRAG when a real corpus exists. Phases 1, 2, 4 and 5 are not built.

## Delivered: `evidence.sufficiency.assessed` — LIVE PASS

**PASS — `evidence.sufficiency.assessed` @ 2026-09-02T23:28:32.984Z**, org
`f07e57c0…0001`, conversation `74059ef1…`, emitted by **deployed** tip
`fcd244de` (live `git_sha` confirmed equal to local HEAD before probing).
Artifact: `sufficiency-audit-live.json`. All 13 checks pass.

Emitted from inside `build_unified_turn_knowledge_context`, not from its caller:
the loop is the mechanism, and an audit attached to the caller would be bypassed
the moment a second caller appears.

### The strongest evidence was not the probe

The probe's own turn wrote a row at 23:29:41 (`bar=regulatory`, 2 rounds,
3 × `llm` assessors). But a **recurring production smoke job** drives a turn in
this org roughly every 30 minutes, and it produced its own row at 23:28:32
(`bar=business`, 1 round) one second before its `unified_turn.live.completed`
event — **deployed code, unprompted, on its own schedule.**

That gives a clean before/after from the same recurring job:

| Turn | Tip | Nested `evidenceSufficiency` | `evidence.sufficiency.assessed` |
|---|---|---|---|
| 22:01:51Z `smoke-ok` | `36f947d2` | present, `bar=business`, 1 round | **absent** |
| 22:31:05Z `smoke-ok` | `36f947d2` | present, `bar=business`, 1 round | **absent** |
| 23:28:33Z `smoke-ok` | **`fcd244de`** | present, `bar=business`, 1 round | **PRESENT** |

Same job, same query, same verdict. The only variable is the deploy, so the
instrument is what changed and nothing else.

### Two rows were checked before being believed

Two rows for one probe run looked like double emission, which would inflate
every future query off this action. Matching each row against the surrounding
`unified_turn.*` events showed two distinct turns, one row each — the smoke
turn and the probe turn. **No double-count.** Worth recording that the
suspicious number was chased rather than accepted, because "13/13 checks
passed" would have shipped over it.

### Cross-checked against an independent signal (lesson 2)

The dedicated event and the pre-existing nested block are written by different
code from the same verdict, so they can disagree. They were compared on
`bar`, `final_sufficient`, `additional_rounds_used` and `stopped_because` —
**all four agree**. `assessorRan` was additionally checked against the raw
`assessors` list it derives from, rather than trusted on its own.

### Lessons carried, concretely

- **Real actor or a loud skip.** A non-UUID actor or conversation is recorded in
  the metadata *and* logged by name; `write_audit_event` is never called with
  values it would silently drop. The live row carries the real actor
  (`a9f1240f…`) and the real conversation.
- **Fail-closed announces itself.** `assessorUnavailable` separates a turn whose
  evidence was never judged from one that genuinely fell short; without it
  `finalSufficient=False` means both.
- **`assessorRan` compared against constants, not a literal.** The four inline
  assessor strings in `evidence_sufficiency_service` are now named constants
  (`ASSESSOR_LLM`, `MODEL_ASSESSORS`, …). This pre-empts the grounding
  validator's bug, where a literal `"model"` never matched
  `"loaded_model_artifact"` and read False on every event for weeks.
- **The call site is pinned.** An AST test asserts the production caller passes
  `actor_id` and `conversation_id` and that neither is hardcoded `None`. A
  correct emitter that is never handed an actor records nothing — the "one layer
  too low" failure this program has now hit five times.
- **The fast path pays nothing.** No row is written when the loop is skipped;
  a per-turn insert on casual turns would add a write to the conversational path.

Mutation-proven **9/9**, including the literal-comparison bug, the removed actor
guard, and the call site reverting to `actor_id=None`. 15 new tests; targeted
regression set 83 passed.

## Still open, honestly labelled

- **Phase 1's real delta is NOT built:** the verdict remains binary
  (`sufficient: bool`), and evidence is judged but never **refined** — rows are
  never filtered. Deferred with the CRAG program, not silently dropped.
- **Phase 3 Layer 1 (contextual chunk enrichment) is NOT built.** Confirmed
  absent, highest-value retrieval gap, unmeasurable at one chunk.
- **Org RAG has no persisted keyword index.** BM25 is real but in-memory over a
  500-row fetch; Knowledge Fabric has a proper `tsvector`+GIN and org RAG does
  not. Accepted for now, recorded as a known asymmetry.
- **CI is red on `main`** for pre-existing reasons: e2e chat scenario dry-runs
  asserting on mocked execution, plus a `sk-test-` placeholder key producing
  embedding 401s in CI. Verified unrelated — the docs-only Phase 0 commit, which
  touched no application code, failed identically.

  > **CORRECTED 2026-09-03 at `5ece38df`. Both halves of that sentence were
  > wrong.** It was **eight** distinct causes, not two, and the embedding 401s
  > were **never** one of them — they are caught and logged as warnings, so they
  > could not fail a test. The red streak also began **2026-08-06**, 39 of the
  > last 40 runs, so it long predates the docs-only commit named above. Full
  > diagnosis and fixes in the `5ece38df` commit message. Recorded here because
  > this paragraph is where the incorrect "two known causes" framing entered the
  > standing record and was then repeated back as established fact.
  >
  > **CORRECTED AGAIN — it was nine.** Fixing the eight turned `Backend
  > (pytest)` green, which un-skipped `Integration Smoke Test` (`needs: [web,
  > backend]`). It had been **skipped, not passing**, on all 40 red runs, and on
  > its first real execution in a month it **hung for 40+ minutes** and had to be
  > cancelled. Cause: `warm_local_tool_encoder` was added to the blocking
  > lifespan on **2026-08-06** in `ef7ef50f` — the same day the streak began —
  > pushing time-to-`/health` to 51.6s warm / ~62s cold, past the job's 30s
  > readiness window; the failure branch then called `wait $SERVER_PID` on a
  > server that was still starting and blocked forever, with no
  > `timeout-minutes` on any job in any workflow to bound it. This is **Class C
  > exactly**: a skipped job reads as an absent failure. Cause 9 was structurally
  > unfindable until 1–8 were fixed, which is the honest reason the earlier
  > "complete explanation" was incomplete rather than careless.

---

# FORMAL DEFERRAL — Prompt 1 (CRAG) and Prompt 2 (Context Engine)

**Decision date:** 2026-09-03 · **Decided by:** Cesar · **Status: DEFERRED —
correctly-timed-later work. NOT an open gap, NOT a known defect, NOT debt.**

This section exists so neither programme is later rediscovered and misread as
something that was overlooked. Both were **audited, scoped, and deliberately
not built**, on evidence.

## What is being deferred

| | Programme | Scope as written |
|---|---|---|
| **Prompt 1** | Corrective RAG (CRAG) | Three-way evidence evaluation (Correct / Incorrect / Ambiguous), bounded corrective retrieval, contextual-retrieval quality layers, cross-source contradiction detection, RAGAS-style verification |
| **Prompt 2** | Context Engine | A thin cross-source ranking layer above customer RAG, Knowledge Fabric, Tool Knowledge, memory, connectors, knowledge graph and web research, selecting the best candidate subset within an enforced budget |

## Why — the measured basis, not a judgement call

Retrieval quality is **confirmed not to be the current limiting factor**:

| Measurement | Value | Source |
|---|---|---|
| Real (non-probe) unified turns, 30d | **36** | `crag-phase0-realturns.json` |
| Real turns carrying no knowledge block at all | **31 of 36** | same |
| Knowledge-grounded research answers | **0** | same |
| `rag_chunks`, all 229 orgs | **1** | `crag-phase0-platform.json` |
| Sufficiency-loop runs on real user traffic | **0 of 256** (all probe) | `crag-phase0-reachability.json` |

Both programmes improve *how well candidates are chosen*. At one chunk
platform-wide and zero research-shaped turns, there is nothing to choose
between. A ranking layer over a single candidate ranks it first.

This is **lesson 4 applied as designed**: measure real reachability with real
production data before investing a fix-and-prove cycle. It is the same
discipline that prevented building Phases 1–5 in the first place.

## What this deferral does NOT claim

Stated explicitly, because a deferral is easy to over-read:

- **Not** that the designs were wrong. Phase 0 found the CRAG architecture
  substantially sound and already half-built in the right place.
- **Not** that retrieval quality is good. Three real gaps stay recorded and
  unfixed below.
- **Not** that they were skipped for cost or difficulty. Neither was estimated,
  because volume made the estimate moot.

## The real gaps that remain recorded and unfixed

Deferring the programmes does not retire these. They are carried in the
standing risk register:

1. **Layer 1 contextual chunk enrichment is ABSENT** — the highest-value single
   retrieval improvement available (Anthropic measure ~35% fewer retrieval
   failures for this layer alone). Unmeasurable at one chunk.
2. **Org RAG has no persisted keyword index** — BM25 is real but in-memory over
   a 500-row fetch; Knowledge Fabric has `tsvector`+GIN and org RAG does not.
3. **Phase 1's genuine delta is unbuilt** — the sufficiency verdict is binary
   (`sufficient: bool`) and evidence is judged but never *refined*; rows are
   never filtered.

## Re-open triggers — the conditions that make this work correctly-timed

Deferred is not forgotten. Revisit when **any** of these becomes true, and
prefer gap 1 above before either programme:

- `rag_chunks` exceeds ~1,000 across ≥3 real orgs (currently **1** / **1 org**)
- Real research-shaped turns exceed ~10% of real traffic (currently **0%**)
- The sufficiency loop runs on real user traffic at all (currently **0 of 256**)
- A real customer reports a wrong-evidence or conflicting-evidence answer

These are now cheap to check: `evidence.sufficiency.assessed` (shipped
`fcd244de`) makes the third queryable directly, and
`scripts/probe-crag-phase0-platform.py` answers the first two.

**Read the production numbers first.** Both programmes were scoped twice before
anyone measured how much traffic they would serve; that measurement is what
changed the decision, and it takes minutes.
