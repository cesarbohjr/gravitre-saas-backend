# Live Baseline Remediation — standing status

Standing record for the remediation program opened against the Live Baseline
Audit (2026-08-27). One row per phase. A phase is CONFIRMED WORKING only with a
live artifact behind it; local test suites do not qualify on their own, because
this program has repeatedly found a green suite to be the reason a bug survived
rather than the reason it was found. That count stood at six when this record
opened and has grown since; the authoritative tally is kept in
`docs/delivery/dormant-model-calls.md`, whose most recent addition is a keyword
retrieval arm that was dormant for the entire life of the feature while its
tests passed against mocks that accepted a calling convention the real client
does not have.

Last updated: 2026-09-03.

### Phase status

| Phase | Subject | Status |
|-------|---------|--------|
| 1 | Voice fix deploy + human verification | PARTIAL — engineering shipped, human mic test pending Cesar |
| 2 | MSP Clay→HubSpot workflow | PARTIAL — blocked on a real Clay webhook URL |
| 3 | F6 verified-completion coverage | **CONFIRMED WORKING** |
| 4 | Action-resolution mismatch safety net | **CONFIRMED WORKING** |
| 5 | Vendor-contract drift scan | NOT BUILT — prerequisite now exists (see "Phase 5 prerequisite" below) |
| 6 | Write-authority governance matrix | **CONFIRMED WORKING** |
| 7 | Conversational + visual consistency per surface | NOT BUILT |
| 8–10 | Marketplace audit, stale evidence, cohesion pass | DEFERRED pending credential/access decision |

No row moved in this update. The work landed since 2026-08-31 belongs to an
adjacent program and touches no phase here; see "What changed" below.

### Deploy state

Live `git_sha` is `2a2e0355`, confirmed at `/health` at
`2026-09-03T21:21:02Z` (`environment: prod`, database/cache healthy). Local
`main` is two commits ahead: `82c647a1` is docs-only, and `2172e618` touches
only `backend/app/services/memory_temporal_service.py` from the parallel memory
hardening work. Neither is on any path this record covers.

**The tip has moved 86 commits and 48 `backend/app` files since this record was
last updated against `123c1960`, so the artifacts below are no longer
self-evidently current.** That was checked rather than assumed. For the three
phases marked CONFIRMED WORKING, both the implementation and its call sites are
byte-untouched across that range:

| Phase | Implementation | Call sites | Touched since `123c1960`? |
|-------|----------------|-----------|---------------------------|
| 3 | `write_success_verification.py`, `entity_get_verify.py`, `field_assert_verify.py`, `success_verification_catalog.json` | `chat_connector_execution_service.py`, `workflows/handlers.py` | **No** |
| 4 | `approval_action_binding.py` | — | **No** |
| 6 | `catalog_write_authority`, `react_write_gate` | — | **No** |

So those three artifacts still describe the code production is running, and the
statuses stand without re-verification. This is a narrower claim than "the
program is still green" and is deliberately the only one the evidence supports.

One Phase 1 file did change: `voice_session_service.py` in `5ece38df`, +7/-4,
routing two telemetry dicts (`cognitiveStageMs`, `latencyBreakdown`) through
`safe_normalize_stored_dict`. That is latency-breakdown normalisation, not the
audio capture path, so the pending human microphone test is unaffected in
substance.

---

## Phase 3 — write verification actually runs — CONFIRMED WORKING

Three separate failures were found and closed. Each has a live artifact.

**The declared read was never executed.** Actions declared `follow_up_entity_get`
but the adapter never issued the read, so an acknowledgement was being counted as
a verified write.

- `docs/delivery/f6-entity-get-verify-live.json` — HubSpot contact `273899005900`
  returned `follow_up_entity_get_confirmed`; fabricated id `99942035368423`
  returned `follow_up_read_returned_no_entity`. Both at git_sha `3d544d65`,
  `2026-08-29T03:25:59Z`–`03:27:08Z`.

**State changes could not be verified at all**, because a record existing does not
prove a field changed. Added `follow_up_field_assert`.

- `docs/delivery/f6-field-assert-verify-live.json` — HubSpot deal `222800541678`
  moved `appointmentscheduled` → `qualifiedtobuy`; the assert confirmed the
  stored value, and re-asserting the old stage was correctly reported
  `field_value_mismatch`. git_sha `3d544d65`, `2026-08-29T03:28:06Z`.

**The chat surface never scheduled verification at all**, while the workflow
surface did — the dual-path gap this program keeps finding.

- `docs/delivery/f6-prod-process-verify-live.json` — production run
  `8ca2e994-718d-4af5-9c8c-c61009e8335b` stamped
  `entity_get_verify.verified=true` for contact `273893648376` after re-reading
  HubSpot **inside the deployed process**, git_sha `b4afc365`,
  `2026-08-29T05:27:04Z`–`05:27:33Z`. Fixes in `34bf5185`, `b4afc365`.

Remaining coverage work is scoped by provability in
`docs/delivery/f6-remaining-feasibility.json`, not by assumption.

## Phase 4 — action-resolution mismatch safety net — CONFIRMED WORKING

`assert_plan_matches_binding` refuses execution when the action about to run is
not the action that was approved. Proven across three vendor pairs on both
approval gates against the real registry, and shown load-bearing by disabling it
(`backend/scripts/scratch_verify_approval_net_load_bearing.py`).

The gap closed in this pass was observability: a refusal on real traffic left no
trace. `b4afc365` added a standing audit event,
`connector.approval.action_mismatch`
(`backend/app/services/approval_action_binding.py:22`), emitted every time the
net refuses, with the refused action identity in the payload.

Honest caveat: the audit path is proven by test and by code, and no real
production refusal has occurred yet — which is the expected state for a net that
only fires on a bug. The trace is standing so that the first real occurrence is
visible rather than silent.

## Phase 6 — write-authority governance matrix — CONFIRMED WORKING

MCP-sourced actions, extension-bridge writes, and capability-resolved tools all
route through the same `catalog_write_authority` / `react_write_gate` path as
chat direct-create.

- `docs/delivery/capability-write-authority-live.json` — against the deployed
  backend, both `hubspot_contacts_create` and the capability-resolved
  `capability__crm__contact__create` returned `write_approval_required` with
  `pending_approval=true`, `2026-08-27T20:40:54Z`.
- `backend/tests/test_write_authority_matrix.py` re-run and current.

Scheduled workflow steps perform connector writes without a per-step runtime
approval. Cesar reviewed this and confirmed it is intended; it is recorded here
as a known, accepted characteristic so it cannot silently drift into looking
like a defect or like parity.

---

## Phase 5 prerequisite — action→endpoint mapping (api_reference)

Phase 5 was correctly found unbuildable: 724 of 727 catalog actions had no
`api_reference`, so there was nothing for a drift scan to diff a vendor contract
against. That mapping now exists.

- Extractor: `backend/scripts/build_api_reference_map.py` — walks each action's
  real executor to the call that issues the HTTP request and transcribes the
  method and path from source. Not derived from the action's name.
- Served at: `ActionSpec.to_dict` → `apiReference`, with
  `apiReferenceProvenance` alongside it.
- Data: `backend/app/connectors/action_catalog/data/api_reference_map.json`
- Full report: `docs/delivery/api-reference-map.json`

Coverage, 727 of 727 actions accounted for:

| Provenance (as served) | Count | What it means |
|------------|------:|---------------|
| `dedicated` | 420 | read from the executor that issues the request |
| `name_inferred` | 233 | generic `catalog_http` executor; route derived from the action suffix — real, but **never checked against the vendor** |
| `dedicated_multi` | 33 | reaches more than one endpoint; each individually reviewed |
| `no_vendor_endpoint` | 19 | SMTP, in-process, browser-driven, or no executor — no endpoint, reason carried in `apiReferenceNote` |
| `manual_verified` | 15 | hand-read where static analysis cannot see (SDK calls, non-literal paths) |
| `route_table` | 7 | hand-written method+path table |

The 233 `name_inferred` routes are the honest weak spot and are flagged as such
in the served payload. They are what Gravitre sends; nothing has confirmed the
vendor accepts them. A drift scan must treat them as unproven rather than as
agreement.

Two of those labels only became visible in the served payload on 2026-08-31. The
generator had been stamping `manual_verified` on the 19 actions that have no
vendor endpoint at all, and flattening `dedicated_multi` to `dedicated`, so a
drift scan reading the shipped data would have been told an SMTP send was a
hand-read route with a missing path, and that a reviewed pick among several
endpoints was the only one reachable. Both labels are now emitted precisely and
guarded by tests that were mutation-proven — relabelling the 19 and flattening
the 33 each fail their guard
(`backend/scripts/scratch_mutate_provenance_labels.py`).

Vendor contracts: 20 machine-readable locations verified by live fetch
(`docs/delivery/vendor-contract-probe.json`), covering 271 actions.

Live spot-check (`docs/delivery/api-reference-spotcheck-live.json`): 24 sampled
actions across 8 vendors invoked through the normal `invoke_tool` path with the
outbound request read off the wire. 23 of 23 attempted hit the recorded endpoint.
The 24th, `pipedrive.deals.get`, is skipped because the Pipedrive sandbox holds
zero deals — `GET /deals` returns `data: null` with
`more_items_in_collection: false`, so there is no record to fetch. Negative
control (`docs/delivery/api-reference-spotcheck-negative.json`): 6 deliberately
wrong endpoints — a neighbouring object, a wrong verb, a wrong API version — all
6 rejected.

**One of those 23 was a false pass, and the harness found it, not the map.**
`invoke_tool` evaluates connector availability before dispatching, and that
evaluation live-probes other vendors' credentials: Apollo's profile endpoint plus
two Apollo discovery searches, HubSpot token introspection, and so on. That
traffic is real and outbound, so filtering by host or by OAuth path does not
remove it. Apollo's discovery probe calls `POST /mixed_people/api_search` — the
exact endpoint `apollo.people.search` records — so that row had been passing on
pre-flight traffic whether or not the action itself ever ran. The first run after
excluding pre-flight by call origin reported it as `NO_REQUEST`, and the retry
then matched it on its own request, distinguishable by query
(`?query=engineer&limit=1` versus the probe's `?per_page=1`). The same defect was
also mis-attributing another vendor's probe traffic to three unrelated rows as
`MISMATCH`. Pre-flight is now excluded by call stack
(`PREFLIGHT_MODULES` in `backend/scripts/spot_check_api_reference_live.py`) and
each recorded request carries the row and thread it was issued under.

Two smaller harness defects were fixed in the same pass: a `--only` subset run
was overwriting the full-sample artifact, and a local Windows socket failure
(`WinError 10035`) before the request left the machine was being reported as the
endpoint not being reached, rather than retried once and labelled as a runner
problem.

Incidental live finding, recorded for the future drift scan rather than acted on
here: Pipedrive's `GET /deals` returns `deprecation_warning` — "this endpoint will
be removed soon". That is precisely the class of signal Phase 5 is meant to
catch, observed by hand here because the scan does not exist yet.

Deployed-tip readback (`docs/delivery/api-reference-deployed-verify.json`): the
mapping is generated locally, so a green extractor proves nothing about what
production serves. `scripts/verify-api-reference-deployed.py` pulls
`/api/connectors/catalog/actions` off the deployed backend and diffs every action
field-by-field against the committed map — 727 of 727 actions present, 708
carrying an `apiReference` byte-identical to the map, 19 correctly carrying none,
zero endpoint or provenance drift.

**Phase 5's drift scan itself is not built by this work and remains separately
scoped.** This is the foundation it was gated on, nothing more.

## What changed between 2026-08-31 and 2026-09-03

None of it moves a phase row. It is recorded because a status document that
silently skips a 86-commit window is the same failure this program keeps
naming.

**The regression signal this record leans on was not trustworthy for most of the
window.** `Backend (pytest)` was red on `main` from 2026-08-06 until
2026-09-03 — nine distinct causes, not the two believed — and `Integration
Smoke Test`, which declares `needs: [web, backend]`, therefore resolved to
`skipped` on 40 consecutive runs. A skipped job reports no failure, contributes
no annotation, and appears in no failing-checks list, so the absence of red was
not evidence of green. Closed in `5ece38df` plus a follow-up that bounded the
smoke job, which hung 40+ minutes on its first real execution. Recorded in
`dormant-model-calls.md` as the fifth Class C instance.

This does not retract anything above: every status in this record rests on a
live production artifact, not on a suite. It does mean that for this window the
suite would not have caught a regression *into* those paths — which is why the
untouched-file check in the deploy-state section above was done by diff rather
than by re-running tests.

**Both outstanding migrations are applied.** `20260903100000_rag_chunks_fts`
(org RAG `content_tsv` + GIN) and `20260903120000_memory_hardening_temporal`
(`agent_memories` temporal columns, `agent_memory_history`) are both live —
verified by reading `to_regclass` and `information_schema.columns` directly,
6 of 6 temporal columns present and the history table existing.

Migration history was reconciled on 2026-09-03 after direct schema inspection:
the generated duplicate stamps were removed and the already-live migrations
were recorded under their canonical repository versions (`20260903100000`,
`20260903120000`, and `20260903140000`). No DDL was rerun. `supabase migration
list` now reports local and production history fully aligned with no pending or
remote-only entries.

**Adjacent program, separate record.** The dormant-model-call and corrective-
retrieval work accounts for most of the 48 changed `backend/app` files —
Knowledge Fabric keyword retrieval (dormant since written, now fused and
live-verified), knowledge-router department matching, the three-way evidence
classification and its bounded retry loop, and memory recall instrumentation.
Status for all of it lives in `docs/delivery/crag-iterative-loop.md` and
`docs/delivery/dormant-model-calls.md`, not here. It touches no phase in this
record, which is why no row moved.

**One register/code disagreement is knowingly open.** The Context Engine was
formally deferred, but landed on `main` from parallel work in a shared worktree
and its shadow-mode flag still defaults to on, so deferred work computes
diagnostics on informational turns in production while the risk register reads
DEFERRED. Cesar reviewed this and elected to handle the Context Engine
separately; it is recorded here so the disagreement is explicit rather than
discovered later.

## Still pending Cesar

1. Human microphone test on `/ai` plus three department agent chats.
2. The outcome-card screenshot.
3. The credential/access decision that unblocks Phases 8–10.

### Closed from this list on 2026-09-03

**The `voice-duplex-browser.spec.ts` guard is proven to actually run.** It was
listed as pending on the assumption it had never executed. It has:
`.github/workflows/voice-duplex-guard.yml` runs daily at 07:00 UTC plus
dispatch, and `gh run list` shows 8 completed runs, all `success` — one
`workflow_dispatch` on 2026-08-28 and 7 scheduled since, most recently run
`33751784297` at `2026-09-03T11:49:21Z`.

Per the Class C lesson, a green job is not by itself proof the guard inside it
ran, so that was checked separately rather than inferred: in run
`33751784297` the `Run voice duplex guard` step itself reports
`conclusion: success`, not `skipped`, and the run took 1m19s with Playwright
Chromium installed. Durations across the 8 runs are 1m14s–1m44s, consistent
with real spec execution rather than a no-op. This is the distinction the
Integration Smoke Test failure turned on, applied here deliberately.
