# Marketplace 3.0: department evidence depth

The six remaining department packs now have department-specific data contracts,
four operating standards each, multi-source Play workflows, and explicit IDs for
record-specific reviews. Existing catalog identities, prices, skill provenance,
dashboard visualization choices, OBSERVE installation, and publication gates are
preserved.

| Pack | Plays | Required v1 sources | Evidence focus |
| --- | ---: | --- | --- |
| Revenue Operations | 8 | HubSpot | Contacts, accounts, deals, stages, owners |
| Customer Success & Support | 8 | HubSpot + Zendesk | Commercial context, support cases, account mapping, customer themes |
| Finance Operations | 8 | QuickBooks + Stripe | Receivables, payments, vendors, ledger accounts, subscriptions, billing invoices |
| Marketing Operations | 8 | HubSpot | Campaigns, contacts, opportunities, funnel stages, attribution evidence |
| People & IT Operations | 8 | BambooHR + Freshservice | Employee lifecycle, service requests, identity mapping, readiness checklists |
| Executive Command Center | 8 | HubSpot + QuickBooks + Zendesk | Revenue, cash, service exposure, demand signals, accountable priorities |

MSP Service Desk and Security Operations retain their existing flagship builds.
Across all eight packs, the catalog declares 65 Plays, 24 agents, and 69 KPI
entries. Some KPI keys are shared across departments; 69 is not a count of unique
business metrics.

## Runtime behavior

- Canonical department Play readiness requires every evidence action in its
  workflow. Optional providers remain context options rather than substitutes
  for tested v1 sources.
- Deal, ticket, invoice, subscription, and employee reviews use explicit
  `param_sources` aliases and declared `runtime_inputs`. Record-specific reviews
  start manually; scheduled cohort reviews retain their existing cadences.
- Discovery requires every source used by a Play to be connected. It exposes
  missing systems and required runtime input names. Connection support does not
  assert that tenant inputs or data coverage are complete.
- Revenue Leak Hunter keeps its existing key and signature outcome metrics, but
  now requires the QuickBooks/Stripe evidence used by its Finance workflow.
  CRM and other finance providers remain optional context. A duplicate template
  with the same key is removed to prevent lookup-order-dependent readiness.
- Knowledge standards and agent instructions require verified cross-system
  identity mappings, aligned reporting windows, source references, and explicit
  handling of missing data. Prepared reviews cannot assert delivered actions or
  measured business improvements.

## Measurement boundaries

Dataset entities are normalized contracts, not new ingestion adapters. A field
declared in a dataset is not proof that a provider read supplies it. Tenant
custom properties, source associations, historical snapshots, contract data,
quota, attribution policy, and currency policy must be supplied and verified
where relevant. Existing `verified_metric` formulas continue to consume verified
outcome measurements; this change does not fabricate measurements or baselines.

Operating standards install as knowledge-source metadata pending tenant upload,
consistent with the existing knowledge installer. Their guidance is also included
in agent purposes and Play analysis instructions so the workflows retain the
measurement boundaries before tenant documents are uploaded.

Finance must reconcile Stripe and accounting records before summing exposure.
Marketing must retain its attribution model and cannot infer spend or ROAS from
CRM campaign context. People/IT service records cannot prove live access,
device posture, or license usage without authoritative evidence. Current
snapshots cannot prove trends, conversion rates, or causal improvement.

## Certification and next gate

The reproducible portfolio report is available at
`GET /api/marketplace/platform/marketplace3/portfolio-readiness` (platform admin).
All eight seeded packs pass existing fixture certification and remain governed,
internal, and draft. Zero have live Production Verified or Outcome Verified
evidence in the source catalog.

Continue through Revenue, Customer Success, Finance, Marketing, People/IT, and
Executive in that order:

1. Refresh the seeded internal catalog through the normal seed path. Verify
   companion components match the parent configuration.
2. Install in an authorized tenant with the required v1 connections; supply real
   record IDs and tenant policies. Verify OBSERVE mode, source reads, missing-ID
   failure, partial-source failure, tenant isolation, and archival on uninstall.
3. Collect production Run references and source-linked verification for the
   declared runtime actions. No fixture Run counts as production proof.
4. Submit actual evidence through
   `POST /api/marketplace/platform/assets/{asset_ref}/marketplace3/certify-run`.
   Installation-harness assertions must describe observed checks.
5. Record an aligned baseline and verified business result before requesting
   Outcome Verified. Review preparation alone is activity evidence.
6. Use the existing `marketplace3/promote` endpoint only when its evidence gate
   passes. Existing public packs and legacy offerings are not deleted or relabeled.

Regression checks cover all department config schemas, skill digests, bundle
consistency, canonical action readiness, explicit parameter bindings, duplicate
Play keys, partial-source discovery, and the existing Marketplace installation
and certification tests. This change does not modify customer-facing chart code.

Validation on this change: all 665 Marketplace tests pass; the focused
Marketplace/Play readiness regression run also passes (58 tests).
