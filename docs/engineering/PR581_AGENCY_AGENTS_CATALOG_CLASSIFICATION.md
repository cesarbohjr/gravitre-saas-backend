# Agency Agents → Gravitre catalog classification (PR #581)

Status: **initial sourced inventory and proposed tiers, not installed agents**. Source: https://github.com/msitarzewski/agency-agents (README roster, reviewed 2026-10-27; upstream is MIT-licensed). Pin a commit and audit individual files before importing. Classification is provisional until product approval and automated collision checks against the current marketplace catalog.

## Canonical boundary

PR #581 owns role inventory, specialist manifests, provenance, default/marketplace classification, marketplace metadata and compatibility tests. PR #587 owns shared dialogue, seven-capability reasoning, personality, memory and voice. No duplicate agent selector or intelligence router in #581. Existing `marketplace_assets` / `ai_agent` / `department_pack` flows are canonical; no new marketplace subsystem.

## Initial roster mapping

| Upstream Agency Agents role | Proposed tier | Gravitre target / action | Reason / gate |
|---|---|---|---|
| Backend Architect | Default capability | Engineering Agent — enrich | Avoid duplicate engineering operator |
| Frontend Developer | Default capability | Engineering Agent — enrich | Same engineering surface |
| Code Reviewer | Default capability | QA / Engineering — enrich | Review expertise, not separate privileges |
| DevOps Automator | Default capability | Engineering / Operations — enrich | Existing CI/deploy approvals remain authoritative |
| Software Architect | Default capability | Engineering — enrich | Architecture guidance only |
| Technical Writer | Default capability | Research / Operations — enrich | Broad cross-functional use |
| Data Engineer | Marketplace agent | Data/Analytics department pack | Requires data-source readiness and plan entitlement |
| AI Engineer | Marketplace agent | Engineering/AI specialist | Narrow advanced expertise |
| Database Optimizer | Marketplace agent | Engineering/Database specialist | Restrict schema/write operations through existing gates |
| SRE | Marketplace agent | Operations/Reliability specialist | No autonomous production changes |
| Incident Response Commander | Marketplace agent | Operations/Incident pack | Existing incident workflows and approvals |
| Mobile App Builder | Marketplace agent | Engineering/Mobile pack | Specialized platform scope |
| Voice AI Integration Engineer | Marketplace agent | Engineering/Voice pack | Distinct from #587 voice dialogue infrastructure |
| Payments & Billing Engineer | Marketplace agent | Finance/Engineering pack | Payment and PCI-related actions remain gated |
| Network Engineer | Marketplace agent | IT/Network pack | Sensitive infrastructure actions require approval |
| Solidity Smart Contract Engineer | Marketplace agent | Engineering/Web3 pack | Security audit and no financial execution by default |
| Embedded Firmware Engineer | Marketplace agent | Engineering/Embedded pack | Niche hardware specialization |
| Filament Optimization Specialist | Marketplace agent | Engineering/PHP pack | Stack-specific, not universal |
| WeChat Mini Program Developer | Marketplace agent | Engineering/WeChat pack | Platform-specific |
| Drupal Shopping Cart Engineer | Marketplace agent | Commerce/Drupal pack | Platform-specific |
| WordPress Shopping Cart Engineer | Marketplace agent | Commerce/WordPress pack | Platform-specific |
| Git Workflow Master | Marketplace agent | Engineering/Git specialist | Default engineering already handles standard Git |
| Codebase Onboarding Engineer | Default capability | Engineering — enrich | Safe read-only baseline |
| Minimal Change Engineer | Default capability | Engineering — enrich | General regression minimization |
| Prompt Engineer | Marketplace agent | AI Operations specialist | Advanced prompt operations |
| Multi-Agent Systems Architect | Marketplace agent | Engineering/AI systems pack | Does not replace One Brain |
| Autonomous Optimization Architect | Marketplace agent | AI Operations pack | Provider cost guardrails, no independent orchestrator |
| Email Intelligence Engineer | Marketplace agent | Operations/Email pack | Consent and connector restrictions |
| IT Service Manager | Marketplace agent | IT/Service pack | Reuse existing workflow engine |
| Rapid Prototyper | Marketplace agent | Product/Engineering pack | Optional development workflow |
| Senior Developer | Marketplace agent | Engineering/PHP pack | Laravel-specific upstream role |
| CMS Developer | Marketplace agent | Content/CMS pack | Stack-specific |
| Feishu Integration Developer | Marketplace agent | Integration/Feishu pack | Connector readiness required |
| OrgScript Engineer | Exclude pending review | None | Domain-specific upstream grammar not verified in Gravitre |
| AI Data Remediation Engineer | Marketplace agent | Data/Remediation pack | High-risk data writes gated |

This is a **first engineering-division tranche**, not a complete census of all Agency Agents divisions. Next inventory design, product, project management, research, strategy, sales, marketing, support, finance, security, testing, and remaining specialized divisions; dedupe by normalized function and existing `marketplace_assets` slugs, not merely by title. A role classified Default capability does not automatically become a separately selectable built-in agent.

## Required implementation gates

1. Produce a machine-readable full upstream manifest with source file path, immutable revision, license, division, display name, slug, role capabilities, workflows, intended Gravitre target, tier and conflict disposition.
2. Compare against published Gravitre agent/department-pack assets and existing operators; choose `enrich_existing`, `new_default`, `marketplace_agent`, `marketplace_pack`, or `exclude`. Do not clone existing roles.
3. Curate a product-approved built-in shortlist spanning Executive, Sales, Marketing, Customer Success, Operations, Engineering, QA, Security and Research; do not assume all upstream roles are appropriate defaults.
4. Implement marketplace packages through existing publish/install/entitlement/version/rollback lifecycle. Preserve org isolation, permissions, connector readiness, plan and MSP governance.
5. Sanitize external persona/workflow text as untrusted data. Role descriptions never grant tool rights. Do not import install scripts or autonomous action policy.
6. Remove #581 shared prompt/router changes or transfer their ownership to #587; preserve compatibility contract and tests.
7. Run catalog validation, idempotent install/upgrade/rollback tests, cross-tenant negative tests, regression suite and full CI on the final branch. Merge #581 first only when green; then rebase #587 and retest. No production deployment or new service as part of inventory.
