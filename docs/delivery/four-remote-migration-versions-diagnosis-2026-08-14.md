# Four remote-only migration versions — diagnosis only (2026-08-14)

**Constraint honored:** No `migration repair`, no `db pull`, no Dashboard DDL, no history rewrite.

**Project:** `smyeexlrqdpymwjmgzqu`  
**Method:** Read-only `supabase_migrations.schema_migrations` + `information_schema` probes (same discipline as `docs/delivery/supabase-migration-history-drift-diagnosis.md`).

## Verdict

These four remote versions are **real, legitimate applies** of known repo migrations, recorded under **wall-clock version IDs** (Dashboard/CLI live apply), **not** mystery orphans and **not** a second schema track.

| Remote version | Remote `name` | `created_by` | Local twin (different stamp) | Live schema probe |
| -- | -- | -- | -- | -- |
| `20260811175745` | `knowledge_sources_license_metadata` | cesar.bohorquez.jr@gmail.com | `20260811210000_knowledge_sources_license_metadata.sql` | `knowledge_sources.license` **present** |
| `20260811202051` | `knowledge_sources_wave2_metadata` | cesar.bohorquez.jr@gmail.com | `20260811220000_knowledge_sources_wave2_metadata.sql` | `knowledge_sources.licence_verified` **present** |
| `20260813092023` | `cognitive_turn_kernel` | cesar.bohorquez.jr@gmail.com | `20260813120000_cognitive_turn_kernel.sql` | `cognitive_turn_traces` **exists** |
| `20260813093326` | `org_entity_relationships_archived_at` | cesar.bohorquez.jr@gmail.com | `20260813140000_org_entity_relationships_archived_at.sql` | `org_entity_relationships.archived_at` **present** |

Statement prefixes on remote match local file headers 1:1 (license granularity; wave2 metadata; CognitiveTurnKernel tables; soft-archive `archived_at`).

## Class of drift

Same class already diagnosed 2026-08-11: remote history stamped with apply-time IDs while the repo keeps rounded `…120000` / `…140000` filenames. CLI `db push` then fails with “Remote migration versions not found in local migrations directory” until local filenames (or history bookkeeping) are aligned — **without** implying prod is missing those four changes.

## Not these versions

Part 1 nullable `agent_memories.agent_id` (`20260813170000_workspace_memory_nullable_agent.sql`) is a **separate** gap: probe shows `agent_id` still **NOT NULL** on prod. Do not conflate unblocking `db push` for these four with applying that later migration.

## Safe next steps (not executed)

1. **Option D-style rename** of the four local files to the remote wall-clock versions (after confirming no duplicate local version collision), **or**
2. Leave history alone and apply only forward idempotent SQL for true gaps (e.g. nullable `agent_id`) via an explicit Cesar-named choice.

**Do not** `repair --status reverted` on these four remote rows — that would falsely deny real applies.
