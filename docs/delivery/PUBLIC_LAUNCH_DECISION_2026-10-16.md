# Gravitre public launch — 2026-10-16

## Launch decision
**PUBLICLY AVAILABLE / GLOBAL ACCESS — GO**, on owner instruction "fix the issues and then launch."

The public marketing website at https://gravitre.app, pricing page at https://gravitre.app/pricing, and self-service account registration at https://gravitre.app/get-started are accessible without a regional or invite-only entry gate. No environment flag, database authorization policy, or billing control was bypassed or changed for this announcement.

## Verified release evidence
- Full CI: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/39005844074 — success: backend pytest, shared runtime, web build, dependency audit, integration smoke.
- Release 1 production smoke: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/39009930016 — PASS, zero failures, backend runtime SHA aligned. Fixed false-positive arising from test-only backend edit in PR #490.
- Public MCP and SSRF: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/38994473914 — PASS.
- Live chat/voice revocation: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/39002628381 — PASS (text-ingress voice session).
- Release 1 owner sign-off: docs/delivery/RELEASE1_OWNER_SIGNOFF_2026-10-16.md.

## Scope and conditions
- **Global access** refers to the website and publicly displayed self-registration path. It does *not* certify every OAuth flow, country-specific payments/tax eligibility, email confirmation or billing transaction.
- **Billing E2E (Playwright) was skipped** on the green full CI run; paid checkout is therefore not certified by this release entry. Keep billing controls and approval gates enabled.
- This file is a release decision record, not evidence of a promotional campaign, successful account creation, or a transaction.

## Immediate operational follow-up
Run a genuine sandbox-mode-to-production-safe signup and paid-checkout E2E, verify taxes and customer support routing by region, and monitor production errors and onboarding conversions. Any failing path should be addressed without weakening tenant isolation, approval enforcement or rate limiting.
