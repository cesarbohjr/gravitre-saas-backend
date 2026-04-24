# Configuration Hardening

## Risk identified
- Missing secrets can silently degrade behavior in production.
- No environment separation increases misconfiguration risk.

## Current state
- Critical keys are required, but some secrets default to empty strings.
- No explicit `APP_ENV` or production validation.

## Recommended fix
- Add `APP_ENV` for environment separation.
- Fail fast in non-dev environments when critical secrets are missing.

## Implementation details
- Added `APP_ENV` with default `dev`.
- Added settings validation to require:
  - `OPENAI_API_KEY` in staging/production
  - `CONNECTOR_SECRETS_ENCRYPTION_KEY` in staging/production
- Updated `.env.example` with `APP_ENV` and production notes.

## Future scaling notes
- Add a boot-time config audit endpoint (admin-only).
- Integrate secret validation into deployment pipelines.
