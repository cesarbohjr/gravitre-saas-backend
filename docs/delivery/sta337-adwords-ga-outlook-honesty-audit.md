# STA-337 — AdWords / GA / Outlook honesty audit

**Method:** code-path honesty audit only  
**Date:** 2026-08-03  
**Machine artifact:** [`sta337-adwords-ga-outlook-honesty-audit.json`](./sta337-adwords-ga-outlook-honesty-audit.json)  
**live_pass_claimed:** `false`  
**overall_verdict:** `FAIL` (driven by bare `outlook.*` overclaim)

Do **not** upgrade any connector to honesty PASS without fresh `audit_events` / run ids after remediation + deploy.

## Verdict table

| connector | verdict | why |
|-----------|---------|-----|
| `google_ads` / `googleads` / AdWords | PARTIAL | Dedicated mutate/read executors + aliases exist; pause/resume miss mutation markers; completed-work honesty still gated |
| `google_analytics` / GA | PARTIAL | v1–v3 invoke paths wired; `funnels.run` overclaims (not a real funnel API) |
| `microsoft365` | PARTIAL | Real Graph executors; missing from `HONESTY_GATED_CONNECTORS`; `mail.send` often proof-empty |
| bare `outlook.*` | FAIL | Catalog/schemas/verified-output imply send/reply; no executor, no HTTP profile, no alias to `microsoft365.*` |

## Findings (summary)

### Google Ads
- Catalog + dedicated `googleads.*` registry + `google_ads`→`googleads` alias are real.
- Gap: `MUTATING_ACTION_MARKERS` omit `.pause` / `.resume` → pause/resume may classify as read.
- Gap: verified-output lists `google_ads.*` while runtime stamps `googleads.*`.

### Google Analytics
- Dedicated + priority paths cover reports/properties/metadata.
- Gap: `run_funnel_report` ignores `funnel_steps` and returns a generic event report (`google_analytics.py`).

### Microsoft 365 / Outlook
- `microsoft365.*` Graph paths are real (mail/calendar/teams/files).
- Bare `outlook.*` is an overclaim surface (catalog + workflow schemas + verified-output) with no invoke path.
- Install gate keys `outlook` / `microsoft` but not `microsoft365`.

## Remediation backlog (ordered)

1. Alias or kill bare `outlook.*` (`outlook`→`microsoft365` action map, or strip catalog/verified-output/schemas).
2. Add `microsoft365` to `HONESTY_GATED_CONNECTORS`.
3. Extend `MUTATING_ACTION_MARKERS` with `.pause`, `.resume`.
4. Normalize Google Ads action stamps vs verified-output naming.
5. Fix or demote `google_analytics.funnels.run`.
6. Stamp proof on `microsoft365.mail.send` (result_url / accepted marker).
7. Live evidence pass — Ads pause/resume, GA report, M365 send — before any PASS claim.

## Status

**INCONCLUSIVE for production honesty** — audit complete as backlog evidence; no live PASS.
