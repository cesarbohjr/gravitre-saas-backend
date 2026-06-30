# Marketing Operations Department Pack — Phases 5–8 Audit

**Date:** 2026-06-07  
**Scope:** Buildability audit (Phases 5–7, audit-only) + Department Pack Pricing Framework and Stripe implementation (Phase 8)  
**Assumption baseline:** Phases 1–4 platform consolidation and AI/agentic Decisions 1–3 are live — **verified against code, not assumed.**

---

## Executive Summary

### What consolidation changed

| Expected post-consolidation state | Verified actual state | Discrepancy? |
|---|---|---|
| `execute.py` single entry router | **Partial.** Graph runs use `execution_engine_runtime`; linear workflows still have a separate path in `backend/app/workflows/execute.py`. | Minor — graph is canonical for multi-agent chains. |
| `ExecutionCore` class | **Renamed/absent.** Shared path is `AgentIntelligence.execute_task()` in `backend/app/operators/agent_intelligence.py` with profiles via `execution_mode_service.py`. | Naming only — capability exists. |
| `UnifiedRetrievalService` | **Live** — `backend/app/services/unified_retrieval_service.py`; Knowledge Search and Assistant route through it. | None |
| `execution_mode` / `execution_verified` | **Live** — swarm migration `20260707120000_agent_swarm_execution_verified.sql`, surfaced in operator/agent/workflow/swarm outputs. | None |
| CoordinationLayer cut-over | **KILLED (2026-06-21).** `docs/delivery/sta258-coordination-evaluation-latest.json` records `forcedOutcome: "kill"`; no `backend/app/coordination/`. Swarm/workflow remain separate wrappers around AgentIntelligence. | Expected cut-over did **not** happen. |
| Audit log immutability | **Partial fix.** RLS read-only for members shipped (`20260708130000_audit_retention_and_immutability.sql`). `retention_purge()` **still deletes** aged events via controlled RPC — not append-only forever. | Compliance caveat for long-lived approval trails. |
| Connector count ~19 OAuth | **Undercount in brief.** 19 OAuth providers in `oauth_provider_registry.py`; **62** vendors in action catalog (**40** shipped per connection health). | Updated count, not a regression. |
| Marketplace paid gating | **Live** — `marketplace/entitlements.py` + `assert_install_entitlement()`; one-time checkout via `pricing_type=paid` (`mode=payment`). Subscription checkout remains for other asset types if needed. | None |
| Marketing claims (Decision 3) | Not re-audited in UI copy this pass; pack seed description does not claim autonomous cross-tool action. | Monitor when full 4-agent chain ships. |

### What consolidation did **not** change (never in Decisions 1–3 scope)

These gaps remain **exactly as before** — platform consolidation did not incidentally solve them:

1. **Batch partial approval (5.2)** — still missing; no `partial_approval` model, UI, or selective re-entry.
2. **Rejection → specific upstream agent (5.2)** — `on_reject` is only `fail_workflow` or `skip` in `execution_engine_runtime.py`.
3. **Brand/positioning knowledge store as pack primitive (7.1)** — RAG sources exist; no pack-scoped structured brand store.
4. **Pack-level version/rollback (7.2)** — asset versions exist; coordinated multi-entity pack rollback does not.
5. **Partial batch outcomes in analytics (7.3)** — no batch-outcome schema; `estimated_hours_saved` remains estimate-only.
6. **Mode B — autonomous outcome-driven replanning (6.2)** — **net-new platform work**, not a config switch.

### Mode A / Mode B (explicit product decision required)

- **Mode A (human-approved suggestions)** — **recommended default.** Extends existing patterns: `CompanyIntelligenceOrchestrator`, `outcome_attribution_service.py` (correlational, not RL), integration suggestions (`integration_suggestion_service.py`). Agent behavior changes only after human approval.
- **Mode B (autonomous replanning)** — **does not exist** on the platform. Would require new infrastructure: automatic tone/cadence/content-type shifts, per-cycle caps, rollback, and audit trail without an approval anchor. **Awaiting pack-owner sign-off** on whether Mode B ships at all and on default mode selection.

**Tradeoff (plain language):** Mode A adapts slower but every behavior change is reviewed. Mode B adapts faster but can shift brand voice and content strategy with nobody checking first. Engineering recommends Mode A as default; product leadership must confirm or override.

### Phase 8 pricing

Phase 8 figures are grounded in **cited comparable research** (June 2026), not invented intuition. A **general department pack pricing framework** (tier banding 1–3) is now codified in `backend/app/marketplace/pack_pricing.py` and migration `20260709120000_marketplace_pack_tier.sql`. Marketing Operations Pack is the first live test case at **Tier 2 / $149 one-time unlock** (not a recurring pack fee).

---

## Capability Matrix

| Capability | Status | Evidence |
|---|---|---|
| 4-agent sequential chain via graph + handoff | **Partial / expressible** | `handoff_service.execute_agent_step_with_handoff()` supports `next_agent_id`; graph engine in `execution_engine_runtime.py`. Seed pack has **2 agents**, not 4 — full chain is pack content work, not platform gap. |
| Pack as `department_pack` marketplace asset | **Exists** | `asset_type` in `20260617130000_marketplace_unified_assets_schema.sql`; install in `marketplace/service.py`; seed `marketing-operations-pack`. |
| Independent agent versioning in chain | **Partial** | Agents version via `agents` table; workflow graph references agent IDs. No pack-coordinated semver across chain members. |
| Batch approval (single gate, multiple items) | **Missing** | Approval pauses one node; no batch grouping. |
| Partial approve/reject within batch | **Missing** | No schema or UI. |
| Rejection routes to upstream agent | **Missing** | `on_reject ∈ {fail_workflow, skip}` only. |
| Mode A feedback loop | **Partial — extend** | Company intelligence + outcome attribution + integration suggestions; not wired to post-publish marketing metrics. |
| Mode B autonomous replanning | **Missing — net-new** | No autonomous behavior mutation loop. |
| Brand knowledge on UnifiedRetrievalService | **Partial — extend** | Pack RAG doc in seed; department-scoped RAG migration `20260602130000_department_scoped_rag.sql`. |
| Audit trail for approvals | **Partial** | Immutable member writes fixed; retention purge still deletes old events. |
| Pack-level rollback | **Missing** | Per-asset version history only. |
| Partial batch analytics | **Missing** | — |
| Hours saved measurement | **Estimate only** | `estimated_hours_saved` on assets; ROI in `marketplace/roi.py`. |
| Paid pack install gating | **Exists** | `entitlements.assert_install_entitlement()` → `PAYMENT_REQUIRED`. |
| One-time pack checkout | **Exists (Phase 8)** | `create_asset_checkout_session()` mode `payment` when `pricing_type = paid`. |

---

## Connector Gap List (Phase 6.1)

Reconfirmed against current connector layer (`vendor_definitions.py`, `oauth_provider_registry.py`, `tool_service.py`).

| Connector | State | Notes | Complexity vs OAuth pattern |
|---|---|---|---|
| **Apollo.io** | **Partial — exists** | Action catalog + `apollo_tools.py`; API-key auth (`apollo_api.py`), not OAuth registry. | **Low** — already shipped |
| **Notion** | **Partial — exists** | OAuth (`notion_oauth.py`), sync service, pages/databases actions. | **Low** — already shipped |
| **Google Drive** | **Partial — exists** | Google vendor OAuth + `google_drive` tools in `tool_service.py`. | **Low** — already shipped |
| **Dropbox** | **Missing** | No vendor definition or OAuth spec. | **Medium** — new OAuth provider + file actions |
| **Canva** | **Partial — exists** | OAuth in registry; designs/export/autofill actions; `canva_tools.py`. | **Low** — already shipped |
| **Adobe (Creative Cloud)** | **Missing** | Adobe Marketo exists; no Creative Cloud / Express design connector. | **High** — separate Adobe API surface |
| **Engagebay** | **Missing** | Not in catalog. | **Medium** — new vendor profile + OAuth/API key |
| **LinkedIn (publishing)** | **Partial — read/enrich only** | LinkedIn in catalog for prospect enrich, ads, leads — **no `posts.create` / `w_member_social` publish action**. Write scopes not handled for organic publishing. | **High** — LinkedIn Marketing API partner program + publish scopes |

**LinkedIn flag:** Pack requirements that include organic post publishing need new write-scope actions and likely LinkedIn partner approval — current scope handling cannot satisfy publish-only flows.

---

## Platform Gaps Requiring New Infrastructure

| Gap | Priority | Effort | Blocks pack? |
|---|---|---|---|
| Batch + partial approval model + UI + selective re-entry | P0 for compliance workflows | Large | Yes — core pack differentiator |
| Rejection → upstream agent routing | P0 | Medium | Yes |
| Mode B autonomous replanning + guardrails + audit | P1 (opt-in only) | Large | No if Mode A default |
| Post-publish marketing metrics → Mode A suggestions | P1 | Medium | Partial — limits feedback loop |
| Pack-level coordinated rollback | P2 | Medium | No for v1 |
| Partial batch analytics | P2 | Medium | No for v1 |
| LinkedIn publishing connector | P1 for social publish workflow | High | Yes for publish step |
| Dropbox / Engagebay / Adobe CC | P2 | Medium–High | Depends on workflow design |
| Full 4-agent seed content (vs current 2-agent seed) | P1 content | Medium | Yes for marketed scope |

---

## Phase 8 — Pricing Research Findings

### Comparable products (June 2026)

| Product | What's bundled | Model | Price | Match quality |
|---|---|---|---|---|
| **Make.com Teams** | Multi-step automation, connectors, team workspace | Per-user/month | Core $9, Pro $16, **Teams ~$29/user/mo** | **Strong** — automation bundle, not single feature |
| **Zapier Team** | Multi-app automation, shared workspaces | Flat + task caps | Professional ~$20/mo; **Team ~$69/mo** (annual) | **Strong** — recurring automation value |
| **Jasper Pro** | AI content, brand voice, knowledge assets | Per-seat/month | **$69/mo** monthly; $59/mo annual | **Moderate** — AI marketing content, not multi-agent ops |
| **HubSpot Marketing Hub Starter** | Email, forms, basic automation | Per-seat/month | ~$20/seat/mo | **Weak** — full CRM/marketing suite anchor |
| **HubSpot Marketing Hub Professional** | Campaigns, automation, reporting | Org/month | ~$800–890/mo + onboarding | **Weak** — enterprise marketing platform |
| **Salesforce Account Engagement (Pardot)** | B2B marketing automation on CRM | Org/month (annual) | From **$1,250/mo** | **Weak** — enterprise, not agent pack |
| **Salesforce Marketing Cloud Growth** | Agentic marketing automation edition | Org/month (annual) | **$1,500/mo** | **Weak** — enterprise suite |

**Patterns observed:** Genuinely comparable **automation bundles** use **flat or org-level monthly** pricing with usage/credit caps, not pure per-seat — because value is in the automation, not headcount. AI content tools (Jasper) use per-seat. Enterprise marketing clouds are poor anchors for a department agent pack.

**Price range for strong comparables:** roughly **$29–$69/month** at entry team tier; enterprise suites **$800+/mo** are weak matches.

**Gravitre positioning:** Department packs are **one-time unlocks** on top of the monthly platform plan and metered AI usage. Tier band amounts ($49 / $149 / $299) anchor to automation-bundle research but are not recurring pack subscriptions.

---

## Department Pack Pricing Framework (Phase 8.3)

**Codified in:** `backend/app/marketplace/pack_pricing.py`  
**Schema:** `marketplace_assets.pack_tier` (migration `20260709120000_marketplace_pack_tier.sql`)

### How billing is split (revised)

| Layer | Billing model | What it covers |
|-------|---------------|----------------|
| **Platform plan** | **Monthly subscription** | Node / Control / Command tier limits (agents, workflows, connectors, seats) |
| **AI usage** | **Metered / usage-based** | Model calls, operator sessions, run consumption per org plan |
| **Department pack** | **One-time purchase** (`pricing_type = paid`) | Permanent unlock + install of bundled agents, workflows, RAG, connector requirements |

Department packs are **not** recurring marketplace subscriptions. A customer on Control or Command pays their platform subscription and usage separately, then buys a pack once to install it.

### Pricing model chosen

**One-time flat unlock per org** (`pricing_type = 'paid'`), Stripe Checkout mode `payment`. Tier band dollar amounts anchor to automation-bundle research but are expressed as **permanent unlock fees**, not monthly pack rent.

### Tier eligibility (platform plans)

Department packs are purchasable add-ons for orgs on **Control or Command**. **Node** (and free) must upgrade first — Node limits (2 agents, 5 connectors) are insufficient for Tier 2 packs.

### Price banding by pack complexity (one-time)

| Tier | Profile | One-time price |
|------|---------|----------------|
| **1** | Single agent + 1–2 workflows (starter pack) | **$49** |
| **2** | Multi-agent chain + connector requirements | **$149** |
| **3** | Full department command-center + advanced feedback loops | **$299** |

### Marketing Operations Pack

**$149 one-time · Tier 2 · `paid`** — 4-agent chain target, connector dependencies, Mode A/B feedback complexity.

### Mode B pricing implication (product decision — not settled in code)

**Recommended:** Mode B included at base Tier 2 price with in-product risk-acknowledgment gate; optional **+$49 one-time add-on** if product differentiates autonomous replanning (`MODE_B_AUTONOMOUS_ADDON_CENTS`). No separate Stripe SKU until pack owner confirms.

### Trial/preview model

Reuse existing marketplace asset detail page — read-only preview before one-time purchase.

---

## Phase 8 — Implementation Summary

| Item | Action |
|---|---|
| `pack_tier` column | Added via `20260709120000_marketplace_pack_tier.sql` |
| Marketing Operations Pack price | `pricing_type=paid`, `price_cents=14900`, `pack_tier=2` |
| Checkout | Existing `create_asset_checkout_session()` — one-time `payment` mode |
| Tests | `backend/tests/marketplace/test_department_pack_pricing.py` |
| Live verification (8.7) | POST install without entitlement → `402 PAYMENT_REQUIRED` with one-time price; Stripe Checkout `payment` mode |

---

## Reusability Assessment (Phase 7.4)

| Finding | Reusable as-is | Marketing-specific |
|---|---|---|
| Graph + handoff agent chains | ✅ All department packs | — |
| `department_pack` marketplace type | ✅ | — |
| Partial batch approval | 🔧 Build once, all packs | — |
| Rejection → upstream routing | 🔧 Build once | — |
| **Mode A/B feedback toggle** | 🔧 **General primitive — build once** | Marketing is first consumer |
| UnifiedRetrievalService + RAG for brand | ✅ Pattern | Content varies per pack |
| Pack tier pricing framework | ✅ All paid packs | — |
| Subscription entitlement path | ✅ All paid packs | — |
| Connector gaps (LinkedIn publish, etc.) | — | Marketing-heavy; Sales may reuse LinkedIn |
| Post-publish engagement metrics loop | Partial | Marketing-first; Sales content possible |

**Uncertainty:** Tier eligibility gating at checkout not yet enforced in code — flag for next pack.

---

## Risks and Technical Debt Warnings

1. **Seed vs marketed scope:** Catalog ships 2 agents; brief describes 4-agent chain — risk of overpromising until content updated.
2. **Audit retention:** `retention_purge()` still deletes compliance-relevant approval events after retention window.
3. **Mode B:** Shipping without guardrails would be brand-risk; default Mode A until product sign-off.
4. **LinkedIn publishing:** High integration risk; do not imply autonomous cross-posting in copy until connector exists.
5. **CoordinationLayer killed:** Multi-agent coordination stays in swarm/workflow wrappers — no shared coordination layer to depend on.
6. **Linear execution naming:** Docs/code refer to ExecutionCore; implementation is AgentIntelligence — onboarding friction.
7. **Hours saved:** Still estimate-only; do not claim measured ROI until Phase 4 measurement distinction is wired to packs.

---

## Linear Tickets

Linear MCP/API key was **not available** in this environment (`LINEAR_API_KEY` unset). Ticket bodies are prepared in `scripts/create-marketing-pack-audit-linear-issues.mjs`. Run:

```powershell
$env:LINEAR_API_KEY="lin_api_..."
node scripts/create-marketing-pack-audit-linear-issues.mjs
```

Categories (to be filled with IDs after script run):

1. Phase 5–7 section tickets (5.1, 5.2, 6.1, 6.2, 7.1, 7.2, 7.3)
2. Dedicated Mode A/B decision ticket (product owner assignment required)
3. Consolidation discrepancy ticket (CoordinationLayer killed, ExecutionCore naming, audit retention)
4. Reusability tracking ticket (Mode A/B toggle as general primitive)
5. Department Pack Pricing Framework reference ticket
6. Marketing Operations Pack Stripe implementation ticket
