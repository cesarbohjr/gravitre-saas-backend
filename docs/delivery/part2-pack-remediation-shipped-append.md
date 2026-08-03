# Linear append — Part 2 pack remediation (paste into Slice A / pack honesty ticket)

## Part 2 finish — remediated (2026-08-03)

**Decision:** REMEDIATE all 6 (not unpublish). Seed binding bugs only.

| Slug | Fix |
|------|-----|
| hubspot-lead-qualification | `hubspot.search_contacts` → `hubspot.contacts.search` |
| customer-health-monitoring | same |
| lead-routing-automation | same |
| qbr-preparation-workflow | same |
| zendesk-ticket-triage | declare install var `TICKET_ID`; param_sources `$TICKET_ID` |
| support-operations-pack | same `$TICKET_ID` |

**Evidence (seed catalog in-process — not prod DB reseed yet):**
- `pytest backend/tests/marketplace/test_marketplace_seed_catalog.py tests/marketplace/test_install_ready.py -q` → **88 passed**
- `python backend/scripts/audit_published_pack_install_ready.py` → **pass=72 fail=0**
- Artifact: `docs/delivery/published-pack-install-ready-audit.json` (`generatedAt` 2026-08-03T…, `installReadyFail: 0`, `failedSlugs: []`)

**Still needed for marketplace UI:** redeploy tip + re-seed marketplace catalog in prod so published rows pick up remediations (seed audit alone ≠ prod install surface).

Status: **PART 2 CODE REMEDIATION COMPLETE** — label as Done for seed gate; prod reseed = follow-up deploy step.
