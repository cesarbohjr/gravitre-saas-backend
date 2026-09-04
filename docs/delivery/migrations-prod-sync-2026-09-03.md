# Supabase migrations — prod sync confirmation

**Date:** 2026-09-03 · **Method:** `supabase db push --linked` + schema probes

## Result: all local migrations applied

```
Remote database is up to date.
```

Latest local/remote pairs (CLI `migration list`):

| Version | Name |
|---|---|
| `20260903100000` | `rag_chunks_fts` |
| `20260903120000` | `memory_hardening_temporal` |
| `20260903140000` | `agent_identity_iam` |

## Schema verification (prod `smyeexlrqdpymwjmgzqu`)

- `agent_memories`: `memory_key`, `is_current`, `source_class`, `structured_payload` present
- `agent_memory_history` exists
- `agent_identity_records`, `agent_delegation_grants` exist

No pending migrations to apply.

## Re-check (2026-09-04 — Agent ROI closeout)

`supabase db push --linked --dry-run` → **Remote database is up to date.**

Agent ROI (`a78ef32d`) uses existing `model_calls` / `agent_jobs` / `intelligence_outcome_events` — **no new migration required**.
