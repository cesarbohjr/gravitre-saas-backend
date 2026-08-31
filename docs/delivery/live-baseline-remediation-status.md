# Live Baseline Remediation — standing status

Standing record for the remediation program opened against the Live Baseline
Audit (2026-08-27). One row per phase. A phase is CONFIRMED WORKING only with a
live artifact behind it; local test suites do not qualify on their own, because
this program has already found six cases where a green suite was the reason a
bug survived rather than the reason it was found.

Last updated: 2026-08-29.

| Phase | Subject | Status |
|-------|---------|--------|
| 1 | Voice fix deploy + human verification | PARTIAL — engineering shipped, human mic test pending Cesar |
| 2 | MSP Clay→HubSpot workflow | PARTIAL — blocked on a real Clay webhook URL |
| 3 | F6 verified-completion coverage | **CONFIRMED WORKING** |
| 4 | Action-resolution mismatch safety net | **CONFIRMED WORKING** |
| 5 | Vendor-contract drift scan | NOT BUILT — prerequisite now exists (see Phase 1 below) |
| 6 | Write-authority governance matrix | **CONFIRMED WORKING** |
| 7 | Conversational + visual consistency per surface | NOT BUILT |
| 8–10 | Marketplace audit, stale evidence, cohesion pass | DEFERRED pending credential/access decision |

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

| Provenance | Count | What it means |
|------------|------:|---------------|
| `dedicated` | 420 | read from the executor that issues the request |
| `name_inferred` | 233 | generic `catalog_http` executor; route derived from the action suffix — real, but **never checked against the vendor** |
| `dedicated_multi` | 33 | reaches more than one endpoint; each individually reviewed |
| `manual_verified` | 15 | hand-read where static analysis cannot see (SDK calls, non-literal paths) |
| `route_table` | 7 | hand-written method+path table |
| no vendor endpoint | 19 | SMTP, in-process, browser-driven, or no executor — recorded with the reason |

The 233 `name_inferred` routes are the honest weak spot and are flagged as such
in the served payload. They are what Gravitre sends; nothing has confirmed the
vendor accepts them. A drift scan must treat them as unproven rather than as
agreement.

Vendor contracts: 20 machine-readable locations verified by live fetch
(`docs/delivery/vendor-contract-probe.json`), covering 271 actions.

Live spot-check (`docs/delivery/api-reference-spotcheck-live.json`): 23 actions
across 8 vendors invoked through the normal `invoke_tool` path with the outbound
request read off the wire. 23 of 23 hit the recorded endpoint; 1 skipped for lack
of a live record id. Negative control
(`docs/delivery/api-reference-spotcheck-negative.json`): 6 deliberately wrong
endpoints, all 6 rejected.

**Phase 5's drift scan itself is not built by this work and remains separately
scoped.** This is the foundation it was gated on, nothing more.

## Still pending Cesar

1. Human microphone test on `/ai` plus three department agent chats.
2. Triggering the `voice-duplex-browser.spec.ts` CI run so the regression guard
   is proven to actually run.
3. The outcome-card screenshot.
4. The credential/access decision that unblocks Phases 8–10.
