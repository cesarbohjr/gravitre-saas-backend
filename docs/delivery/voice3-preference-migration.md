# Voice 3 preference migration — staged, DBA-only

The additive schema creates a journal and two invoker-rights maintenance functions.
Installing it does not migrate any agent. No application role, including service_role,
has permission to execute them. No production execution is authorized.

Scope is explicit per-agent preset_library voice_id substitutions only. A reviewed
manifest contains the exact before and after JSONB profile, agent UUID, tenant UUID
and exact release SHA. Do not normalize profiles: unknown fields and model, key,
language, sensitivity and personality are preserved. Custom source and tenant custom
registry matches are rejected. Key-only, implicit default, malformed and ambiguous
preferences stay untouched pending inventory and effective resolver mapping.
The SQL does not authenticate a quality manifest or establish acoustic identity;
a trusted DBA must independently verify the fully certified candidate mapping,
configured resolver overrides and explicit change approval before invoking it.
Never migrate from a proposed candidate list.

Apply is atomic, bounded to 500 rows, tenant-scoped, and idempotent for identical
batch replay. A conflicting request aborts the whole transaction. Rollback compares
the full after image and the applied row xmin; any intervening write refuses the
entire rollback rather than overwriting user changes. xmin is suitable only as a
short-window conservative fence, not durable across restore or wraparound. Keep
the original provider IDs and aliases available until rollback acceptance is proven.
Journal contains preference data; restrict access and define retention before release.
The custom registry SHARE lock blocks concurrent writes across tenants for the short
transaction: validate contention in isolated acceptance before rollout.

The new PostgreSQL workflow runs against throwaway tables only. Full deployed schema,
concurrent edits, production role grants, effective voice identity and browser picker
parity require separate acceptance. No migration gate is promoted by this change.
