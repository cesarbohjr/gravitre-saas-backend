# PR605 Gate 14 — runtime route artifact reconciliation and exact-head certification
Date 2026-11-05. Read-only evidence from GitHub Actions; no production mutation.

## Source-backed route inventory result and identified defect
- Main CI [42094961866](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42094961866) at `4e1dcc59b48ae66b5af52c2bae0ef660234839a4`: route inventory step **FAILED**, report artifact `13447667155` uploaded and inspected.
- Runtime inventory artifact **successfully resolved all 134 nested router wrappers**: `registered_routes=1035`, `unresolved_wrappers=0`, `import_edges=8707`, generated OpenAPI `paths=877`. These values are *registered route and static import counts*, not active production caller/traffic counts.
- Cross-check revealed **12 OpenAPI paths absent from reconstructed inventory**. They are five enterprise insights routes, five marketplace certification/outcome blueprint routes, and two operator recommendation/confirmation routes. Source trace:
  - `backend/app/routers/enterprise.py` defines router prefix `/api/enterprise` and includes insights child router with local `/insights` prefix;
  - `backend/app/routers/marketplace.py` defines `/api/marketplace` and includes certification child routes whose local paths begin `/assets` or `/outcome-pack-blueprints`;
  - `backend/app/operators/router.py` defines `/api/operators` and includes governed recommendation child routes with local `/{operator_type}` paths.
- The exporter was preserving each child route's local path but omitting the parent prefix. **This is an inventory-tool graph reconstruction defect**, not evidence that production routes are missing: the same generated OpenAPI includes all 12.
- Repair committed `f4c43ef3712f16a6ce804b937e35bf17374f8f6a`: inherit `original_router.prefix` across nested router containers, prepend only when the route path does not already contain the prefix. Retain strict OpenAPI parity assertion. Exact-head CI rerun and artifact inspection are required before certification.

## PostgreSQL status contract independent evidence
- Independent isolated PostgreSQL certification [42094961780](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42094961780) passed **12 PostgreSQL tests and 14 focused application mapping tests**, with no skips in those scopes, at SHA `4e1dcc59b48ae66b5af52c2bae0ef660234839a4`.
- The later documentation and route-exporter code changes do not change the migration, but **exact-head full CI still must pass** and the independent check should be rerun or verified unchanged on the final release SHA.
- Main CI PostgreSQL test step in run 42094961866 was **skipped** due to the earlier route-export failure. The independent pass does not count as an integrated full-CI pass.

## Other release blockers
- Latest main CI against the latest PR SHA and Lighthouse check must both pass; a prior Lighthouse homepage performance score 0.74 failed 0.75 threshold.
- All historical records remain untouched. The controlled reconciliation plan is documented in `docs/delivery/pr605-gate-12-certification-and-reconciliation-approval.md`; production DB identity attestation and row-level authorization remain mandatory.
- The inventory currently traces route handlers, DI dependencies and bounded static import edges. It **does not** certify every dynamic call target, UI caller, database event subscriber or production traffic edge. Preserve separate evidence labels.

## New findings
- ECO-069 P0: nested router parent prefixes omitted from runtime inventory; exact-head exporter correction and OpenAPI parity test required.
- ECO-070 P1: distinguish mounted API route enumeration from actual production traffic/caller coverage; do not claim the latter based on 1035 route records.
- ECO-071 P0: maintain independent PostgreSQL pass while preventing skipped integrated gate from being counted as successful.
