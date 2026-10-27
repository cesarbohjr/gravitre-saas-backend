# PR #580 — Anthropic live certification gate

Status: **BLOCKED / NOT_CERTIFIED** until actual provider-backed evidence is captured. This document is a test plan, not a test receipt.

## Preconditions
- Confirm the deployed backend resolves `ANTHROPIC_API_KEY` and its preferred provider/model routing without exposing secret values.
- Verify a real authenticated Anthropic inference request from the deployed service, recording timestamp, deployment SHA, request correlation ID, provider/model identity, status and sanitized outcome.
- A configured environment-variable name or healthy Railway deployment is **not** a successful inference test.

## Fixtures
- Use an authorized isolated smoke tenant with installed Customer Rescue and Process Drift Plays and ready-to-act workflow dependencies.
- Supply authorized ticketing connector and readback fixtures; preserve tenant isolation, approvals, idempotency and verified-write requirements.

## Certification
- Execute all 56 capability/surface cells with distinct live cases; do not promote the 168 offline probes to live evidence.
- For each case capture provider-backed decision provenance, bounded intelligence envelope, downstream workflow/Play execution, external readback and outcome.
- Verify independent model-backed review, no false 100% confidence, unavailable confidence recorded as null, and explicit provider outage/fallback behavior.
- Reject duplicate conversations, stale evidence, missing artifacts and unsafe writes.
- Run affected CI suites and record exact run URL, SHA and results. Certify only after every required live case and business scenario passes.

## Credential handling
Never paste API keys into PRs, logs or chat. Do not overwrite production provider selection merely to force a passing test. If Anthropic cannot be used, keep certification blocked and report the precise missing dependency.
