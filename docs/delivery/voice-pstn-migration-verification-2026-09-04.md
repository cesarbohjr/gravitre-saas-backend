# Voice PSTN migration verification (2026-09-04)

## Migration applicability

- `public.voice_pstn_sessions` exists in production and is required by:
  - `backend/app/routers/voice_gateway.py`
  - `backend/app/services/voice_gateway_service.py`
  - `backend/app/services/pstn_voice_bridge.py`

## Migration execution evidence

- Applied migration via Supabase MCP (`apply_migration`) with name `voice_pstn_sessions`.
- Migration history now contains entries:
  - `supabase_migrations.schema_migrations.version = 20260904054015` (`name = voice_pstn_sessions`)
  - `supabase_migrations.schema_migrations.version = 20260904053833` (`name = voice_pstn_sessions`)
- Table presence check:
  - `checked_at_utc = 2026-09-04 05:41:21.17822+00`
  - `to_regclass('public.voice_pstn_sessions') = voice_pstn_sessions`

## Test evidence

- Command:
  - `PYTHONPATH=backend python -m pytest backend/tests/services/test_voice_gateway_service.py backend/tests/services/test_voice_pstn_policy.py backend/tests/services/test_pstn_voice_bridge.py -q`
- Result:
  - `9 passed in 4.00s`

## Deploy state

- Health check:
  - `GET https://api.gravitre.app/health`
  - `status = 200`
  - `git_sha = 45d8affae97a374b0444655143938a815b9e2f1f`
  - `timestamp = 2026-09-04T05:41:27.681754+00:00`
