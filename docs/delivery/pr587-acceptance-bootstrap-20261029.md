# PR587 acceptance database bootstrap checkpoint

Only `aadnwmjzrmbvadszroqt` (`gravitre-acceptance`) was changed. Production
database `smyeexlrqdpymwjmgzqu` was not changed.

Source: verified data-free baseline from migration-history-replay artifact
`12491251030`, run `39929148399`, SHA256
`bf66e05f4dc221f1d761e8965343ebd5bdbda43734dd26cd21f2f3b2d67c2617`.
The target was independently verified to have zero public tables and zero auth
users before initialization. No production rows or credentials were copied.

The connector rejected the full 805137-byte request with an expired request-state
error. The same baseline was split with sqlparse 0.5.5 at statement boundaries
into 29 ordered batches, each recorded through apply_migration as
`acceptance_verified_bf66_part_00` through `_28`. Each batch required the previous
batch's migration record. The first batch required an empty target. Dump session
settings were re-established per batch; schema/object definitions were preserved.
Initial default privileges withheld API grants until the later RLS/grant batches.

Verified after execution:

- 241 public tables, 241 with RLS enabled, zero tables without RLS.
- All 29 baseline migration records present; vector 0.8.0 dependency recorded.
- Canonical billing reference seed from repository migration
  `20260729120000_seed_all_billing_plans.sql` applied separately. This fixes the
  auth signup trigger's `org_billing_plan_code_fkey` failure on an empty baseline.
- No customer connector or external business action was created.

Security advisories from the inherited baseline are retained, not counted as
clean certification: 33 RLS-without-policy informational findings (deny by default),
35 mutable function search paths, vector in public, and exposure notices for the
intentional `auth_org_accessible(uuid)` RLS helper. That helper was inspected:
it checks `auth.uid()` membership and deployment region, and has an explicit
search path. Neither anon nor authenticated can CREATE in public. These
observations do not substitute for cross-tenant runtime certification.

The initial fixture bootstrap exposed a legacy Supabase list-users response
assumption and a swallowed auth error/fallback to a production smoke actor ID.
The acceptance bootstrap now resolves the actual test SA, creates it explicitly
through Auth Admin when absent, and propagates its actual ID to session minting.
Target-pinning tests pass locally. Fixture provisioning and full voice trials
must be verified from subsequent exact-head CI; neither is claimed here.

Inference remains blocked until an authorized acceptance provider is configured.
An attempted Railway relay deployment was rejected by automatic approval review
because it targeted the production environment. No relay was deployed.
