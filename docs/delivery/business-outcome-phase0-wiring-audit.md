# BusinessOutcome Phase 0 — Wiring audit

**Date:** 2026-07-20  
**Tip at audit:** `0a389d27` (local main)  
**Rule:** Missing pieces are backend work. No frontend fallbacks.

---

## Prior-round confirmations (closed)

| # | Claim | Verdict | Evidence |
|---|--------|---------|----------|
| 1 | Read surface → scoped action follow-up | **PASS** | tip `5997045b`, conv `77178525-d5ad-4671-936c-dc1610c4d0e8` — Apollo inventory then staged `apollo.lists.create` (`docs/delivery/post-action-read-surface-live.json`) |
| 2 | Auto completion-rec never reaches `invoke_tool` / `execute_write_action` | **PASS** | `backend/tests/services/test_post_action_experience.py` — source ban + AST on `build_post_action_recommendation` / `enrich_execution_turn` / `_turn_from_execution` + `assert_no_execute_surface` |

---

## Module A substrate

**Sole write authority:** `finalize_execution_outcome()` → runs + audit + notifications + `intelligence_outcome_events` + in-process bus.  
**Schema:** `OUTCOME_SCHEMA_VERSION = "1.0.0"` (`execution_outcome.py`).

There is **no** customer-facing `BusinessOutcome` row today. Surfaces that show “what happened” currently mix chat text, `ExecutionResult`, run detail, and ops aggregates — that is the gap this program closes.

---

## BusinessOutcome section readiness

| Section | Status | Backing today | Phase 1 plan |
|---------|--------|---------------|--------------|
| Summary | **PRESENT** | `VerifiedOutputRef.summary` | Project as `sections.summary` |
| Impact | **MISSING** | No impact/ROI on Module A | **Omit** until ground-truth impact exists — never fabricate |
| Evidence | **EXTENDABLE** | `result_url`, `external_url`, entity ref | Project links + entity; no fake artifacts |
| Verification | **EXTENDABLE** | Soft: non-empty summary/URL + connector verifiability gate | Project `verification` only when Module A / connector gate actually passed |
| Explanation | **EXTENDABLE** | `error_summary` + Module D body | Project voice-safe explanation; omit if empty |
| Timeline | **MISSING** on outcome | Steps live on `workflow_steps` / orch `step_results` | Join when `run_id` present; else omit |
| Related Outcomes | **MISSING** | No related IDs | **Omit** until real edges exist |
| Dependencies | **MISSING** on Module A | Separate v8/v10 tables | **Omit** from visible sections until joined |
| Recommendations | **EXTENDABLE** | Post-action / heuristics engines (suggest-only) | Attach via existing hook; never invent |
| History | **MISSING** | Append-only learning rows, no version chain | **Omit** |
| Approval | **EXTENDABLE** | `approval_status` + `approvals` by `run_id` | Project when approval row/status exists |
| Diff | **MISSING** on outcome | Snapshots only in `workflow_compensation_records` for few HubSpot/Zendesk updates | Project only when real prior snapshot exists |
| Undo | **MISSING** on catalog | Hardcoded `COMPENSATABLE_FORWARD_ACTIONS` in `compensation_service.py` | **Catalog work required** (Phase 1–2) |
| Metadata | **PRESENT** | `metadata`, `schema_version`, `source`, `status` | Always project non-secret metadata |

---

## Lifecycle grounding (real triggers only)

| State | Real trigger today? | Ship as visible status? |
|-------|---------------------|-------------------------|
| Created | `finalize_execution_outcome` ran | **YES** — outcome exists |
| Verified | Connector verifiability / non-empty verified_output | **YES** — only when that check passed |
| Presented | Notification fanout or first DTO serve | **YES** — if notification emitted or presentation audit logged |
| Reviewed | Dedicated user-view event | **NO** — gap; do not show “Reviewed” until view events are logged |
| Approved | HITL `approval_status` / approvals row | **YES** — only when approval record exists |
| Edited | Governed update write completed after original | **NO** until edit path writes a linked outcome edge |
| Undone | Compensation run completed | **YES** — only when compensate API actually completed |
| Referenced | Another outcome/conversation points at this id | **NO** — gap |
| Archived | Archive disposition | **NO** — gap |

**Unshipped (honest gaps):** Reviewed, Edited, Referenced, Archived — not cosmetic labels.

---

## Catalog Diff / Undo readiness

| Capability | Status | Citation |
|------------|--------|----------|
| `ActionSpec` declares `compensatingAction` / undo counterpart | **MISSING** | `action_catalog/models.py` — kind/destructive/idempotent only |
| `catalog_write_authority` answers undo counterpart | **MISSING** | Write/read classification only |
| Hardcoded compensation map | **PRESENT (narrow)** | `compensation_service.py` HubSpot/Zendesk set |
| Diff from live prior vendor value | **PARTIAL** | Snapshot only for listed update actions |

**Phase 1–2 backend work (required before Diff/Undo sections ship):**

1. Add catalog property `compensating_action: str | None` (and optional `supports_diff: bool`) on `ActionSpec`.
2. Populate from current compensation map **into catalog definitions** (single source); `compensation_service` must read catalog, not a parallel frozenset.
3. Irreversible actions (e.g. `gmail.messages.send`) leave `compensating_action=None` → Undo section states that honestly.

---

## Identity for relationships

**PRESENT enough to start:** `run_id`, `entity_type`/`entity_id`, `org_id`, often `conversation_id` in metadata.  
**MISSING for Related/Dependencies:** parent/child outcome ids, explicit dependency edges on Module A.

---

## Phase 0 verdict

Safe to build **BusinessOutcome as a read-time projection** over Module A + run/steps/approvals joins for:

- Summary, Evidence (URLs), Verification (when real), Explanation, Metadata  
- Approval (when present), Timeline (when steps exist), Recommendations (suggest-only hook)

**Must not populate yet:** Impact, Related, Dependencies, History, Reviewed/Edited/Referenced/Archived lifecycle.

**Must build before Diff/Undo UI:** catalog `compensating_action` (promote off hardcoded map).

Next: Phase 1 projection + single GET shape for all consumers.
