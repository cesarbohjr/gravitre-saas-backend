# GRAVITRE_COMPONENT_REGISTRY.md

**Authority:** Subordinate to `GRAVITRE_3_0_PLUS_MASTER_SPEC.md` (§§5.2, 33).  
**Phase:** 5 consolidation — audit-first; consolidate before inventing.

## Rule

AI adaptive UI selects only from approved Gravitre primitives. Do not create duplicates if equivalents exist.

## Conceptual registry (target names → existing / gap)

| Concept | Existing / direction |
|---------|----------------------|
| GravitreWindow | `ai-workspace-provider` + floating/shell — consolidate via Window Manager |
| GravitreConversation | `ai-workspace` / assistant panels — functional SoT |
| GravitrePromptBar | Composer in AI workspace |
| GravitreTask | Task side panel / taskState — functional |
| GravitreExecution | Execution panel / run overlays |
| GravitreApproval | Approvals + in-chat chrome |
| GravitreArtifact | Work canvas / durable deliverables — functional schema |
| GravitreInsight / Metric / Evidence / Recommendation / Diff | Creative grammar + Intelligence inspectors — extend |
| GravitreWorkflowPreview | Compact preview → Open in Builder (§17.4) — prototype |
| GravitreAgentActivity | Activity TRACE / agent history |
| GravitreContext | Context / inspector panels |
| GravitreOrb / Wave | Canonical voice visuals — retain |
| ShowWork* | Placement reserved (`docs/design/3.0-plus/12-show-the-work-placement.md`) — **no live impl yet** |

## Adaptive renderers (§5.2)

Conversation, Insight, Metric, Chart, Table, Timeline, Workflow preview, Approval, Task, Recommendation, Artifact, Evidence, Entity, Diff, Execution state, Context panel, Inspector, Generated form.

## Workflow nodes

Custom Gravitre nodes on React Flow (Option B target) — Nodus/emerald/Nucleo, not stock RF demos.
