# I8 — Models + Model Studio

**Date:** 2026-09-16  
**Status:** SHIPPED (code)  
**Depends on:** I1 shell (Training already off hub tabs)

## Delivered

### Models (`/models`)
- Business catalog cards: purpose, business status, where used, performance, learning sources, last updated, recommended next step
- Technical view toggle: architecture, base, dataset id, version — no invented hyperparameters/drift/logs
- Usage topology (deployed vs registered only)
- Create CTA routes to Model Studio; `?action=register&intent=` still opens the real register dialog
- Training called out as folded into Studio

### Model Studio
- Segments: Create · Train · Evaluate · Deploy · Runs
- Intent-first Create: Predict outcome · Classify/score · Detect anomaly · Forecast · Improve agent · Advanced/custom
- Train/Runs read live `trainingApi` datasets/jobs (same `/training` system)
- Evaluate/Deploy list live registry models

## Verification

- Local: model-catalog vitest (this ship)
- [ ] Prod: Models business view + Studio intent → register after Railway deploy

## Not in scope (I9)

Reports rebuild.
