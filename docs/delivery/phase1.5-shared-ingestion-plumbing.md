# Phase 1.5 — Shared ingestion plumbing (generalize before packs)

**Status:** IN PROGRESS — implementation started 2026-07-13. **Blocks** Executive / MSP / Sales Intelligence Pack builds.  
**Date:** 2026-07-13  
**Parent:** `docs/delivery/master-knowledge-intelligence-packs-program.md`  
**Why this exists:** Phase 1 made the pack/install/`auth_mode` layer global. The data path under it (`fetch → cache → normalize → KG → signal`) is still per-source bespoke — same shape as Wave 1 (two paths pretending to be one), one layer deeper. Closing this **before** three packs land avoids four slightly-different pipelines to unify later.

**Analogy (do not soft-pedal):** Wave 1 unification problem at data plumbing instead of execution.

**Impl pointers (Gate A):**
- `backend/app/intelligence_packs/shared/durable_cache.py` — `cache_get` / `cache_set`
- `backend/app/intelligence_packs/shared/normalize.py` — `normalize_source_result` + `register_mapper`
- `backend/app/intelligence_packs/shared/provenance.py` — `write_external_entity_with_provenance`
- `backend/app/intelligence_packs/shared/signals.py` — `PackSignalDefinition` + `register_signal`
- `backend/app/intelligence_packs/shared/mappers.py` — FRED / NVD / World Bank registrations only
- `backend/app/intelligence_packs/shared/pipeline.py` — `run_shared_ingestion`
- Smoke HTTP (not chat): `POST /api/intelligence-packs/plumbing/smoke`
- Migration preflight: `docs/delivery/phase1.5-migration-preflight.md` (needs Option A/B/C)

---

## In scope

Prove one shared pipeline with **FRED + NVD** as the first two registrations, then **World Bank** as the third-source generalization proof.

| Shared surface (exactly one of each) | Vendor-specific (allowed) |
|--------------------------------------|---------------------------|
| `cache_get` / `cache_set` | Cache key construction inputs from mapper/fetch |
| `normalize_source_result` **dispatcher** | Exactly two mappers for FRED + NVD initially; third mapper for World Bank — **plugged into** the dispatcher, not a parallel normalize path |
| `write_external_entity_with_provenance` | Entity/type fields produced by the mapper |
| `PackSignalDefinition` **registration path** | Signal detector config / predicate per registration |

**Hard rule:** After Phase 1.5, you must be able to point at **ONE** of each shared function above — with FRED, NVD, and World Bank as **registrations against** them, not copies of them.

---

## Explicitly out of scope (do not sneak in)

| Item | Owner phase | Notes |
|------|-------------|-------|
| Agent / tool / router wiring so chat can call FRED/NVD/WB live | **Phase 3** (Executive pack proof case) | Confirmed deferred. Phase 1.5 must **not** claim “agent can call FRED in chat.” Track separately below. |
| Executive / MSP / Sales pack catalog UX, demos, workflows | Pack track **after** 1.5 DONE | Blocked until 1.5 closes with live evidence |
| CRM outcome emit production callers | **Phase 5 precondition** (gap) | Schema + `ingest_*` exist; zero prod callers — not a 1.5 blocker; see below |
| OpenCorporates commercial activation | Human/Cesar license gate | Client may use shared path later; live enable still gated |
| Crunchbase / PDL → KG/Memory | Governance stop-line | Unchanged |
| Phase 5 ML | HELD | Unchanged |

### Agent/tool/router ownership (no ambiguity)

- **Phase 1.5 owns:** shared cache → normalize → KG/provenance write → PackSignalDefinition path, exercised via a **dedicated live smoke / service invoke** on prod (HTTP or admin-authenticated script hitting the shared functions). Not governed chat.
- **Phase 3 owns:** wiring those same shared functions into the real agent/tool/router path so an agent can call FRED/NVD (and pack sources) live through chat as part of the Executive Intelligence Pack proof case.
- Phase 1.5 **DONE** does **not** mean chat-callable sources. Phase 3 **DONE** does.

### CRM outcomes → Phase 5 precondition (flagged, not blocker)

`crm_recommendation_outcomes` + `ingest_crm_recommendation_outcome` exist; **zero production callers**; live artifact waiting on CRM sync. This confirms Phase 5’s “real outcome data volume” precondition is **not close**. Expectation-setting only — **do not** expand Phase 1.5 to wire CRM emit.

---

## Acceptance gates (all required)

### Gate A — Same shared functions (not lookalike parallels)

Point-to test after implementation:

1. **ONE** `cache_get` / `cache_set` (durable; vendor + key + TTL + provenance fields).
2. **ONE** `normalize_source_result` dispatcher with vendor-specific mappers registered into it (FRED mapper + NVD mapper; later WB mapper) — not two/three independent normalize modules that happen to share a TypedDict.
3. **ONE** `write_external_entity_with_provenance`.
4. **ONE** PackSignalDefinition registration path (FRED signal + NVD signal as two registrations).

Fail if FRED and NVD each have their own cache/normalize/KG/signal stack that “looks similar.”

### Gate B — Third-source proof (World Bank)

After FRED + NVD pass Gate A on the shared path:

1. Add World Bank as the live third source.
2. **Allowed new code:** (a) World Bank mapper plugged into the existing dispatcher, (b) one `PackSignalDefinition` registration, (c) catalog/`auth_mode` entries if missing.
3. **Forbidden for DONE:** changes to `cache_get`/`cache_set` internals, `write_external_entity_with_provenance` internals, or the PackSignalDefinition **registration mechanism** itself — beyond accepting the new registration.
4. If WB requires touching those shared internals → abstraction **not done**; say so; do **not** mark Phase 1.5 DONE.

### Gate C — Live prod evidence (not local-only)

On Railway tip SHA, for **FRED, NVD, and World Bank** each:

| Evidence | Required |
|----------|----------|
| Durable cache row | Present with provenance / vendor / TTL semantics |
| KG or external-entity write with provenance | Present via shared writer |
| Signal registration exercised | PackSignalDefinition path produces a detectable signal (or persisted signal row) for that source |

Artifact: `docs/delivery/phase1.5-shared-plumbing-live.json` (or per-source siblings rolled into one) with tip SHA, org, and row IDs.  
Unit/local tests are necessary but **never** sufficient (same bar as Phase 1 HTTP closure).

### Gate D — Phase ownership checklist signed in artifact

Live artifact must include explicit fields:

```text
agent_tool_router_wiring: "deferred_to_phase_3"
crm_outcome_emit: "flagged_phase_5_precondition_gap"
third_source: "world_bank"
shared_functions_unchanged_for_third_source: true | false
```

If `shared_functions_unchanged_for_third_source` is false → Phase 1.5 is PARTIAL, not DONE.

---

## Build order (when implementation starts)

1. Durable cache table + shared `cache_get` / `cache_set` (replace/augment in-memory-only `SourceCache` for this path).
2. `NormalizedExternalRecord` + `normalize_source_result` dispatcher; register FRED + NVD mappers.
3. `write_external_entity_with_provenance` (thin shared write; reuse KG/`external_entities` as designed — one API).
4. Minimal `PackSignalDefinition` registry + two registrations (macro/time-series style for FRED; CVE/KEV-style for NVD).
5. Live smoke for FRED + NVD on prod (Gate C partial).
6. World Bank mapper + signal registration only (Gate B); re-run live for all three (Gate C full).
7. Mark DONE on master program doc only when Gates A–D pass.

**Do not start Executive Intelligence Pack build until step 7.**

---

## Relation to older “Phase 2 — Pipeline wiring”

Phase 1.5 **is** the shared-pipeline generalization that Phase 0/1 docs called “Phase 2 — Durable cache + KG + minimal signal” at the framework layer. After 1.5 DONE:

- Old Phase 2 shrinks to pack-specific signal *content* / Memory opt-in usage on top of the shared path (not new plumbing).
- Pack track (Executive → MSP → Sales) may start; Phase 3 still owns agent/tool/router chat wiring for the Executive proof.

---

## Stop-lines (unchanged)

- No Crunchbase/PDL → KG/Memory without Cesar governance clear.
- No OpenCorporates tenant enable without commercial license confirmation.
- No Phase 5 ML start.
- No claiming “one pipeline” DONE without Gate B (World Bank) + Gate C (prod).
