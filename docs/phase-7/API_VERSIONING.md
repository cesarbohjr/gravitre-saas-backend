# Phase 7: API Versioning Layer

## Current Architectural Limitation
- No stable versioning mechanism for public API routes.
- Future changes risk breaking existing clients.

## Target Architecture
- Support `/api/v1/*` without breaking existing `/api/*` routes.
- Allow version selection via headers.
- Echo resolved version in response headers.

## Minimal Implementation Plan
- Add middleware to normalize `/api/v1/*` to `/api/*` internally.
- Accept version headers (`X-Api-Version` or `Accept-Version`).
- Reject unsupported versions or header/path mismatches with 400.
- Set `x-api-version` on API responses.

## Required Migrations
- None.

## Integration Changes
- Middleware added in `backend/app/main.py`.
- CORS headers allow `X-Api-Version` and `Accept-Version`.
- Legacy `/api/*` remains valid (defaults to v1).

## Risks
- Middleware must preserve routing for non-API paths.
- Clients sending mismatched version headers will receive 400.

## Future Scaling Notes
- Add per-version docs and changelog.
- Implement explicit deprecation policies and sunset headers.
