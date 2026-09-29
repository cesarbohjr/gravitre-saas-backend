# 08 — AI-native interaction architecture

## Product philosophy (binding)

1. **AI is the primary intent layer** — Ask / voice / float runtime  
2. **Adaptive UI is the contextual work surface** — artifacts, inspectors, field, builder  
3. **Expert workspaces remain** — full Workflows, Intelligence, Agents, Connectors  
4. **Do not collapse the product into chat**  
5. **One coherent environment** — not bolted chat widgets on SaaS pages  

## Layers

```
Intent (composer / voice / summon)
    ↓
Shared runtime (conversation, taskState, approvals)  ← Functional SoT
    ↓
Presentation (Window Manager modes)
    ↓
Adaptive surfaces (work canvas, TRACE, Field, builder)
    ↓
Expert routes (full pages when user needs control)
```

## Entry points (target)

| Entry | Role |
|-------|------|
| Ask Gravitre / helper / `/ai` | Global intent |
| Selection-contextual Ask | Object → question |
| Meson | **Workflow-builder-local** copilot only |
| Page chrome CTAs | Summon same runtime — no second brain |

## Adaptive surface triggers (real data only)

| Signal | Surface |
|--------|---------|
| Artifact / deliverable present | Work canvas |
| Pending approval | Approval chrome |
| Execution in progress | Progress / TRACE (honest states) |
| Intelligence selection | Inspector + Ask |
| Empty / sparse / error | Honest empty — no invented nodes |

## Forbidden

- Fake streaming progress, confidence, or completed work  
- Parallel chat products (assistant-ui / CopilotKit shells)  
- Mode change that remounts conversation state
