# Gravitre 3.0-H — cross-system entities on ExecutionPlan (2026-09-21)

**Status (2026-09-24):** NL store-backed join answers + diagnostic plan stamp on the shared runtime. Live unique Alpha bind remains store-backed (synthetic QBO/Zendesk ids). **Not** a live multi-provider OAuth PASS. No fuzzy STA-312 person joins. Frontend contract: `gravitre-3.0-h-frontend-contract.md`.

## Original 3.0-H requirements

From `docs/ai/GRAVITRE_PLATFORM_EXECUTION_3.0.md`: BusinessEntity bindings; CS-13; STA-312 owner; no silent merge; gate = join tests + live. Spec §M: bindings + evidence + confidence; Memory HMAC exact.

## 2026-09-24 product behavior

- Natural-language “across HubSpot / QuickBooks / Zendesk” answers load `org_business_entities` for the tenant only.
- Ambiguous display names stay unjoined.
- Disconnected live vendors are disclosed; metrics are not mixed.
- Diagnostic parallel READ stamps `entity_id` when an accepted join exists.
- Person joins remain email-only (`join_provider_bindings`).


Cesar authorized 3.0 after deferring remaining 2.0 human tests to the end. This phase does not start 3.0-C lane B production, a second worker, or fuzzy STA-312 person joins.

## What shipped

| Piece | Behavior |
|-------|----------|
| `ExecutionPlan.entity_id` | Survives `as_dict` / `from_dict` and is stamped from accepted BusinessEntity |
| `stamp_entity_on_execution_plan` | Tenant `expected_org_id` must match; foreign org → no entity id, no silent merge |
| `join_provider_bindings` `left_org_id` / `right_org_id` | `refused_cross_org` when a binding is from another tenant |
| Isolated Alpha | Stable id `a1fa0000-1501-4000-8000-c04e57a00001` on isolated org only |

## Gate

- UNIT_TEST: `test_platform_execution_3_0_h_entities.py`
- LIVE unique bind: **PASS** — `org_business_entities` `78e5c0d2-…` canonical `a1fa0000-…` isolated org; join `joined`; foreign org `refused_cross_org`; plan `entity_id` stamped. Evidence `gravitre-3.0-closeout-live.json` @ Railway `7a2eaaab` 2026-09-21T21:25Z. Provider OAuth for QBO/Zendesk still not connected (synthetic bindings).
- WRITE: not invoked
