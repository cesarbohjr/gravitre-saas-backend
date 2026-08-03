# Linear append — STA-337 (append-only; do not replace description)

## Honesty audit (2026-08-03) — code-path only

**Artifacts:**
- `docs/delivery/sta337-adwords-ga-outlook-honesty-audit.md`
- `docs/delivery/sta337-adwords-ga-outlook-honesty-audit.json`

| Connector | Verdict |
|-----------|---------|
| google_ads / googleads | PARTIAL |
| google_analytics | PARTIAL |
| microsoft365 | PARTIAL |
| bare outlook.* | FAIL |

**overall_verdict:** FAIL (bare outlook overclaim)  
**live_pass_claimed:** false

Top remediation: alias or kill `outlook.*`; add `microsoft365` to honesty gate; mark Ads pause/resume mutating; fix/demote GA `funnels.run`.

Do **not** mark STA-337 Done/PASS until live `audit_events` after remediation + deploy.
