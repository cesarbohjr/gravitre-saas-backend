# Vercel cost controls — 2026-10-29

## Applied

- The duplicate `web` project accepted `previewDeploymentsDisabled: true`. Its production deployment path is preserved; the project was not paused or deleted.
- Both projects accepted an ignored-build command that runs `apps/web/scripts/vercel-ignore-build.mjs` (or the same script relative to the app root). Older branches without the script continue building.
- The script compares VERCEL_GIT_PREVIOUS_SHA with VERCEL_GIT_COMMIT_SHA. Frontend changes, public app documentation, shared/unknown paths, root dependency/config files, and the backend provider-registry source build. Backend-only/internal docs/test changes skip. Unavailable history and force-pushed history build. GRAVITRE_FORCE_WEB_BUILD=1 forces a build.
- The dependency-free Git fixture test is wired into CI. Local execution passed; the CI step also passed in https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/40896669970. This does not claim the entire CI run is complete.
- Production deployment of 6b903f54f4dabb4ae6a556509bd5bc18db758597 reached READY with gravitre.app assigned: https://vercel.com/gravitre-ai/gravitre-saas-backend/GPAwW6BqamoMyW2xHt6NgSJbvPS3.

## Pending / not applied

- Full automatic-build shutdown of `web`: automatic approval review rejected an unconditional skip because it could stop production updates. The narrower preview-only change was accepted.
- Disabling elastic concurrency / restricting the build queue: Vercel returned a role/permission error; no successful change is claimed.
- Deployment-retention policy and v0 subscription review: the connector lacks the needed controls, and the dashboard browser is signed out.
- Shrinking the dev-only static-preview route's traced bundle needs a separate verified source change; no bundle-size reduction is claimed.

## Verification and rollback

This documentation-only commit also exercises the live ignored-build setting. Check its Vercel build log for `Skipping web build: no frontend build inputs changed.` before claiming the live skip was verified. Its intended behavior is to leave the previous successful production deployment serving.

To resume all frontend Git builds, clear the project's Ignored Build Step command. To restore duplicate preview builds, set `previewDeploymentsDisabled` to false on `web`. Production hosting, auth protection, runtime limits, and monitoring were not intentionally changed.
