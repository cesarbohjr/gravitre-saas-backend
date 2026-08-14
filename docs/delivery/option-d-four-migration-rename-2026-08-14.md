# Option D rename resolution — four remote wall-clock versions (2026-08-14)

**Choice:** Cesar confirmed Option D-style rename only (no `migration repair`, no Dashboard SQL).

## Renames performed

| Old local filename | New local filename (= remote version) |
| -- | -- |
| `20260811210000_knowledge_sources_license_metadata.sql` | `20260811175745_knowledge_sources_license_metadata.sql` |
| `20260811220000_knowledge_sources_wave2_metadata.sql` | `20260811202051_knowledge_sources_wave2_metadata.sql` |
| `20260813120000_cognitive_turn_kernel.sql` | `20260813092023_cognitive_turn_kernel.sql` |
| `20260813140000_org_entity_relationships_archived_at.sql` | `20260813093326_org_entity_relationships_archived_at.sql` |

## Post-rename (before push of pending locals)

| Metric | Value |
| -- | -- |
| Remote-only | **0** (the four blockers gone) |
| Local-only | **3** — `20260813150000`, `20260813160000`, `20260813170000` |
| `db push --dry-run` | Clean (no remote-missing error); would push the three Part 1 pending files |

## After authorized follow-on push (nullable + siblings)

`supabase db push --linked` applied:

- `20260813150000_cognitive_phase_d_aliases.sql`
- `20260813160000_part1_dept_memory_investigators.sql`
- `20260813170000_workspace_memory_nullable_agent.sql`

| Metric | Value |
| -- | -- |
| Both local+remote | **201** |
| Local-only | **0** |
| Remote-only | **0** |
| `db push --dry-run` | **Remote database is up to date.** |
| `agent_memories.agent_id` nullable | **YES** (live probe) |

Artifacts: `_migration_list_after_option_d_rename.txt`, `_db_push_dry_run_after_option_d_rename.txt`, `_migration_list_post_push.txt`, `_db_push_dry_run_post_push.txt`.
