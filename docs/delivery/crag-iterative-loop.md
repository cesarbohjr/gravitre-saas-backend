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

**NOT YET RUN.** Requires the deploy and, for the keyword arm, the migration.
Recorded here as NOT PROVEN rather than left to be assumed from green tests: a
green test proves the path behaves correctly, never that production takes it.

Outstanding to close Phase 5:

1. Push, deploy, confirm live `git_sha`.
2. Apply migration `20260903100000` (additive, idempotent; the FTS path degrades
   to the old unfiltered fetch with a WARNING until then, so the code is safe to
   deploy ahead of it but the fix is not live).
3. Probe-derived trace showing `finalStance` populated and
   `finalStanceInferred=false` on a real turn through the deployed tip.
4. Probe-derived trace showing a discard and a refinement each occurring once.
5. Measured latency on a simple turn confirming no regression.

Every claim in that list must be labelled organic or probe-derived. Organic
volume is honestly low — 36 real turns in the last measured month — so
probe-derived is the expected kind here, and it is real evidence, just not the
same claim.

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
