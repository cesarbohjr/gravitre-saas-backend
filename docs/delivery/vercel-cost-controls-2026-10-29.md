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
- Dashboard inspection later succeeded. `web` preview retention was reduced from 30 days to two weeks. Its production retention stays 30 days. The production-serving project already had one-day canceled/errored/preview retention and one-week production retention; these were left unchanged.
- v0 Business was $100/user/month, with no usage events in the Oct 11–Nov 11 cycle. Auto-renewal was turned off: Business remains through Nov 11, then Free. Automatic credit recharge was also turned off; no new $40 top-ups. Current credits were not spent or deleted.

## Production bundle optimization

Normal production builds now compile out the development-only static-preview filesystem handler. Explicit E2E builds retain it via a build-time boolean, without exposing credentials. The wrapper preserves the production 404 response.

Local verification: production build completed successfully; route trace changed from 4,077 files / 41,144,251 bytes to 176 files / 1,934,836 bytes (traced inputs, not compressed deployment bytes). Three Vitest checks passed: normal-production 404, explicit E2E extension manifest delivery, and directory traversal rejection. Targeted ESLint passed. Production deployment verification is required separately; this local comparison does not claim an invoice saving.

## Verification and rollback

Live skip verification succeeded for documentation commit 2ebe60d75f07b52768039bb9b999d9d47872b0a0: both Vercel logs report `Skipping web build: no frontend build inputs changed.` and cancellation by ignored-step exit code 0. Evidence: production-serving project https://vercel.com/gravitre-ai/gravitre-saas-backend/5raBDWJc3ov4UPpe5zSut1Daa7zS and duplicate https://vercel.com/gravitre-ai/web/GNAQ2mHPxtUjJ2AB8FjGzqExHxiB. The previous successful production deployment continued serving (home and login HTTP 200; dev-only route HTTP 404).

To resume all frontend Git builds, clear the project's Ignored Build Step command. To restore duplicate preview builds, set `previewDeploymentsDisabled` to false on `web`. Production hosting, auth protection, runtime limits, and monitoring were not intentionally changed.
