# Domain Retrieval — Wave C1+C2

Status: **Implemented** (2026-07-04).

## Architecture

Single retrieval hot path:

```text
DomainRetrievalPolicy → UnifiedRetrievalService → ContextPrioritizationEngine
```

Both **Assistant Chat** (`IntelligenceOrchestrator`) and **Intelligence Router** (`ContextAssembler`) consume the same policy and service.

## Feature flag

`DOMAIN_RETRIEVAL_POLICY_ENABLED` — default `true` in dev/local; env-controlled in production.

## Assignment alignment

New nullable columns on `agent_knowledge_assignments`:

- `department`
- `subdomain`
- `confidence_weight` (default 1.0)

## Filter priority (when domain active)

1. `assignment_id`
2. `source_id`
3. department/subdomain match
4. label fallback (low confidence / non-strict only)

`require_assigned_only` defaults to **false**. Use `strict_assignment_mode=true` for enterprise strict mode.

## Marketplace intelligence packs

- `marketing-intelligence-pack`
- `sales-intelligence-pack`
- `support-intelligence-pack`
- `msp-intelligence-pack`

Install via `app.marketplace.intelligence_packs.install.install_intelligence_pack`.

## Outcome metadata

Every response records `retrieval_effectiveness` in outcome metadata for future adaptive/meta learning.

## Future hooks (reserved on RetrievalPlan)

- `adaptive_weight_delta`
- `meta_learning_delta`
- `freshness_multiplier`
- `outcome_multiplier`
- `optimization_multiplier`
