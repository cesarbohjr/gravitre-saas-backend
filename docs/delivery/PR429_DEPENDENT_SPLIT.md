# Draft #429 — dependent split plan (reviewability)

Parent draft: [#429](https://github.com/cesarbohjr/gravitre-saas-backend/pull/429). **Migrations unapplied; flags off** until each slice’s gates pass.

| Slice | Scope | Augments (cohesion) | Target |
|-------|--------|---------------------|--------|
| **A — Write safety** | Idempotency RPC, argument sealing, migration `100000`+`100001` | `tool_service`, approval scope | Merge first |
| **B — Release 1 auth** | `requireAuthenticatedOrg`, `/api/sessions` | Supabase route auth pattern | Merge after A or parallel |
| **C — Lifecycle UI** | `lifecycle-envelope.ts`, AI workspace merge | `conversation_state_service` envelope | Merge after B |
| **D — Queue + CI gates** | Redis/PG CI steps, queue poison | `workflow_queue` | With A |

**Migration prerequisites**

1. `20261014100000_write_invoke_idempotency.sql` — table, RPCs, REVOKE (no service_role GRANT in-file).
2. `20261014100001_write_invoke_idempotency_grants.sql` — **requires (1)**; GRANT EXECUTE/TABLE to `service_role` only.

**Not split yet:** voice ROI panel wiring, Freshservice prod proof, MSP product — separate tracks when matrix rows unblock.
