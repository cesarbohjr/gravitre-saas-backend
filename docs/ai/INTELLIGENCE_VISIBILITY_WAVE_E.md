# Wave E — Enterprise Intelligence Visibility

Wave E makes Gravitre intelligence understandable, measurable, auditable, and executive-friendly without exposing chain-of-thought or internal reasoning.

## Scope (E1 + E2)

- `DecisionTransparencyEnvelope` — unified per-decision visibility schema
- `IntelligenceVisibilityService` — single read-only aggregation facade
- `ExecutiveIntelligenceScoringService` — centrally weighted executive score
- `IntelligenceMaturityService` — maturity levels 1–5
- Sanitization layer — strips CoT, prompts, deliberation, consensus internals
- Visibility APIs under `/api/intelligence/visibility/*`
- Router + orchestrator integration

## Feature flag

`INTELLIGENCE_VISIBILITY_ENABLED` — independent from domain retrieval and adaptive learning flags.

Auto-enabled in dev/local when unset (same pattern as other intelligence flags).

## API routes

### Org member

- `GET /api/intelligence/visibility/explainability`
- `GET /api/intelligence/visibility/trust-health`
- `GET /api/intelligence/visibility/maturity`

### Admin only

- `GET /api/intelligence/visibility/learning-health`
- `GET /api/intelligence/visibility/domain-health`
- `GET /api/intelligence/visibility/knowledge-health`
- `GET /api/intelligence/visibility/executive`

Admin learning/freshness/optimization internals remain at `/api/admin/intelligence/*`. Visibility consumes those systems rather than duplicating them.

## Executive scoring weights (defaults)

| Component     | Weight |
|---------------|--------|
| Trust         | 30%    |
| Learning      | 25%    |
| Freshness     | 20%    |
| Optimization  | 15%    |
| Domain Health | 10%    |

Weights live in `ExecutiveIntelligenceScoringService` and can evolve without API redesign.

## Maturity model

1. **Connected** — integrations and knowledge sources connected
2. **Learning** — outcome and learning signals collected
3. **Adaptive** — confident domain-segment adaptations
4. **Optimizing** — freshness, retrieval, and optimization loops active
5. **Autonomous Intelligence** — mature cross-domain intelligence with strong trust and workflow adoption

## Alternative paths (evidence only)

Per decision envelope:

```json
{
  "alternative_strategy_count": 3,
  "selected_strategy": "marketing:seo",
  "guidance_strength": 0.22
}
```

Never exposed: deliberation, model reasoning, consensus discussion, rejected chain-of-thought.

## Extension points (reserved)

`DecisionTransparencyEnvelope.extension_points`:

- `wave_f_multi_agent_explainability`
- `wave_g_simulation_transparency`
- `wave_h_autonomous_research_visibility`

## Later sub-waves (not E1/E2)

- Frontend: `/intelligence/reports`, Intelligence Center health grid
- Agent profiles: `/agents/[id]` and `/intelligence/agents/[id]`
- Admin learning trends UI
