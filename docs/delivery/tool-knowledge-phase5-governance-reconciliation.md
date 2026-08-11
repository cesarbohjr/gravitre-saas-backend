# Tool Knowledge — Phase 5 governance reconciliation (2026-08-11)

## Decision (no second system)

The proposal’s per-capability tiers (READ=LOW … REFUND/DELETE=CRITICAL) map onto the **existing** ActionSpec model that already drives `catalog_write_authority`:

| Proposal intent | Existing catalog fields |
| -- | -- |
| READ / LOW | `kind=read`, `destructive=false`, `requires_approval=false` |
| CREATE task / LOW–MEDIUM | `kind=write`, often `destructive=true` (mutating default) |
| UPDATE contact / MEDIUM | `kind=write` + scopes `*:write` |
| SEND marketing email / HIGH | `kind=write` or `advanced`, `destructive=true`, often `requires_approval=true` |
| DELETE / refund / budget increase / CRITICAL | `destructive=true` + `requires_approval=true` (and/or advanced tier) |

**Do not build** a parallel LOW/MEDIUM/HIGH/CRITICAL enum. Enforcement stays in:

- `backend/app/services/catalog_write_authority.py`
- ActionSpec `kind` / `destructive` / `requires_approval` / scopes
- CI lint: `backend/tests/connectors/test_action_schema_standard_lint.py`

## Optional future extension (report only — not built)

If product needs finer UX labels than read/write/destructive, propose a **derived display mapping** from existing fields (e.g. `approval_tier_label`) without introducing a second authority gate. That would be an explicit follow-up decision, not silent dual governance.
