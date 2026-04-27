# Legacy Migrations

These migrations were moved out of the primary migration path to reduce restart
confusion and avoid schema drift for the current frontend contract + cohesive
demo data flow.

Do not include these in standard recovery runs.

Use:

- `supabase/scripts/README_recovery_order.md`

for the active migration order.
