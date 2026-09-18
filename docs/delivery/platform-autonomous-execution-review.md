# Platform Autonomous Execution Review

**Status:** IN PROGRESS — audit-only (no connector fixes in this pass)  
**Date:** 2026-09-17  
**Scope:** End-to-end audit of Gravitre's ability to reliably plan, parameterize, govern, and execute connector actions in autonomous chat and workflow paths.

---

## Purpose

This review answers whether Gravitre can **actually execute** the business tasks it advertises — not merely whether connectors exist in the catalog or show as "connected." Recurring parameter and validation failures may indicate problems beyond intent/resource resolution; this review audits the full connector → capability → action → execution stack.

**Do not treat "connector exists" as synonymous with "connector can reliably execute supported business tasks."**

---

## Review sections

| Section | Document | Status |
|---------|----------|--------|
| **Manus-like autonomous business execution (full platform)** | [gravitre-autonomous-business-execution-audit-2026-09.md](./gravitre-autonomous-business-execution-audit-2026-09.md) | **Complete (audit-only)** |
| **Connector action wiring & capability completeness** | [connector-action-wiring-audit.md](./connector-action-wiring-audit.md) | **Complete (audit-only)** |
| Parameter ledger / Module B turn controller | [module-b-architecture-reference.md](./module-b-architecture-reference.md) | Reference (prior audits) |
| Connector catalog implementation matrix | [connector-catalog-audit-latest.json](./connector-catalog-audit-latest.json) | Regenerated 2026-09-17 |
| Connector action health matrix (machine-readable) | [connector-action-health-matrix.json](./connector-action-health-matrix.json) | Generated 2026-09-17 |
| STA-303 error code taxonomy | [sta303-connector-error-codes-audit.md](./sta303-connector-error-codes-audit.md) | Reference |
| HubSpot search schema dead-end (exemplar) | [hubspot-search-validation-dead-end.md](./hubspot-search-validation-dead-end.md) | Live-proven class |
| Connector certification states (Section R) | [connector-certification-states.md](./connector-certification-states.md) | **Process only (2026-09-17)** — no code / no customer badge |
| **Re-audit 2.0 (post E1–E5/F1)** | [gravitre-autonomous-execution-reaudit-2.0.md](./gravitre-autonomous-execution-reaudit-2.0.md) | **AUDIT ONLY (2026-09-18)** — code + `/health`; not LIVE_USER_PROVEN |

---

## Executive summary (connector actions)

| Metric | Value | Source |
|--------|------:|--------|
| Catalog vendors | 85 | `vendor_definitions.py` |
| Catalog actions | 732 | `connector-catalog-audit-latest.json` |
| Registry-implemented | 730 (99.7%) | audit script 2026-09-17 |
| Catalog-only ("ghost") | 2 | `webhook.connectors.get`, `webhook.post.replay` |
| Verified working (tests) | 482 | audit JSON |
| Implemented but unverified | 248 | audit JSON |
| Canonical capabilities | 9 | `capability_ontology/registry.py` |
| Resource resolver adapters | 8 vendors + GA4 special-case | `connector_resource_adapters.py` |
| Registry violations | 0 | audit JSON |

**Headline finding:** Catalog/registry wiring is **strong** (730/732 implemented, 0 registry violations). The recurring user-visible parameter failures are **not primarily** "missing handlers." They cluster in **schema disagreement across layers**, **ReAct-first paths that skip governed preflight**, **sparse resource/parameter source contracts**, and **capability ontology too thin to route business intents without model tool-name memory**.

**Recommended future architecture (audit conclusion — not implemented):**

1. **Strengthen existing action registry** — single canonical schema per action (merge JSON Schema + workflow schema + executor guards).
2. **Introduce action preflight** — unified gate before every provider invocation (resource → params → scopes → constraints → governance).
3. **Strengthen capability/action mappings** — expand ontology + recipes; encode cross-connector substitutes (e.g. GA4 + GSC for website performance).
4. **Standardize parameter compilation** — explicit `ParameterSourceRule` per required field on `ActionSpec`; ledger consumes rules, not ad hoc extraction.
5. **Repair specific adapters** — targeted fixes where live evidence shows schema/executor mismatch (HubSpot search class is the template).
6. **Do not** create a parallel connector subsystem — extend `action_catalog`, `connector_execution_matrix`, `action_selection_gate`, and `connector_availability_service`.

---

## Platform invariants evaluated (K–R)

See [connector-action-wiring-audit.md § U](./connector-action-wiring-audit.md#u-platform-invariants-to-evaluate) for full PASS/FAIL/PARTIAL per invariant.

| Invariant | Verdict |
|-----------|---------|
| K. Every advertised capability → executable action or explicit unavailable | **PARTIAL** — 9 capabilities covered; 723 actions have no capability mapping |
| L. Every action → one canonical schema | **FAIL** — JSON Schema, workflow schema, and executor guards can disagree |
| M. Every required param → explicit source strategy | **FAIL** — ledger source ranks exist; no per-field source registry |
| N. Every action → preflight before provider invoke | **FAIL** — ReAct-first fresh intents skip governed preflight |
| O. Every executable action → Observation tied to plan_id/step_id | **PARTIAL** — audit events yes; structured Observation object not uniform |
| P. Provider limitations → structured metadata | **FAIL** — mostly discovered at runtime (GA4 combos, HubSpot filter rules) |
| Q. Future connector → no cognitive-core special cases | **PARTIAL** — SDK/MCP paths exist; NL mapper still has vendor `_extract_args` fallbacks |
| R. "Connected" ≠ all actions available | **PARTIAL** — `evaluate_connector_availability(action_key=…)` exists but not always consulted pre-plan |

---

## Root-cause question (Section T summary)

Recurring parameter failures are **primarily a combination** (not a single cause):

| Failure class | Approx. contribution | Evidence |
|---------------|---------------------:|----------|
| 5. Incorrectly wired action schemas | **~30%** | HubSpot search class: 4/4 failures deterministic on `deals.search` vs 8/8 success on `deals.list` — `hubspot-deals-search-validation-probe.json` |
| 8. Missing preflight validation | **~25%** | Fresh single-connector intents → ReAct without `should_run_connector_preflight` — `connector_chat_routing.py` |
| 4. Parameter compilation failure | **~20%** | Dual schema paths; workflow gate ≠ ReAct JSON Schema — `action_selection_gate.py` vs `action_parameters.py` |
| 9. Tool-selection mismatch | **~15%** | Same user ask → different tools (`deals.list` vs `deals.search`) — probe JSON |
| 3. Resource resolution failure | **~10%** | 77/85 vendors return `resolver_not_implemented`; GA4/GSC need linked property/site |
| 7. Provider constraint handling | **~10%** | GA4 dimension/metric incompatibilities not encoded structurally |
| 2. Capability routing failure | **~5%** | 9 capabilities vs 732 actions; no GSC binding for `analytics.traffic_overview` |
| 6. Incomplete connector actions | **~2%** | Only 2 catalog-only actions |
| 1. Reasoning failure | **~3%** | Residual after structural fixes |
| 10. Execution adapter defects | **~5%** | `catalog_http` generic executors — unverified for edge params |
| 11. Combination | **Dominant** | Layers interact: wrong tool + wrong schema + no preflight = user-visible "invalid parameters" |

---

## Next steps (post-audit — not in this pass)

1. Approve architecture direction (single schema + preflight + parameter source rules).
2. Prioritize P0 actions from health matrix (schema/executor disagreement on high-traffic reads).
3. Expand capability ontology for marketing/analytics business asks (traffic, GSC, campaigns).
4. Add `CAN_THIS_ACTION_EXECUTE_NOW` check to planner/tool router before tool_choice. **Shipped 2026-09-17** — `app/services/action_execute_now.py`; wired in `narrow_tools_for_turn`, `embed_narrow_tools_for_turn`, `narrow_permitted_tools_for_capability`. Cheap snapshot only (no per-tool `force_live`). See `docs/ai/PHASE_EXECUTE_NOW.md`.
5. Define connector certification states (Section R) as product/process — not code yet. **Documented 2026-09-17** — [connector-certification-states.md](./connector-certification-states.md). Internal Track A/B/C only; no customer Certified/TRAINED badge, no schema, no Enable toggle.
