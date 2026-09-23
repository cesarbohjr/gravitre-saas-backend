# 00 — Ownership and conflict matrix

**Frontend track:** `feat/gravitre-3.0-plus-frontend` worktree  
**Functional track:** Platform Execution 3.0 (current slice: 3.0-D finished-work artifacts) on `main` / functional agent

## Ownership

| Domain | Owner | Notes |
|--------|-------|-------|
| Window Manager UI (modes, shells, morph) | Frontend 3.0 Plus | Must not reset conversation/task/voice/approval state |
| Design system / Nodus / Nucleo / motion tokens | Frontend 3.0 Plus | Proposals only until Cesar gate |
| Route chrome, page intros, Matrix→Field visual | Frontend 3.0 Plus | Prototype in harness first |
| Workflow **visual** canvas (React Flow adoption) | Frontend 3.0 Plus | Canonical schema remains backend-owned |
| Cognitive runtime, ExecutionPlan, ActionSpec/HMAC, PendingAction | Functional | Do not change authority |
| Observations, Response Composer, SSE/API contracts | Functional | UI may consume; may not redefine |
| Durable deliverable schema / lifecycle | Functional | Frontend renders authoritative states only |
| Voice execution runtime | Functional | Presentation modes must preserve voice state |

## Shared / collision files (do not independently rewrite on this branch without coordination)

### Hard conflict — functional agent active

| Path | Why |
|------|-----|
| `apps/web/app/ai/_components/ai-workspace.tsx` | Sole `useChat` owner; taskState |
| `apps/web/components/gravitre/assistant/chat-execution-panel.tsx` | Artifacts / finished work |
| `apps/web/components/gravitre/ai-work-canvas.tsx` | Work canvas beside conversation |
| `apps/web/components/gravitre/assistant/task-side-panel.tsx` | Task side panel |
| `apps/web/lib/gravitre-command-os.ts` | Artifact presence rules |
| `apps/web/app/api/chat/route.ts` | Chat API bridge |
| Backend `*_turn*`, `durable_work_session*`, `react_write_gate*`, Observation / Composer services | Functional SoT |

### Soft conflict — coordinate before production edits

| Path | Why |
|------|-----|
| `apps/web/components/gravitre/ai-workspace-provider.tsx` | Presentation + summon |
| `apps/web/lib/gravitre-ai-presentation.ts` | Mode vocabulary |
| `apps/web/components/gravitre/ai-floating-workspace.tsx` | Compact/float shell |
| `apps/web/app/approvals/page.tsx` | PendingAction UI |
| `apps/web/app/activity/page.tsx` | Outcomes / TRACE |
| `apps/web/app/workflows/[id]/builder/page.tsx` | Canvas + Meson; schema persistence |

### Frontend-owned (safe for harness / docs / isolated prototypes)

| Path | Why |
|------|-----|
| `docs/design/3.0-plus/**` | This package |
| `apps/web/app/dev/ai-workspace-preview/**` | Design harness |
| New prototype-only components under harness | Not production routes |

## Integration rule

Prototype UI against documented contracts. Never invent finished artifacts or parallel deliverable lifecycles for production.
