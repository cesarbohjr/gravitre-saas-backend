# Voice branch browser repairs — 2026-11-26

Base: PR #610 at `57b92b7ab4e92834cf02ca6d1f19420946dd276d`.

## Hosted evidence

[Independent CI run 45774925001](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45774925001) completed backend, web, shared text/voice, dependency audit and integration smoke successfully. Billing E2E was cancelled at its timeout; this is not a passing browser suite. Its [job log](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45774925001/job/139784535331) confirms Home's single submission/single compact runtime case and all five retained header cases passed.

Master PR #611 remains at `499e0db2dfb29e2ae08ea6ce1b9243958f85639a`; all ten workflow conclusions were rechecked as success, including [Core](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45734741169) and [QA12](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45734741065). This is independent master evidence, not evidence for Voice changes.

## Confirmed repairs

1. Connectors' list case queried an obsolete `data-gravitre-connector-row`. The actual default surface uses the accessible Connected systems table. Assert default list visibility and exactly one visible row each for fixture HubSpot, Salesforce and Slack. This replaces an implementation-specific selector with stronger semantic assertions, without removing coverage.
2. `/e2e/shots/ai` reproduced with visible composer but `canonicalPresentation=minimized`, rather than fullscreen. The fixture auto-summon ran before root authentication finished; the outer gate closed the shared provider. Expose root-auth readiness inside the fixture and defer its auto-summon until ready. Production auth gate/provider are unchanged. A unit regression checks no summon during loading and summon after readiness.

## Local validation

- Chromium, retries=0: before fixture timing repair, 7 passed / 1 failed (fullscreen expected, minimized received). After repair: **8 passed in 37.3 seconds**: Home, five headers, Agents/Connectors, and AI query params.
- Vitest: **16 passed**, fixture host boundary and authentication gate suites.
- TypeScript `tsc --noEmit`: passed.
- `git diff --check`: passed.

Browser command: `playwright test -c playwright.local.config.ts e2e/canonical-ai-workspace.spec.ts --retries=0 --grep 'Agents hub|shots /ai|Home prompt|header Ask'`.
Local-only configuration uses Chromium from @sparticuz/chromium, explicit loopback Next binding, and video disabled. Synthetic shot fixtures and mocked chat transport; no live provider acceptance. An intermediate run lost its web server during concurrent TypeScript compilation and was inconclusive; the final browser run ran separately after TypeScript completed. No CI workflow was changed.

## Remaining gates

Current publication requires new hosted verification. Navigation crawler's SSO 403 and obsolete marketing scene expectations remain unresolved; this patch does not certify them or the full browser suite. Controlled integration remains pending. No merge, production deployment, migration, provider mutation or finding certification. Newly certified findings: **0**.
