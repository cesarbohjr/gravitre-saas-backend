# Linear Integration Backlog (Cursor reference)

Use this file to navigate integration work in Cursor. Issues live in [Linear — Staqbot](https://linear.app/staqbot).

| Tier | Horizon | Project | Initiative |
|------|---------|---------|------------|
| **1** | 30 days | [Tier 1 Integration Platform](https://linear.app/staqbot) | Tier 1 — Integration Platform (30 days) |
| **2** | 90 days | [Tier 2 Integration Platform](https://linear.app/staqbot) | Tier 2 — Department Expansion (90 days) |
| **3** | 6 months | [Tier 3 Integration Platform](https://linear.app/staqbot) | Tier 3 — Enterprise & Marketplace (6 months) |
| **4** | 12 months | [Tier 4 Integration Platform](https://linear.app/staqbot) | Tier 4 — Enterprise Scale & Ecosystem (12 months) |
| **5** | 18 months | [Tier 5 Integration Platform](https://linear.app/staqbot) | Tier 5 — Autonomous Workforce & Vertical Scale (18 months) |

**Re-run issue creation:** `npm run linear:tier1` … `linear:tier5` (requires `LINEAR_API_KEY`).

---

## How to work through this in Cursor

1. Open this file (`docs/integration/LINEAR_INTEGRATION_BACKLOG.md`) in chat with **@LINEAR_INTEGRATION_BACKLOG.md**.
2. Pick the next issue in **Recommended order** whose Tier 1 dependencies are done.
3. Say: *"Implement STA-XX — [title]"* and reference the issue description in Linear.
4. Mark done in Linear when merged.

---

## Tier 1 — Epics

| Epic | Linear | Focus |
|------|--------|--------|
| A Platform Foundation | [STA-6](https://linear.app/staqbot/issue/STA-6) | invoke_tool, permissions, execution merge, OAuth UX |
| B HubSpot CRM | [STA-7](https://linear.app/staqbot/issue/STA-7) | OAuth, 5 actions, triggers |
| C Cross-Agent Orchestration | [STA-8](https://linear.app/staqbot/issue/STA-8) | Handoff bus, routing, builder persistence |
| D Knowledge + Connectors | [STA-9](https://linear.app/staqbot/issue/STA-9) | Dept RAG, Zendesk, GitHub, Calendar stretch |

## Tier 1 — Issues (execution order)

| Order | Ref | Linear | Title | Blocked by |
|-------|-----|--------|-------|------------|
| 1 | T1-001 | [STA-10](https://linear.app/staqbot/issue/STA-10) | Unified invoke_tool service ✅ | — |
| 2 | T1-002 | [STA-11](https://linear.app/staqbot/issue/STA-11) | Agent-tool permission model ✅ | STA-10 |
| 3 | T1-003 | [STA-12](https://linear.app/staqbot/issue/STA-12) | Merge dual execution engines ✅ | STA-10 |
| 4 | T1-004 | [STA-13](https://linear.app/staqbot/issue/STA-13) | Real connector OAuth UX ✅ (platform hardened: `CONNECTOR_PLATFORM.md`) | STA-10 |
| 4a | T1-004a | [STA-125](https://linear.app/staqbot/issue/STA-125) | **Platform setup:** HubSpot OAuth app & deployment secrets ✅ (CLI app deployed; Railway env via `npm run hubspot:railway`) | STA-13 (code) |
| 5 | T1-005 | [STA-14](https://linear.app/staqbot/issue/STA-14) | HubSpot OAuth + token lifecycle ✅ | STA-13, [STA-125](https://linear.app/staqbot/issue/STA-125) |
| 6 | T1-006 | [STA-15](https://linear.app/staqbot/issue/STA-15) | HubSpot v1 actions (5 core) ✅ | STA-10, STA-11, STA-14 |
| 7 | T1-007 | [STA-16](https://linear.app/staqbot/issue/STA-16) | HubSpot inbound triggers ✅ | STA-12, STA-14, STA-15 |
| 8 | T1-008 | [STA-17](https://linear.app/staqbot/issue/STA-17) | Cross-agent handoff data bus ✅ | STA-10 |
| 9 | T1-009 | [STA-18](https://linear.app/staqbot/issue/STA-18) | Wire next_agent_id routing ✅ | STA-17, STA-15 |
| 10 | T1-010 | [STA-19](https://linear.app/staqbot/issue/STA-19) | Workflow builder persistence ✅ | STA-12 |
| 11 | T1-011 | [STA-20](https://linear.app/staqbot/issue/STA-20) | Department-scoped RAG ✅ | — |
| 12 | T1-012 | [STA-21](https://linear.app/staqbot/issue/STA-21) | Zendesk v1 ✅ | STA-10, STA-11 |
| 13 | T1-013 | [STA-22](https://linear.app/staqbot/issue/STA-22) | GitHub v1 ✅ | STA-10, STA-11 |
| 14 | T1-014 | [STA-23](https://linear.app/staqbot/issue/STA-23) | Calendar integration (stretch) ✅ | STA-13 |

**Tier 1 demo milestone:** Seed workflow `backend/app/services/org_seed_service.py:89-100` runs live (STA-15 + STA-18).

**Production verification:** `docs/integration/TIER1_PRODUCTION_SMOKE.md` (HubSpot env: `npm run hubspot:fill-env` after `npm run hubspot:open`).

### Platform ops (before STA-14)

**[STA-125](https://linear.app/staqbot/issue/STA-125) (T1-004a)** is for **Gravitre operators only** (not end users): one HubSpot OAuth app per environment, `HUBSPOT_CLIENT_ID` / `HUBSPOT_CLIENT_SECRET`, redirect URLs, and `CONNECTOR_SECRETS_ENCRYPTION_KEY` on the API host. Customers only use **Connect HubSpot** in the UI.

Create or refresh the Linear issue:

```bash
npm run linear:hubspot-platform-setup
```

Requires `LINEAR_API_KEY`. Parent epic: HubSpot CRM (STA-7).

---

## Tier 2 — Epics

| Epic | Linear | Focus |
|------|--------|--------|
| A Salesforce CRM | [STA-24](https://linear.app/staqbot/issue/STA-24) | OAuth, actions, triggers |
| B Finance & Accounting | [STA-25](https://linear.app/staqbot/issue/STA-25) | QuickBooks, Stripe read |
| C DevOps & Incidents | [STA-26](https://linear.app/staqbot/issue/STA-26) | Jira, PagerDuty |
| D Marketing Analytics | [STA-27](https://linear.app/staqbot/issue/STA-27) | Google Analytics |
| E Knowledge Sync Pipeline | [STA-28](https://linear.app/staqbot/issue/STA-28) | Notion, Confluence, CRM→RAG |
| F Platform Maturity | [STA-29](https://linear.app/staqbot/issue/STA-29) | Cron, council, agent memory |

## Tier 2 — Issues (execution order)

| Order | Ref | Linear | Title | Blocked by (Tier 1 / Tier 2) |
|-------|-----|--------|-------|------------------------------|
| 1 | T2-001 | [STA-30](https://linear.app/staqbot/issue/STA-30) | Salesforce OAuth ✅ | STA-10, STA-13 |
| 2 | T2-002 | [STA-31](https://linear.app/staqbot/issue/STA-31) | Salesforce v1 actions ✅ | STA-10, STA-11 |
| 3 | T2-004 | [STA-33](https://linear.app/staqbot/issue/STA-33) | QuickBooks OAuth ✅ | STA-10, STA-13 |
| 4 | T2-005 | [STA-34](https://linear.app/staqbot/issue/STA-34) | QuickBooks v1 read actions ✅ | STA-10, STA-11 |
| 5 | T2-006 | [STA-35](https://linear.app/staqbot/issue/STA-35) | Stripe read-only agent tool ✅ | STA-10 |
| 6 | T2-007 | [STA-36](https://linear.app/staqbot/issue/STA-36) | Jira Cloud OAuth + v1/v2 actions ✅ | STA-10, STA-13 |
| 7 | T2-008 | [STA-37](https://linear.app/staqbot/issue/STA-37) | PagerDuty OAuth + triggers ✅ | STA-12 |
| 8 | T2-009 | [STA-38](https://linear.app/staqbot/issue/STA-38) | PagerDuty v1 actions ✅ | STA-10 |
| 9 | T2-010 | [STA-39](https://linear.app/staqbot/issue/STA-39) | DevOps cross-tool workflow ✅ | STA-36–38, Slack |
| 10 | T2-014 | [STA-43](https://linear.app/staqbot/issue/STA-43) | Notion sync → RAG ✅ | STA-20 |
| 11 | T2-016 | [STA-45](https://linear.app/staqbot/issue/STA-45) | Knowledge sync scheduler ✅ | STA-20 |
| 12 | T2-017 | [STA-46](https://linear.app/staqbot/issue/STA-46) | HubSpot + Zendesk → RAG ✅ | STA-15, STA-21 |
| 13 | T2-003 | [STA-32](https://linear.app/staqbot/issue/STA-32) | Salesforce triggers ✅ | STA-12 |
| 14 | T2-011 | [STA-40](https://linear.app/staqbot/issue/STA-40) | Google Analytics OAuth ✅ | STA-13, STA-10 |
| 15 | T2-012 | [STA-41](https://linear.app/staqbot/issue/STA-41) | GA4 v1 read actions ✅ | STA-40 |
| 16 | T2-013 | [STA-42](https://linear.app/staqbot/issue/STA-42) | Marketing attribution workflow ✅ | STA-41, STA-15 |
| 17 | T2-015 | [STA-44](https://linear.app/staqbot/issue/STA-44) | Confluence sync → RAG ✅ | STA-20 |
| 18 | T2-018 | [STA-47](https://linear.app/staqbot/issue/STA-47) | Workflow schedule / cron worker ✅ | STA-12 |
| 19 | T2-019 | [STA-48](https://linear.app/staqbot/issue/STA-48) | Council → workflow branch ✅ | STA-17, STA-12 |
| 20 | T2-020 | [STA-49](https://linear.app/staqbot/issue/STA-49) | Agent memory API ✅ | STA-20 |

**Start Tier 2 only after:** STA-10, STA-12, STA-13 (minimum platform), and relevant Tier 1 connector for your track.

**Tier 2 production verification:** `docs/integration/TIER2_PRODUCTION_SMOKE.md` (OAuth + API key flows use shared `app/connectors/platform.py`).

**Current focus:** Tier 5 Epic E — STA-121 Agent role marketplace (STA-120 workflow digital twin ✅).

**Tier 5 production verification:** `docs/integration/TIER5_PRODUCTION_SMOKE.md` — run `npm run smoke:tier5`. Federation: `docs/integration/b2b-handoff-protocol.md`, delegated tasks: `docs/integration/delegated-external-tasks.md`, swarm: `docs/integration/multi-agent-swarm-coordinator.md`, digital twin: `docs/integration/workflow-digital-twin.md`.

---

## Tier 3 — Epics

| Epic | Linear | Focus |
|------|--------|--------|
| A NetSuite ERP | [STA-50](https://linear.app/staqbot/issue/STA-50) | OAuth, read/write (gated) |
| B Workday HRIS | [STA-51](https://linear.app/staqbot/issue/STA-51) | HR data, policy → RAG |
| C LinkedIn Sales Navigator | [STA-52](https://linear.app/staqbot/issue/STA-52) | API ADR, prospect enrich |
| D Marketo MAP | [STA-53](https://linear.app/staqbot/issue/STA-53) | Enterprise marketing automation |
| E Segment CDP | [STA-54](https://linear.app/staqbot/issue/STA-54) | identify/track, workflow triggers |
| F Connector Marketplace | [STA-55](https://linear.app/staqbot/issue/STA-55) | SDK, review, sandbox demo |

## Tier 3 — Issues (execution order)

| Order | Ref | Linear | Title | Blocked by |
|-------|-----|--------|-------|------------|
| 1 | T3-015 | [STA-70](https://linear.app/staqbot/issue/STA-70) | Connector SDK spec ✅ (`connector-sdk-spec.md`, `app/connectors/sdk/`) | STA-10, STA-13, STA-11 |
| 2 | T3-007 | [STA-62](https://linear.app/staqbot/issue/STA-62) | LinkedIn API evaluation (ADR) ✅ (`linkedin-sales-nav.md`) | — |
| 3 | T3-001 | [STA-56](https://linear.app/staqbot/issue/STA-56) | NetSuite OAuth ✅ | STA-10, STA-13 |
| 4 | T3-004 | [STA-59](https://linear.app/staqbot/issue/STA-59) | Workday OAuth ✅ | STA-10 |
| 5 | T3-009 | [STA-64](https://linear.app/staqbot/issue/STA-64) | Marketo OAuth ✅ | STA-13, STA-10 |
| 6 | T3-012 | [STA-67](https://linear.app/staqbot/issue/STA-67) | Segment write-key linking ✅ | STA-10 |
| 7 | T3-002 | [STA-57](https://linear.app/staqbot/issue/STA-57) | NetSuite read actions ✅ | STA-56 |
| 8 | T3-005 | [STA-60](https://linear.app/staqbot/issue/STA-60) | Workday read actions ✅ | STA-59 |
| 9 | T3-010 | [STA-65](https://linear.app/staqbot/issue/STA-65) | Marketo v1 actions ✅ | STA-64 |
| 10 | T3-013 | [STA-68](https://linear.app/staqbot/issue/STA-68) | Segment identify/track ✅ | STA-67 |
| 11 | T3-017 | [STA-72](https://linear.app/staqbot/issue/STA-72) | Marketplace sandbox org ✅ (`/marketplace/sandbox`) | STA-70 |
| 12 | T3-016 | [STA-71](https://linear.app/staqbot/issue/STA-71) | Partner submission workflow ✅ | STA-70 |
| 13 | T3-006 | [STA-61](https://linear.app/staqbot/issue/STA-61) | Workday → RAG sync ✅ | STA-20, STA-45 |
| 14 | T3-008 | [STA-63](https://linear.app/staqbot/issue/STA-63) | LinkedIn prospect enrich ✅ | STA-62, STA-15 |
| 15 | T3-003 | [STA-58](https://linear.app/staqbot/issue/STA-58) | NetSuite write (gated) ✅ | STA-57, STA-11 |
| 16 | T3-011 | [STA-66](https://linear.app/staqbot/issue/STA-66) | Marketo nurture templates ✅ | STA-65, STA-17 |
| 17 | T3-014 | [STA-69](https://linear.app/staqbot/issue/STA-69) | Segment → workflows ✅ | STA-68, STA-12 |
| 18 | T3-018 | [STA-73](https://linear.app/staqbot/issue/STA-73) | Marketplace demo ✅ (`POST /api/marketplace/sandbox/demo`) | STA-70–72 |

**Start Tier 3 only after:** Tier 1 platform (STA-10, STA-11, STA-13) and relevant Tier 2 tracks.

**Tier 3 status:** Complete in code and Linear (STA-50–73 Done). Production smoke: `TIER3_PRODUCTION_SMOKE.md`. Operator scripts: `netsuite:*`, `workday:*`, `marketo:*`.

---

## Tier 4 — Epics

| Epic | Linear | Focus |
|------|--------|--------|
| A Security & Compliance | [STA-74](https://linear.app/staqbot/issue/STA-74) | Residency, SOC2, PII, SIEM |
| B Deploy & Identity | [STA-75](https://linear.app/staqbot/issue/STA-75) | White-label, VPC, SSO |
| C Extended HR & Finance | [STA-76](https://linear.app/staqbot/issue/STA-76) | BambooHR, Greenhouse, Xero |
| D AI Governance & Analytics | [STA-77](https://linear.app/staqbot/issue/STA-77) | Model policy, KPIs, cost |
| E Global Scale & Reliability | [STA-78](https://linear.app/staqbot/issue/STA-78) | Multi-region, HA queue, DR |
| F Marketplace Scale | [STA-79](https://linear.app/staqbot/issue/STA-79) | Revenue share, private connectors |

## Tier 4 — Issues (execution order)

| Order | Ref | Linear | Title | Blocked by |
|-------|-----|--------|-------|------------|
| 1 | T4-015 | [STA-94](https://linear.app/staqbot/issue/STA-94) | Durable workflow run queue (HA) ✅ (`app/workers/workflow_queue.py`, Redis) | STA-12, STA-47 |
| 2 | T4-007 | [STA-86](https://linear.app/staqbot/issue/STA-86) | Enterprise SSO (SAML/OIDC) ✅ (`app/routers/sso.py`, SCIM) | — |
| 3 | T4-001 | [STA-80](https://linear.app/staqbot/issue/STA-80) | Data residency ✅ (`GET/PUT /api/enterprise/data-region`) | — |
| 4 | T4-002 | [STA-81](https://linear.app/staqbot/issue/STA-81) | SOC2 evidence export ✅ (`GET /api/enterprise/compliance/soc2-export`) | STA-10 |
| 5 | T4-003 | [STA-82](https://linear.app/staqbot/issue/STA-82) | PII redaction in audit ✅ (`app/services/compliance_service.py`) | STA-10 |
| 6 | T4-011 | [STA-90](https://linear.app/staqbot/issue/STA-90) | Model allowlist policy ✅ | STA-11 |
| 7 | T4-014 | [STA-93](https://linear.app/staqbot/issue/STA-93) | Multi-region workflow routing ✅ (`GET /api/enterprise/execution-region`) | STA-80 |
| 8 | T4-005 | [STA-84](https://linear.app/staqbot/issue/STA-84) | White-label branding ✅ (`GET/PUT /api/enterprise/branding`) | — |
| 9 | T4-006 | [STA-85](https://linear.app/staqbot/issue/STA-85) | VPC / Helm deployment ✅ (`deploy/enterprise/`) | — |
| 10 | T4-012 | [STA-91](https://linear.app/staqbot/issue/STA-91) | Workforce analytics dashboard ✅ (`GET /api/enterprise/workforce-analytics`) | STA-10, STA-17 |
| 11 | T4-013 | [STA-92](https://linear.app/staqbot/issue/STA-92) | Per-agent cost attribution ✅ (`GET /api/enterprise/cost-attribution`) | STA-10 |
| 12 | T4-008 | [STA-87](https://linear.app/staqbot/issue/STA-87) | BambooHR connector ✅ (`bamboohr.*` tools) | STA-10, STA-13 |
| 13 | T4-009 | [STA-88](https://linear.app/staqbot/issue/STA-88) | Greenhouse connector ✅ (`greenhouse.*` tools) | STA-10, STA-13 |
| 14 | T4-010 | [STA-89](https://linear.app/staqbot/issue/STA-89) | Xero connector ✅ (`xero.*` read tools) | STA-33, STA-34 |
| 15 | T4-004 | [STA-83](https://linear.app/staqbot/issue/STA-83) | SIEM export ✅ (`GET/PUT/POST /api/enterprise/siem`) | STA-81, STA-82 |
| 16 | T4-016 | [STA-95](https://linear.app/staqbot/issue/STA-95) | Workflow DR runbook ✅ (`workflow-dr-runbook.md`) | STA-94 |
| 17 | T4-017 | [STA-96](https://linear.app/staqbot/issue/STA-96) | Marketplace v2 billing ✅ (`/marketplace/billing`, v1 Express + transfers; v2 reference at `/samples/stripe-connect`) | STA-73 |
| 18 | T4-018 | [STA-97](https://linear.app/staqbot/issue/STA-97) | Certified partner program ✅ (static scan, scope review, registry badge) | STA-70 |
| 19 | T4-019 | [STA-98](https://linear.app/staqbot/issue/STA-98) | Private connector runtime ✅ (`/marketplace/private`, signed bundles + sandbox) | STA-70, STA-85 |
| 20 | T4-020 | [STA-99](https://linear.app/staqbot/issue/STA-99) | Fine-tuning → agent runtime ✅ (`agent_finetune_service.py`) | STA-49 |

**Tier 4 status:** Complete in code (STA-74–99 Done). Production smoke: `TIER4_PRODUCTION_SMOKE.md`.

**Start Tier 4 only after:** Tier 1 platform complete; Tier 3 marketplace (STA-70, STA-73) for ecosystem epics.

---

## Tier 5 — Epics

| Epic | Linear | Focus |
|------|--------|--------|
| A Autonomous Execution | [STA-100](https://linear.app/staqbot/issue/STA-100) | Auto-execute, rollback, interrupt, budgets |
| B Regulated Compliance | [STA-101](https://linear.app/staqbot/issue/STA-101) | HIPAA, FedRAMP prep, EU AI Act |
| C Industry Vertical Packs | [STA-102](https://linear.app/staqbot/issue/STA-102) | Healthcare, Legal, Real estate |
| D Multi-Org Federation | [STA-103](https://linear.app/staqbot/issue/STA-103) | B2B handoffs, delegated tasks |
| E Advanced AI Workforce | [STA-104](https://linear.app/staqbot/issue/STA-104) | Swarms, simulation, role marketplace |
| F Platform Intelligence | [STA-105](https://linear.app/staqbot/issue/STA-105) | Predictive ops, recommendations, health score |

## Tier 5 — Issues (execution order)

| Order | Ref | Linear | Title | Blocked by |
|-------|-----|--------|-------|------------|
| 1 | T5-001 | [STA-106](https://linear.app/staqbot/issue/STA-106) | Policy-gated auto-execute ✅ | STA-10, STA-11, STA-90 |
| 2 | T5-003 | [STA-108](https://linear.app/staqbot/issue/STA-108) | Human-in-the-loop interrupt ✅ | STA-106 |
| 3 | T5-004 | [STA-109](https://linear.app/staqbot/issue/STA-109) | Autonomous run budgets ✅ | STA-92, STA-106 |
| 4 | T5-002 | [STA-107](https://linear.app/staqbot/issue/STA-107) | Compensating transactions / rollback ✅ | STA-106, STA-15 |
| 5 | T5-005 | [STA-110](https://linear.app/staqbot/issue/STA-110) | HIPAA BAA + PHI controls ✅ | STA-82, STA-80 |
| 6 | T5-007 | [STA-112](https://linear.app/staqbot/issue/STA-112) | EU AI Act transparency logs ✅ | STA-106, STA-81 |
| 7 | T5-006 | [STA-111](https://linear.app/staqbot/issue/STA-111) | FedRAMP gap assessment ✅ | STA-81 |
| 8 | T5-008 | [STA-113](https://linear.app/staqbot/issue/STA-113) | Healthcare vertical pack ✅ | STA-110 |
| 9 | T5-009 | [STA-114](https://linear.app/staqbot/issue/STA-114) | Legal vertical pack (Clio) ✅ | STA-10, STA-13 |
| 10 | T5-010 | [STA-115](https://linear.app/staqbot/issue/STA-115) | Real estate vertical pack ✅ | STA-15 |
| 11 | T5-011 | [STA-116](https://linear.app/staqbot/issue/STA-116) | Cross-org B2B handoff protocol ✅ | STA-17, STA-86 |
| 12 | T5-012 | [STA-117](https://linear.app/staqbot/issue/STA-117) | Federated connector consent ✅ | STA-116 |
| 13 | T5-013 | [STA-118](https://linear.app/staqbot/issue/STA-118) | Delegate task to external org ✅ | STA-116 |
| 14 | T5-014 | [STA-119](https://linear.app/staqbot/issue/STA-119) | Multi-agent swarm coordinator ✅ | STA-106, STA-48 |
| 15 | T5-015 | [STA-120](https://linear.app/staqbot/issue/STA-120) | Workflow digital twin (simulate) ✅ | STA-12, dry_run |
| 16 | T5-016 | [STA-121](https://linear.app/staqbot/issue/STA-121) | Agent role marketplace | STA-73 |
| 17 | T5-017 | [STA-122](https://linear.app/staqbot/issue/STA-122) | Predictive workflow failure | STA-91, STA-94 |
| 18 | T5-018 | [STA-123](https://linear.app/staqbot/issue/STA-123) | Auto-suggest connectors/workflows | STA-91 |
| 19 | T5-019 | [STA-124](https://linear.app/staqbot/issue/STA-124) | Customer integration health score | STA-91 |

**Start Tier 5 Epic A only after:** STA-10, STA-11, STA-82, STA-90 (guardrails first).

**Tier 5 Epic C status:** STA-113–115 shipped (healthcare, legal/Clio, real estate). Production smoke: `npm run smoke:tier5`.

---

## Full roadmap summary

| Tier | Issues | Linear range |
|------|--------|----------------|
| 1 | 14 + 4 epics | STA-6 – STA-23 |
| 2 | 20 + 6 epics | STA-24 – STA-49 |
| 3 | 18 + 6 epics | STA-50 – STA-73 |
| 4 | 20 + 6 epics | STA-74 – STA-99 |
| 5 | 19 + 6 epics | STA-100 – STA-124 |

---

## Key code paths

| Area | Path |
|------|------|
| Tool registry | `backend/app/routers/connectors.py` |
| Step execution | `backend/app/workflows/execute.py` |
| Stub graph engine | `backend/app/services/execution_service.py` |
| Agent jobs | `backend/app/operators/agent_jobs.py` |
| Demo seed | `backend/app/services/org_seed_service.py` |
| Connector UI | `apps/web/app/connectors/page.tsx` |
| Workflow builder | `apps/web/app/workflows/[id]/builder/page.tsx` |
| RAG | `backend/app/rag/` |
