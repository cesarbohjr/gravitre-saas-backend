# Gravitre Connector Roadmap

**Version:** 1.0  
**Last updated:** May 29, 2026  
**Related:** `docs/integration/LINEAR_INTEGRATION_BACKLOG.md`

---

## Section 2 — Priority ranking

### Tier A (launch now — high demand, auth + tools ready)

| Vendor | Customer demand | Revenue impact | Implementation | Strategic value |
|--------|-----------------|----------------|----------------|-----------------|
| HubSpot | Very high | High | Easy | CRM core |
| Salesforce | Very high | High | Moderate | Enterprise CRM |
| Slack | Very high | High | **Easy** (needs OAuth sprint) | Notifications, workflows |
| Google Workspace (6) | Very high | High | Easy | Universal productivity |
| Jira | High | High | Easy | DevOps / IT |
| Zendesk | High | High | Easy | Support |
| GitHub | High | Medium | Easy | DevOps |
| PagerDuty | Medium | Medium | Easy | Incidents |
| QuickBooks | High | High | Moderate | Finance SMB |
| Gmail / Calendar | High | Medium | Easy | Scheduling, comms |

### Tier B (next quarter — high value, moderate work)

| Vendor | Customer demand | Revenue impact | Implementation | Strategic value |
|--------|-----------------|----------------|----------------|-----------------|
| Notion | High | Medium | Moderate | Knowledge / RAG |
| Confluence | Medium | Medium | Moderate | Enterprise wiki |
| Microsoft 365 | High | High | Complex | Microsoft ecosystem |
| Stripe | High | High | Easy | Billing intelligence |
| NetSuite | Medium | High | Complex | Enterprise ERP |
| Marketo | Medium | High | Complex | Marketing automation |
| Segment | Medium | Medium | Easy | Event pipeline |
| LinkedIn | Medium | Medium | Moderate | Sales enrichment |
| Monday.com | Medium | Medium | Moderate | Work OS |
| Asana | Medium | Medium | Easy | PM |
| Intercom | Medium | Medium | Easy | Support messaging |
| Mailchimp | Medium | Medium | Easy | Email marketing |

### Tier C (expansion — catalog + OAuth route, tools needed)

Airtable, ClickUp, Xero, Freshdesk, Constant Contact, Workday, Odoo, Gorgias, BambooHR, PostgreSQL tools, Snowflake, Mixpanel, Apollo, SendGrid, Twilio, n8n, Motion, SEMrush, StackAdapt, Absorb LMS, MongoDB, AWS S3

### Tier D (blocked or non-OAuth by design)

Zapier, Hootsuite, Gusto, Canva, ADP (partner), Plaid (Link incomplete), API-key-only vendors without tools

---

## Section 9 — Connector revenue strategy

| Vendor | Customer demand | Revenue impact | Strategic value | Recommended phase |
|--------|-----------------|----------------|-----------------|-------------------|
| HubSpot | Very high | High | CRM hub | **Phase 1** |
| Salesforce | Very high | High | Enterprise | **Phase 1** |
| Slack | Very high | High | Activation | **Phase 1** |
| Google (6) | Very high | High | Workspace | **Phase 1** |
| Notion | High | Medium | Knowledge | **Phase 1** |
| Jira | High | High | DevOps | **Phase 1** |
| Zendesk | High | High | Support | **Phase 2** |
| GitHub | High | Medium | DevOps | **Phase 2** |
| Microsoft 365 | High | High | Enterprise | **Phase 2** |
| Monday.com | Medium | Medium | PM | **Phase 2** |
| Asana | Medium | Medium | PM | **Phase 2** |
| ClickUp | Medium | Low | PM | **Phase 2** |
| Stripe | High | High | Finance | **Phase 2** |
| QuickBooks | High | High | Finance | **Phase 1** |
| NetSuite | Medium | High | ERP | **Phase 3** |
| Workday | Medium | Medium | HR | **Phase 3** |
| Marketo | Medium | High | Marketing | **Phase 3** |
| Segment | Medium | Medium | Data | **Phase 3** |
| Partner-gated | Low (until approved) | Medium | Platform | **Phase 3+** |

### Phase definitions

**Phase 1 — Revenue core (0–90 days)**  
Google Workspace, Slack (OAuth), HubSpot, Salesforce, Notion, Jira, QuickBooks, Gmail, Calendar, PagerDuty

**Phase 2 — Department expansion (90–180 days)**  
Microsoft 365, GitHub, Zendesk, Monday, Asana, ClickUp, Stripe, Intercom, Mailchimp, LinkedIn

**Phase 3 — Long tail (180+ days)**  
Remaining connectors, partner programs, Plaid Link, database/IAM tools, enterprise ERP/HR

---

## Recommended launch connector set (top 15)

These maximize **one-click OAuth coverage**, **implemented tools**, and **cross-workflow value**:

1. **HubSpot** — CRM, demo seed workflow, 10 tools  
2. **Salesforce** — Enterprise CRM, 11 tools  
3. **Slack** — Notifications (implement OAuth + keep post_message)  
4. **Gmail** — Email send/read  
5. **Google Calendar** — Scheduling, agent availability  
6. **Google Drive** — Document retrieval for RAG  
7. **Jira** — Issue tracking, DevOps workflows  
8. **PagerDuty** — Incident response  
9. **Zendesk** — Support tickets  
10. **GitHub** — PR/issue automation  
11. **QuickBooks** — Finance read  
12. **Google Analytics** — Marketing attribution  
13. **Notion** — Knowledge (add v1 read tools)  
14. **Stripe** — Billing read  
15. **Segment** — Event identify/track  

**Operator action:** Register platform OAuth apps for items 1–2, 4–12, 14–15; implement Slack OAuth for #3; build Notion read tools for #13.

---

## Engineering milestones

| Milestone | Deliverable | Vendors |
|-----------|-------------|---------|
| M1 | Platform credentials in Railway for Category A | 12 OAuth apps |
| M2 | Slack OAuth implementation | Slack |
| M3 | Notion + Confluence v1 read tools | 2 |
| M4 | Generic OAuth v1 tool template | Mailchimp, Asana, Monday, Intercom |
| M5 | Plaid Link E2E | Plaid |
| M6 | Partner program submissions | Zapier, Canva, Gusto, Hootsuite, ADP |
| M7 | PostgreSQL read-only query tool | PostgreSQL |

---

## Success metrics

| Metric | Current | Phase 1 target |
|--------|---------|----------------|
| Production-ready connectors | ~15 | 20 |
| OAuth routes with platform apps configured | Unknown | 15 |
| Registered invoke_tool actions | 100 | 150 |
| Connectors with ≥1 implemented v1 read action | ~16 | 25 |
| Median time-to-first-connect (OAuth) | — | < 3 minutes |

---

## References

- `docs/CONNECTOR_IMPLEMENTATION_MATRIX.md`
- `docs/CONNECTOR_CREDENTIAL_ACQUISITION_PLAYBOOK.md`
- `docs/CONNECTOR_PRODUCTION_READINESS_REPORT.md`
- `GET /api/connectors/catalog/actions` — live action + workflow catalog
- `scripts/generate_vendor_catalog.py` — regenerate action definitions
