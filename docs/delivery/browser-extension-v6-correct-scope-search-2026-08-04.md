# Extension v6 — correctly scoped surface search (close at v5)

Date: 2026-08-04  
Prior mine (wrong territory for this question): `browser-extension-v6-surface-candidates-2026-08-04.md` (usage-signal tip smoke only)  
Gate: `browser-extension-v6-gate-2026-08-03.md`  
Security review issue: [STA-340](https://linear.app/staqbot/issue/STA-340/extension-v6-agentic-dom-security-review-gated)

## Standing rule (unchanged)

v6 requires **all** of:

1. A specific named surface in a real non-API category  
2. A documented **real Gravitree operator need** (not hypothetical industry existence)  
3. STA-340 security review **passed**

No agentic DOM code until all three. Empty search ⇒ close roadmap at v5 (legitimate complete outcome).

## Scoping correction

The prior usage-signal mine looked at tip `extension.usage_signal` rows (LinkedIn smoke, `example.com`, fixture hosts). That cannot answer “non-API surface,” because:

- Allowlisted CRM/mail hosts are **catalog territory by definition**  
- Smoke fixtures are not operator demand  

This pass searches the **right** territory: industry computer-use categories × Gravitree’s **actual** product/customer evidence.

## What was ruled OUT (catalog / buildable API)

Anything already reachable via an existing **or buildable** governed catalog connector — CRM, marketing, ticketing with documented public APIs — is **out of scope for v6** even if Gravitree has not shipped the connector yet.

Examples explicitly ruled out for v6:

| System | Why not v6 |
|--------|------------|
| HubSpot, Apollo, Salesforce, Slack, Gmail, Outlook | Extension allowlist + catalog actions |
| Zendesk, Jira, QuickBooks, NetSuite, Asana, Monday, etc. | Documented APIs → connector/catalog backlog |
| **ConnectWise, Datto** | Named in `backend/app/domain/profiles/msp.yaml` as `connector_preferences` only; both have public/partner APIs → **catalog backlog if prioritized**, not DOM |

## Category search × Gravitree evidence

Industry computer-use categories checked against repo + Linear (not “does such a site exist on the internet”).

| Category | What we looked for | Finding in Gravitree evidence |
|----------|-------------------|-------------------------------|
| 1. Legacy enterprise / ERP / accounting (no API) | Named customer workflow blocked by portal-only UI | **None.** Financial tools in roadmap (QuickBooks, NetSuite) are API connectors (Tier 2). |
| 2. Government / municipal / utility portals | Permit, license, compliance filings named by operators | **None** in docs, Linear, or packs. |
| 3. Vendor / supplier / MSP / insurance / distributor portals | Named portal with no API blocking a real workflow | **None.** MSP pack does not target Pax8/Ingram/carrier portals. |
| 4. Internal admin panels (DNS, scheduling, legacy tickets) | Named panel + repeated operator need | **None.** |

### MSP Intelligence Pack (most promising place — checked first)

Shipped MSP product scope is **not** PSA/RMM portal ops:

| Artifact | Actual scope |
|----------|----------------|
| `backend/app/marketplace/intelligence_packs/catalog.py` — MSP Intelligence Pack | Apollo/HubSpot MSP **prospecting** + NVD/CISA vuln intel |
| `msp_prospecting_list_workflow.py` / delivery docs | Sell *to* MSPs via lists — catalog APIs |
| `msp.yaml` ConnectWise/Datto | Preferences only; **no connectors**; APIs exist → not v6 |
| MSP Operations Pack | Slack / runbook scaffolds — not vendor portals |

**No MSP workflow is documented as blocked today by a no-API vendor portal.**

### Documented customer segment (ICP)

No formal mid-market ICP interview set in repo. Positioning is **operators / RevOps / department ops** (`introduction.mdx`, marketing copy), with MSP as a **marketplace pack vertical**, not “our customers live in ConnectWise UI with no API.”

### Support / sales / feature-request VOC

| Source | Result |
|--------|--------|
| Repo support-ticket dumps / Zendesk exports | **Absent** |
| Sales discovery / win-loss notes with portal quotes | **Absent** |
| Feature requests naming a no-API portal | **Absent** |
| Linear search (portal / DOM / ConnectWise / government / computer use) | Only engineering gate [STA-340](https://linear.app/staqbot/issue/STA-340/extension-v6-agentic-dom-security-review-gated); no customer-need issue naming a surface |

## Named v6 candidate

**None.**

No exact site/system + exact operator need + evidence of real (not hypothetical) demand.

## Verdict

**CLOSE THE EXTENSION ROADMAP AT v5.**

This is a thorough, correctly scoped search. Re-open only with **new information**: a named non-API surface **and** documented Gravitree operator need (ticket, sales note, or signed operator statement). Do not re-litigate from industry category lists alone.

STA-340 remains the security-review vehicle **if/when** a surface is named; it is **not** the next build step. No agentic DOM code.

## What would reopen (checklist)

- [ ] Exact host/product UI named  
- [ ] Proof no governed API exists (or cannot be productized)  
- [ ] Documented Gravitree operator need (who, how often, which workflow)  
- [ ] STA-340 threat model + sign-off for that surface  
- [ ] Only then: design / build / live Outcomes proof  
