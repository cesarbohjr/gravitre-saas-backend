# MSP parent RLS — deferred (audit 2026-10-14)

Migration `20261014110000_msp_auth_org_accessible_parent.sql` was **removed** from PR #429.

**Reason:** Extending `auth_org_accessible` for parent-org members is not gated by `MSP_PARENT_ORG_ENABLED`. Application false does not disable database access once parent links exist.

**Before any RLS change:**

1. Named product authorization model (roles, link management, audit).
2. Consistent Python dependencies (`require_org_member` vs generic reads).
3. Two-client isolation tests and direct REST behavior review.

Keep **`MSP_PARENT_ORG_ENABLED=false`** until the above ships.
