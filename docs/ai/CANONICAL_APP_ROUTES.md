# Canonical App Routes (binding)

Last updated: 2026-07-03.

| Capability | Route |
|------------|-------|
| Gravitre AI | `/ai` |
| Workspace chat mode | `/ai?mode=chat` |
| Universal Search | `/search` |
| Agents | `/agents` |
| Agent capabilities | `/agents/[id]/capabilities` |
| Agent knowledge | `/agents/[id]/knowledge` |
| Workflows | `/workflows` |
| Connectors | `/connectors` |
| Runs | `/runs` |
| Approvals | `/approvals` |
| Intelligence Center | `/intelligence` |
| Org Learning Admin | `/admin/intelligence` |
| Marketplace | `/marketplace` |

## Legacy redirects (do not link in UI)

| Legacy | Redirect |
|--------|----------|
| `/operator`, `/command-center`, `/assistant` | `/ai` |
| `/chat` | `/search` |
| `/agents/swarm` | `/multi-agent-run` |
| `/integrations` | `/connectors` |
| `/onboarding` | `/welcome` |
| `/tasks` | `/runs` |
| `/systems` | `/connectors` |

Source of truth: `apps/web/lib/app-routes.ts`
