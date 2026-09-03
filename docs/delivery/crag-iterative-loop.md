# CRAG iterative loop — delivery record

Prompt 1, built on the already-proven `evidence.sufficiency.assessed` instrument
rather than beside it.

Status of each phase, with the honest label on every claim.

---

## What the prompt assumed, and what was actually true

Two premises were wrong, and finding that out early changed the work. Recorded
because being wrong about the starting state is the normal case in this program,
not the exception.

**"The verdict is currently binary and rows are judged but never acted on, that
action is this prompt's real, new work."**

Half right. The verdict was binary. But the rows were already acted on: the loop
in `build_unified_turn_knowledge_context` escalated to an untried source on an
insufficient verdict, bounded at 2–3 rounds, and had been doing so since the
sufficiency loop shipped. Phase 2's "bounded retry loop" existed.

What genuinely did not exist was any response other than *adding more evidence*.
That is the real new capability, and it is narrower and sharper than the prompt
described: **discard on INCORRECT, refine on CORRECT.**

**"Org RAG has no persisted keyword index (no tsvector+GIN), unlike the
Knowledge Fabric which already has one. Bring org RAG's retrieval up to the same
real, hybrid standard."**

The index was genuinely absent. But org RAG was already hybrid — vector RPC,
BM25 keyword arm, RRF merge, cross-encoder rerank — and in one respect ahead of
the Fabric, whose FTS arm cannot order by `ts_rank` at all. BM25 produces a real
relevance order.

The real defect was different and worse: the keyword arm had no query to work
with. See Phase 3.

---

## Phase 0 — state of the existing mechanism

`evidence.sufficiency.assessed` confirmed still firing and recording `bar`,
`final_sufficient`, `additional_rounds_used`, `stopped_because`, `assessorRan`
cross-checked against `MODEL_ASSESSORS`. Deployed at `fcd244de`, previously
verified by an unprompted production smoke job.

Hook point confirmed correct: the verdict is produced and consumed inside one
function, so the new actions attach where the decision already lives. No second
sufficiency check and no new emission point were created.

---

## Phase 1 — three-way classification

`SufficiencyVerdict.stance` ∈ {`correct`, `incorrect`, `ambiguous`, `unknown`}.

`unknown` is deliberately a fourth state and not one of CRAG's three. "Was not
judged" and "was judged and failed" produce identical evidence unless they are
named apart — Class C, and the reason a failed assessor cannot authorise
destroying evidence.

**`stance` is authoritative.** `sufficient` is derived from it in `__post_init__`
so the two cannot drift. Two fields encoding one judgement, free to disagree, is
how `assessorRan` read `False` for weeks while the assessor ran fine (Class B).

**Nothing reaches INCORRECT by default.** It is the branch that destroys
evidence, so it requires the assessor to say so explicitly. An absent stance, an
unparseable one, a legacy bool and a failed model all land on AMBIGUOUS or
UNKNOWN. The deterministic short-circuits follow the same principle: no evidence
at all is INCORRECT (nothing to preserve), but a missing citation is AMBIGUOUS,
because on-topic excerpts must not be destroyed over a metadata gap.

`finalStanceInferred` is recorded per turn. Without it a defaulted stance reads
exactly like a reasoned one and the whole three-way signal is unfalsifiable.

---

## Phase 2 — the actions

| Stance | Evidence | Round |
|---|---|---|
| CORRECT | kept; refined to the load-bearing subset when the assessor names one | none spent |
| AMBIGUOUS | kept, combined with a new source | spent |
| INCORRECT | **discarded** | spent |
| UNKNOWN | kept | none spent; loop stops and says why |

**The discard clears the rendered sections, not only the rows.** Clearing only
the rows would have left the discarded text in the prompt while every audit
count said it was gone — a fix one layer below the thing that decides what the
model reads. Class A. `test_discard_removes_the_rendered_sections_too` exists
for exactly this, and a structural AST guard holds the two clears together.

**Refinement is guarded three ways** because over-eager refinement silently
deletes good evidence: only on CORRECT, only on a strict non-empty subset, never
down to nothing. Its index basis is `substantive_rows`, defined once — if the
assessor and the caller disagree about which rows are in scope, refinement keeps
excerpts the assessor never endorsed while reporting a clean refinement.

**Fail-open still announces itself, and now says the right thing.** "Answer only
what the excerpts support" is an invitation to answer from general knowledge
when the excerpts were all discarded, so that case gets its own `NO USABLE
EVIDENCE` advisory.

**Latency tiering unchanged.** The casual bar skips the whole mechanism; a
conversational turn makes zero assessor calls, held by test.

**Mutation proof:** `scripts/mutate_crag_three_way.py`, **14/14 caught**,
including the retry-trigger mutation the prompt asks for by name.

Three escaped on the first run and all three were real holes:

- refining on a non-CORRECT stance was green because only the CORRECT branch
  populates `keep` today — a load-bearing gate with nothing holding it.
- the error path returning INCORRECT instead of UNKNOWN was green because the
  loop happens to `break` on `ASSESSOR_ERROR` before the discard. That ordering
  was the only thing between a fast-model hiccup and every excerpt being
  destroyed.
- misaligning the refinement index basis was green because every stubbed row had
  content, so the two indexings coincided.

---

## Phase 3 — retrieval quality

### The keyword arm had no query

```
client.table("rag_chunks").select(...).eq("org_id", ...).limit(500)
```

No terms, no `ORDER BY`, and no query parameter on the function with which to do
better. BM25 ranked an arbitrary 500-chunk slice. Under 500 chunks per
`(org, environment)` that is the whole corpus and the arm is exact; over it, the
arm silently becomes a sample chosen by whatever order Postgres returned, and
nothing reported which regime an org was in.

**Reachability measured before fixing** (`orgrag-keyword-reach.json`): 1 chunk
platform-wide, 0 scopes over the cap. **Not a live defect.** A latent trap that
fires silently on the first real corpus.

Fixed by giving Postgres the terms: migration `20260903100000` adds
`content_tsv` + GIN mirroring the Fabric's definition exactly, and
`fetch_bm25_corpus` pre-selects on it. `.limit()` before `.text_search()`,
options positional, no `config=` kwarg — all three are how the Fabric's arm
stayed dead for months, and all three are now guarded at the call site by AST,
not only through a mock.

It returns `(rows, reach)` rather than offering reach as an optional out-param,
so no caller can drop the signal. Six named states, because these are six
different facts that previously all looked like one list of rows:

| state | meaning |
|---|---|
| `exact` | whole scope fetched; BM25 saw everything |
| `fts_filtered` | Postgres pre-selected on keywords |
| `fts_no_match` | filter ran, matched nothing — a real answer, not an absence |
| `truncated` | hit the cap unfiltered: **a sample** |
| `no_terms` | no usable keywords; not applicable |
| `empty` | scope resolved to no sources |

### Contextual chunk enrichment

Flag-gated **off** (`rag_contextual_enrichment_enabled`). One model call per
document for a synopsis, then per-chunk context composed deterministically from
that synopsis, the title, the chunk's position and its immediate neighbours.

This is a cheaper approximation of Anthropic's per-chunk call, **not** a
reproduction. Their 35% figure is their result for their variant on their
corpora; it is not a claim about this one.

`content` is untouched and stays the only text ever displayed or cited, so a
generated synopsis can never be shown to a user as something their document
said. The prefix is persisted for auditability, and because an unpersisted
prefix makes "never enriched" and "enriched with nothing" identical. Embedding
cost is counted over what was actually sent.

### Before/after — read the labels

`orgrag-phase3-beforeafter.json`.

**Keyword reach** (deterministic, no model). 2000-chunk corpus, cap 500,
matching chunk at index 1500. Before: 500 fetched, `reach=truncated`, matching
chunk **unreachable** — no BM25 tuning could have found it, the row never left
Postgres. After: `reach=fts_filtered`, found.

**Enrichment** (**synthetic** corpus, **real** embeddings). recall@1 3/8 → 6/8,
MRR 0.6875 → 0.875, 60% reduction in top-1 failures.

The "real, honest before/after on the same real test set" Phase 3 asked for is
**not obtainable**: there is one chunk in production. Quality arithmetic on n=1
would be exactly the confident-but-empty number this program has spent weeks
removing. So the corpus is invented and the embeddings, ranking and numbers are
real, and that distinction is stated wherever the numbers appear.

Two further honest notes:

- **One of the eight queries regressed**, rank 1 → 2. Enrichment is not free:
  adding document context makes same-document chunks compete more closely.
- **recall@3 was already 8/8 both ways.** The gain is in top-1 precision, not
  recall, on a 16-chunk corpus where recall@3 saturates trivially.

**Mutation proof:** `scripts/mutate_orgrag_phase3.py`, **15/15 caught**,
including reinstating the exact `config=` kwarg that killed the Fabric arm and
escaped its first mutation run.

---

## Phase 4 — composition

Contradiction detection reads `rag_source_rows` after the loop, so it sees the
post-discard, post-refine set. A conflict is never reported between two excerpts
one of which was thrown out as off-target — that would invent a warning about
evidence the user will never see.

Held by test, not by reading the code:
`test_contradiction_check_sees_the_surviving_evidence_not_the_discarded`.

---

## Phase 5 — live verification

**PASS (probe-derived), 10/10 checks.** `scripts/prove-crag-phase5-live.py`,
raw output in `docs/delivery/crag-phase5-live.json`.

**Evidence label: probe-derived, not organic.** Deliberate turns, run by hand.
Organic volume is honestly low — 36 real turns in the last measured month — so
probe-derived is the expected kind here. It is real evidence; it is not the
claim that real users triggered it.

Prod served `985149ad`, the last commit touching `backend/` or `supabase/`. The
probe compares against that rather than `HEAD`, because a docs-only commit ahead
of prod is not a version mismatch, and a check that fails on one invites being
relaxed for a reason that is not always true.

| Check | Result |
|---|---|
| prod serves this tip | PASS |
| hard turn engaged the loop | PASS |
| routed turn engaged the loop | PASS |
| simple turn latency unregressed | PASS — 901ms |
| audit carries a stance | PASS |
| stance is reasoned, not inferred | PASS — `finalStanceInferred=false` |
| forced discard destroyed rows | PASS — 6 rows |
| forced refine narrowed rows | PASS — 6 → 1 |
| simple turn paid for none of it | PASS — 0 assessor calls |
| nested block and audit row agree | PASS |

The strongest single result is **not** one of the forced branches. A hard,
single-jurisdiction turn with the **real** assessor and no stubbing classified
`INCORRECT`, spent 2 rounds, and **destroyed 6 real evidence rows**. Unforced,
on real retrieved evidence, through the deployed tip.

### The probe passed the first time for the wrong reason

Recorded because it is the same failure this program keeps finding, now in its
own verification harness.

First run: 6/8, with `forced_refine_executed` failing. The obvious reading was a
bug in the refinement branch. It was not. The probe drove its turns through
`run_unified_turn_shadow` **with no knowledge packs assigned**, so every turn
retrieved zero rows. Refinement cannot narrow an empty list, so it correctly did
nothing.

The part that matters is the check that **passed**:
`forced_discard_executed` was true because the `discards` counter incremented —
while `discarded_rows` was **0**. The discard branch had executed and destroyed
nothing. A green check over an empty evidence set, proving the line was reached
and nothing more. **Class B, in the instrument built to prove Phase 5.**

Both checks were rewritten to assert the outcome rather than the mechanism:
`forced_discard_destroyed_rows` requires `discarded_rows > 0`, and
`forced_refine_narrowed_rows` requires `refined_to < refined_from`. The forced
branches now run through `build_unified_turn_knowledge_context` with the pack
assigned explicitly, so the branches are handed real rows or the check fails.

The second failing check, `simple_turn_skipped_the_loop`, was also the
instrument. It asserted `skipped == "casual_bar"`. The conversational turn never
reaches knowledge augmentation at all, so it emits no sufficiency block and
`skipped` is absent. The turn was free — 901ms, zero assessor calls — and the
check failed it for skipping by the wrong door. Now asserts the property.

### Open finding: the hardest query shape retrieves nothing

Found while diagnosing the above, and worth more than the phase that surfaced it.

The Phase 5 multi-hop query — Ontario health-information breach deadlines versus
California consumer breach deadlines — routes to **zero knowledge packs**:

```
hard_multihop   packs=[]             depts=[]        juris=['US-CA','CA-ON','US-federal']
routed          packs=['pack.legal'] depts=['legal'] juris=['CA-ON']
```

`classify_knowledge_query` resolves three jurisdictions correctly and no
department, and packs are selected by department. A jurisdiction-only route
yields nothing. So the query most obviously about legal compliance retrieves no
legal evidence.

The loop behaved correctly on it: classified `INCORRECT`, escalated twice, hit
its bound, and reported the shortfall honestly rather than answering
confidently. That is the designed behaviour and it worked. But reading turn A as
"the loop works on hard queries" would be exactly wrong — it iterated twice over
nothing. **An iterative loop cannot repair a routing miss; it can only spend
rounds discovering there is nothing there.**

Not fixed here. Changing pack selection to fall back on jurisdiction is a real
retrieval-policy change with real blast radius, and it is not what Phases 1–5
authorised. Logged as **OPEN** in the risk register.

### Migration `20260903100000` — NOT APPLIED

The org RAG keyword index is **not live**. The code degrades to the old
unfiltered fetch with a WARNING, so the deployed tip is safe, but the Phase 3
keyword-reach fix does not take effect until the migration runs.

Not applied because it is a production schema change and this program requires
those to be an explicit human choice, not an agent's reading of "complete Phase
5". Measured impact of applying it today is nil — 1 chunk platform-wide, 0
scopes over the 500 cap — and the value is entirely in the first real corpus,
where the old behaviour fails silently.

---

## Files

| Path | Role |
|---|---|
| `backend/app/services/evidence_sufficiency_service.py` | stances, parser, `substantive_rows` |
| `backend/app/services/unified_turn_knowledge_context.py` | discard, refine, advisories, audit |
| `backend/app/rag/retrieval.py` | keyword arm, reach states |
| `backend/app/rag/contextual_enrichment.py` | synopsis + deterministic context |
| `backend/app/rag/ingest.py` | embeds enriched text, persists prefix |
| `supabase/migrations/20260903100000_rag_chunks_fts.sql` | `content_tsv` + GIN, `context_prefix` |
| `backend/tests/services/test_crag_three_way_loop.py` | Phases 1, 2, 4 |
| `backend/tests/rag/test_orgrag_keyword_and_enrichment.py` | Phase 3 |
| `scripts/mutate_crag_three_way.py` | 14/14 |
| `scripts/mutate_orgrag_phase3.py` | 15/15 |
| `scripts/probe-orgrag-keyword-reach.py` | reachability, measured before fixing |
| `scripts/prove-orgrag-phase3-beforeafter.py` | before/after, both parts |
| `scripts/prove-crag-phase5-live.py` | Phase 5 live proof, 10/10 |
| `docs/delivery/crag-phase5-live.json` | its raw output |

---

## Still open

| Item | State |
|---|---|
| Migration `20260903100000` | **NOT APPLIED** — needs an explicit human decision |
| Multi-jurisdiction queries route to no packs | **OPEN** — real retrieval gap, unfixed |
| Fabric keyword arm has no `ts_rank` ordering | **OPEN** — carried from the prior phase |
| Organic (non-probe) trace of a discard | **NOT PROVEN** — awaits real traffic |
