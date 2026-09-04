# WorkObject verification (2026-09-03)

## Pre-flight (mandatory)

- Branch synced to `main`.
- CI baseline check showed `main` not fully green at start.
- Standing battery rerun (local invocation of workflow-equivalent scripts):
  - `scripts/verify-pending-reply-classifier-live.py` -> PASS, artifact `docs/delivery/pending-reply-classifier-live.json`
  - `scripts/verify-conversational-path-live.py` -> PARTIAL/FAIL exit (live behavior regressions)
  - `scripts/verify-unified-turn-phase2-live.py` -> FAIL exit
  - `scripts/verify-unified-turn-persona-drift-live.py` -> PASS
  - `scripts/verify-unified-turn-prompt-injection-live.py` -> progressed past unpack bug after fix; still unauthorized in this environment (401)

## WorkObject lifecycle live proof

- Migration applied to active Supabase project (`smyeexlrqdpymwjmgzqu`) for:
  - `work_objects`
  - `work_object_events`
- Live lifecycle probe:
  - Script: `python scripts/verify-work-object-lifecycle-live.py`
  - Artifact: `docs/delivery/work-object-lifecycle-live.json`
  - Recorded at: `2026-09-04T05:24:09.934142+00:00`
  - Result: `pass: true`
  - Evidence:
    - one WorkObject (`6e320395-72ba-4ecb-8413-c9e74f2b4a7f`)
    - 3 attributed events
    - 2 distinct consequential actions (`gmail.messages.batch`, `gmail.messages.send`)
    - 3 calendar days (`2026-07-24`, `2026-07-25`, `2026-07-26`)

## Live DB evidence pointers

- Supabase SQL verification query timestamp:
  - `checked_at_utc = 2026-09-04 05:28:01.807023+00`
  - `work_object_count = 2`
  - `work_object_event_count = 38`
- Latest object sample includes:
  - `id = 6e320395-72ba-4ecb-8413-c9e74f2b4a7f`
  - `object_type = objective`
  - `status = failed`
  - `last_activity_at = 2026-09-04 05:24:09.56087+00`

## Connector SOURCE/ACTION/DESTINATION coverage

- Script: `python scripts/report-source-action-destination-coverage.py`
- Artifact: `docs/delivery/connector-source-action-destination-coverage.json`
- Coverage snapshot:
  - `vendorCount = 84`
  - `sourceCount = 83` (`98.81%`)
  - `actionCount = 83` (`98.81%`)
  - `destinationCount = 14` (`16.67%`)

## Deploy state

- Backend health check:
  - `GET https://api.gravitre.app/health`
  - observed `git_sha = 45d8affae97a374b0444655143938a815b9e2f1f`
- Railway production run for the WorkObject feature commit succeeded:
  - GitHub Actions run `33839874774` (`Railway backend production`, success).
