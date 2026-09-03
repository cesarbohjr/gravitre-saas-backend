# Prompt 3 (memory hardening) — reachability assessment before scoping

**Date:** 2026-09-03 · **Artifact:** `memory-reach-census.json`
**Probe:** `scripts/probe-memory-reach.py` (read-only)
**Status: RECOMMENDATION ONLY — the proceed/hold decision is Cesar's.**

## Why this assessment exists

Prompts 1 (CRAG) and 2 (Context Engine) were deferred because the paths they
improve carry no real traffic. Prompt 3 was held out on a specific, reasonable
argument: **memory's value does not depend on retrieval volume the way theirs
does.** Memory helps a returning user on turn two, not a research corpus.

That argument is sound in principle. It is also exactly the kind of plausible
premise lesson 4 exists to test rather than accept, so memory got its own
census before anything was scoped.

**Prompt 3's text was never sent in this conversation.** This assesses the
memory subsystem's real state, not a specific proposed design. If the actual
prompt targets something outside what is measured here, re-read it against
these numbers first.

## Measured state (30-day window, 229 orgs, 146 agents)

| Measurement | Value |
|---|---|
| `agent_memories` rows, all orgs | **13** |
| `agent_memories` rows in **real** (non-probe) orgs | **1** |
| Created between | 2026-08-13 and 2026-08-27 |
| Provenance of all 13 | `learn_outcome` (5), `part1_seven_gates` (5), `one_brain_workspace_memory_probe` (3) — **every row is instrumentation, not use** |
| Categories | `outcome` 5, `preference` 5, `decision` 3 |
| `memory_promotion_candidates` | **3**, all `pending_approval`, all in the probe org |
| `agent_memory_promotion_audit` | **0 rows** — the promotion queue has never been adjudicated |
| Agents with memory retrieval enabled | **0 of 146** |
| Real turns, 30d | 35 |
| Real turns where memory was recalled | **NOT INSTRUMENTED** (see below) |

## Three findings, in order of how much they should influence the decision

### 1. Agent-scoped memory recall is switched off platform-wide

`_memory_retrieval_enabled` (`agent_memory_service.py:437`) returns **False**
unless an agent sets `config.use_memory` or `include_agent_memory`. **Zero of
146 agents set either.** So `build_task_retrieval_context` — the path used by
`assistant.py:557` and `unified_retrieval_service.py:116` — never runs in
production.

This is by design, not a defect: Memory Phase 1 shipped as **Option B** under
STA-312 sign-off — opaque tokens, **opt-in, default off**, no raw PII. The
default is doing what it was authorized to do.

### 2. Workspace recall does run — over an almost empty store

Stated separately because concluding "memory is off" from finding 1 alone would
be the single-path mistake this program has made five times.

`recall_workspace` is called from `cognitive_turn_kernel.py:605`, inside
`if client is not None`, **not** gated by `use_memory`. Workspace memory recall
therefore executes on essentially every kernel turn. Department-shared recall
and cross-conversation entity resolution sit in the same build step.

So the machinery runs. It has **1 row in a real org** to find.

### 3. Memory has no per-turn signal in the audit trail

The census first reported "0 of 35 real turns recalled memory". That number was
wrong to report, and the probe now refuses to: `no_memory_signal` came back on
**1581 of 1581** turns including probe traffic, which is not a plausible usage
pattern — it is a blind instrument.

Confirmed by inspecting the events directly. `unifiedTurnKnowledge` carries
`org_rag_chunk_count`, `fabric_hit_count`, `internet_hit_count` and
`business_graph_status`. **There is no memory field.** The only memory-named
audit action in production is `memory_entity_embeddings.updated`.

Memory is the one major context source whose per-turn contribution **cannot be
asked of production data at all**. `"0 turns recalled memory"` and `"no turn
records whether memory was recalled"` are indistinguishable downstream and mean
opposite things. The probe now reports `NOT INSTRUMENTED` rather than `0`.

This is the same gap that was just closed for the sufficiency loop, where the
verdict existed only as nested metadata until `evidence.sufficiency.assessed`
made it queryable.

## Recommendation: hold the hardening build, close the instrument gap first

**The premise does not survive measurement.** Memory's value genuinely does not
depend on *retrieval corpus* volume — but it does depend on adoption, and
adoption is currently more absolute than RAG's: 0 of 146 agents opted in, and
1 memory row in a real org. Hardening a subsystem that no agent has enabled
would be provable only against probe traffic, over 13 probe-authored rows.
That is the same shape as CRAG, reached by a different route.

**What is worth doing now, and is small:** give memory recall a per-turn signal
— a memory hit count in `unifiedTurnKnowledge` alongside the four counts already
there, and/or a named audit action. Justification, in order:

1. It is the prerequisite for evaluating hardening at all. Any Prompt 3 scoping
   would otherwise start by re-deriving what production cannot currently answer.
2. It does not depend on adoption. It reports honestly at zero, which is the
   whole point.
3. The identical move on the sufficiency loop has already paid for itself, and
   the pattern to copy — real actor or a loud skip, fail-closed announced,
   constants not literals, call site pinned by an AST test — is written down.
4. Two adjacent facts are currently invisible and would become queryable: that
   workspace recall runs on every turn while agent recall runs never, and that
   3 promotion candidates have sat `pending_approval` with an empty audit table.

## The instrument gap is now CLOSED — live PASS at `9222036d`

**Decision (Cesar, 2026-09-03): close the instrument gap now, then re-scope
hardening against real numbers.** Done, shipped, live-proven.

| | |
|---|---|
| Per-turn signal | `unifiedTurnKnowledge.memoryRecall` on every `unified_turn.*` event — `ran`, `total`, `bySource` over all five stores, `attempted`, `degraded`, `failedSources` |
| Named action | `memory.recalled`, emitted when recall contributed **or** degraded |
| Live PASS | **18/18 checks**, `local sha == prod sha == 9222036dccbd`, turn `4d2faa6d-7455-4b85-b249-53a5c022f4d6`, org `f07e57c0…0001`. Artifact: `memory-recall-live.json` |
| Cross-check (lesson 2) | The dedicated row and the nested block are written by **different modules** from the same recall. Both reported `total=28`, identical `bySource` (`workspace` 12, `hybrid` 8, `agent` 8, `department` 0, `ledger` 0). Agreement is the evidence; a row's existence alone is not |
| Real traffic (lesson 1) | Independent of the probe, a genuine production turn emitted `memory.recalled` with `entryPoint=execute_task_streaming`, `agent=None`, `total=20` at `2026-09-03T07:38:35Z`. Real path, real traffic, deployed tip |
| Mutation proof | **10/10 CAUGHT**, `scripts/mutate_memory_recall_signal.py` |

### Three states, previously one

The census's central complaint is fixed at the root:

- `ran=False` → RECALL did not execute. **UNKNOWN.**
- `ran=True, total=0` → every attempted store genuinely returned nothing. **Real zero.**
- `degraded=True` → a store raised. The count is a floor, not a measurement.

### A real defect found while instrumenting, not just a gap closed

All five stores in `CognitiveTurnKernel._recall` — hybrid, agent, department,
ledger, workspace — swallowed their exception into **`logger.debug`**. Debug is
off in production, so a store failing on *every turn* was both invisible and
byte-identical to a store that found nothing. All five now log at WARNING and
record `error` per source, and a test asserts `logger.debug` does not appear in
`_recall` at all, because the log level *is* the defect and no behavioural test
can observe it.

This matters for the hardening decision: it means the census's inability to see
memory was **two** problems stacked, not one, and the second could have hidden a
permanently broken store behind an apparently-empty one.

### What the numbers now say

Memory recall genuinely works when there is data: **28 rows recalled** in the
probe org across three stores, and **20** on the real production turn above. So
the census's zero was the instrument plus real orgs having nothing to recall —
**not** a broken recall path. That is a materially better starting point for any
hardening scope than the census could establish.

### Caveat on the baseline, stated rather than discovered later

The signal exists from `9222036d` forward. **Historical turns carry no
`memoryRecall` block**, so re-running `probe-memory-reach.py` over a 30-day
window will still report near-nothing for turns predating the deploy. That is
correct behaviour, not a regression. A real adoption baseline accrues from
2026-09-03 onward, and `memory.recalled` is the cheap way to ask for it.

**The hold recommendation below stands unchanged.** Closing the instrument was
the prerequisite, not the hardening. Adoption is still 0 of 146 agents and 1
memory row in a real org, and those are the numbers that decide whether hardening
can be proven against anything but probe traffic.

---

**Not recommended now:** any recall-quality work — the exact-match caveat
included. `Memory Phase 1` opaque-alias vectors are **exact HMAC matches** of
normalized mentions, so `"Sarah"` does not match `"Sarah Smith"`. That is a real
limitation and a plausible hardening target, but with 1 real row it cannot be
measured as a miss rate, only asserted.

## Re-open triggers

- Any real org enables `use_memory` on an agent (currently **0 of 146**)
- `agent_memories` rows in real orgs exceed ~50 (currently **1**)
- The promotion queue is adjudicated at all (currently 3 pending, 0 audited)
- A real customer reports the assistant forgetting or misremembering context

## Governance note

Memory is the one area in this program where a schema gate is explicitly **not**
authorization. Per `docs/ENGINEERING_STANDARDS.md` §4, PII / third-party ML
purpose requires a **named owner and a written option choice**, separate from
engineering approval. Memory Phase 1 waited for STA-312 sole-owner sign-off and
Option B. Any Prompt 3 work that widens what memory stores or how it matches
needs that same explicit step — an instrumentation-only change does not, since
it adds no new data category and no new matching behavior.
