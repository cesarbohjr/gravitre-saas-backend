# Gravitre release queue and controlled migration rollout

Status: **operational runbook** (documentation only — no automated prod SQL). Updated **2026-10-14**.

## Current state (cross-check)

| Track | Code on `main` | Prod acceptance |
|-------|----------------|-----------------|
| Release 1 security six + follow-ups | Merged #401–#410 | **NOT RUN** (migrations + auth matrix) |
| Release 2 execution / approvals | Merged #412–#416 | **NOT RUN** |
| Release 3 triggers / metering | Merged #417–#420 | **NOT RUN** |
| Release 4 MSP / external MCP | Not started | — |
| Automate Plays/Workflows/Schedules | Merged #427 | Follow `docs/delivery/plays-production-acceptance.md` |

**Production sample (2026-10-14):** `GET https://api.gravitre.app/health` → `git_sha=b642dd156` (includes security merge train). Compare to `git rev-parse main` after each deploy.

## Open infrastructure PRs

| PR | Purpose | Notes |
|----|---------|-------|
| #424 | `production-release-verification.yml` | CI green on head; merges post-CI SHA check for gravitre.app + api health |
| #426 | This runbook | Documentation |

Vercel `web` + `gravitre-saas-backend` checks were **passing** on PR #424 head (2026-10-14).

## Production migration prerequisites — fail closed

1. Isolated Supabase **staging** project (not `smyeexlrqdpymwjmgzqu`).
2. Reconcile migration filenames/checksums vs staging and prod histories.
3. Run new SQL on staging; smoke org creation, invites, member admin, frontend reads.
4. Test backup/PITR and document irreversible steps (`20261013030000` deactivates dead documents).
5. Protected GitHub environments `supabase-staging` / `supabase-production` with reviewers.
6. Least-privilege credentials in environment secrets only.
7. **Single migration authority** + concurrency lock; abort on drift.
8. Append-only deployment log (migration id, operator, SHA, preflight counts, smoke).
9. Expand → deploy backend/web → contract cleanup in a later release.

Do not enable GitHub Actions production `db push` until steps 1–8 are verified.

## Suggested merge train (remaining product debt — not authorized as a batch)

Prioritize **production acceptance** over new feature PRs. Draft marketplace/voice PRs (#261–#289, #325–#382) remain **P2** until Release 1 gate is **PASS**.

## Per-PR release gate

Record: SHA, migrations, flags, CI URL, `/health` match, smoke JSON, owner sign-off. CI green ≠ production PASS.
