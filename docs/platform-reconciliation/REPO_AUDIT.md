# Platform Reconciliation — Repository Audit

## Summary
The Cursor codebase implements the core Gravitre platform (operators, workflows, runs, approvals, audit, metrics, RAG, integrations, schedules). The v0 prototype overlaps substantially but introduces route naming conflicts (`/connectors`) and adds UI elements not present in Cursor (stats cards, filter bars).

Primary routing is defined by the app shell navigation:
```14:51:apps/web/components/app-shell.tsx
const NAV_GROUPS: NavGroup[] = [
  { label: "Operate", items: [ { label: "AI Operator", href: "/operator" }, { label: "Agents", href: "/agents" } ] },
  { label: "Build", items: [ { label: "Workflows", href: "/workflows" }, { label: "Integrations", href: "/integrations" }, { label: "Sources", href: "/sources" } ] },
  { label: "Run", items: [ { label: "Runs", href: "/runs" }, { label: "Approvals", href: "/approvals" } ] },
  { label: "Observe", items: [ { label: "Metrics", href: "/metrics" }, { label: "Audit", href: "/audit" } ] },
  { label: "Admin", items: [ { label: "Environments", href: "/environments" }, { label: "Settings", href: "/settings" } ] },
];
```

Backend router inventory (FastAPI):
```122:134:backend/app/main.py
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(org.router)
app.include_router(connectors.router)
app.include_router(rag.router)
app.include_router(rag_admin.router)
app.include_router(workflows.router)
app.include_router(workflows.approvals_router)
app.include_router(audit.router)
app.include_router(metrics.router)
app.include_router(operator_router.router)
app.include_router(operators_router.router)
```

## 1) v0 pages that already map to backend APIs

- `/operator` → operator runtime + sessions + action plans (operator/routers)
- `/chat` → RAG retrieve UI (`/api/rag/retrieve`)
- `/agents` → operators CRUD (`/api/operators`)
- `/workflows` → workflow defs list (`/api/workflows`)
- `/workflows/[id]` → workflow detail/versioning/dry-run/execute
- `/workflows/[id]/schedules` → workflow schedules (`/api/workflows/:id/schedules`)
- `/runs` + `/runs/[id]` → workflow runs list/detail (`/api/workflows/runs`)
- `/approvals` → run approvals (`/api/approvals`)
- `/metrics` → metrics endpoints (`/api/metrics/*`)
- `/audit` → audit log (`/api/audit`)
- `/integrations` + `/integrations/[id]` + `/integrations/new` → integrations CRUD (`/api/integrations`)
- `/sources` → redirects to `/rag/sources` (sources UI is implemented under `/rag/*`)

## 2) UI-only pages missing backend support

- `/environments` → placeholder UI only (no backend management)
```7:31:apps/web/app/environments/page.tsx
<CardTitle className="text-lg">Environments</CardTitle>
... "Coming soon."
```

- `/settings` → placeholder UI only (no backend settings model)
```7:31:apps/web/app/settings/page.tsx
<CardTitle className="text-lg">Settings</CardTitle>
... "Coming soon."
```

## 3) Backend modules with no UI surface

- Org membership admin endpoints (`/api/org/members`) exist, but no UI page.
- Operator links (new BE table + endpoints) do not have a UI yet.

## 4) Reusable v0 components vs Cursor equivalents

| v0 Component | Cursor Equivalent |
|-------------|-------------------|
| AppShell | `apps/web/components/app-shell.tsx` |
| Sidebar / TopBar | Same AppShell layout |
| StatusBadge | Local badge components in runs pages (not shared) |
| EnvironmentBadge | Not a shared component (environment text only) |
| DataTable | Standard `<table>` usage, no shared DataTable component |
| SessionItem | `OperatorSessionItem` |
| ReasoningBlock | `ReasoningBlock` |
| ActionCard / ActionProposal | `ActionProposalCard` |
| ContextPack | `ContextPackCard` |
| GuardrailsBox | `ContextPanel` + `GuardrailBadge` |
| VendorLogo | No matching component in Cursor |

Refs:
```1:19:apps/web/features/operator/components/index.ts
export { ActionProposalCard } from "./action-proposal-card";
export { ContextPanel, ContextPackCard, GuardrailBadge } from "./context-panel";
export { OperatorSessionItem } from "./operator-session-item";
export { ReasoningBlock } from "./operator-workspace";
```

## 5) Route conflicts or mismatches

- v0 uses `/connectors` but Cursor has **Integrations**; `/connectors` is a redirect to `/integrations`.
- v0 uses `/sources`; Cursor implements sources under `/rag/sources` with `/sources` redirect.
- v0 includes UI elements (stats cards, filters) not in Cursor Workflows list.
