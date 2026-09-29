# Release integrity — Supabase Preview vs production (2026-09-24)

**Owner:** Cesar (release integrity). Not a product-design stop.

**SHA at discovery:** `a82d29b905235c5c5f2fe0413105be654d82c94d`

**Failed check:** GitHub App `Supabase Preview` — `Remote migration versions not found in local migrations directory.` Combined commit status remained **success**. Required GitHub Actions `CI` **succeeded**. Railway `/health` **succeeded**.

## Missing local version

Production `supabase_migrations.schema_migrations` contains `20260923194438` (`name=claim_pending_connector_write`, `created_by=cesar.bohorquez.jr@gmail.com`).

The repo already had the same idempotent `CREATE OR REPLACE FUNCTION public.claim_pending_connector_write` as `20260923193000_claim_pending_connector_write.sql`. Preview compared **version strings**, not function identity.

## Production schema vs application

`org_business_entities`, `org_business_entity_bindings`, and `org_entity_resolution_records` exist. Isolated org `f07e57c0-…` already has accepted Alpha company join `a1fa0000-…` with HubSpot/QBO/Zendesk **store** bindings. Application 3.0-H code expects those tables.

## Reconciliation (non-destructive)

- Record local file `20260923194438_claim_pending_connector_write.sql` matching the already-applied function.
- **Do not** re-run this function against production to “satisfy Preview.”
- Resolution criterion: Preview can see version `20260923194438` in the local migrations directory; production function remains `CREATE OR REPLACE` (no data rewrite).
