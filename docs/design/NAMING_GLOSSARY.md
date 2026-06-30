# Gravitre — User-facing naming glossary

Approved terminology for customer-facing docs (Part 2). **Routes, API paths, code identifiers, and analytics event names are unchanged** unless noted.

Use the **Docs name** column in all public documentation. **Code / route** column is for engineering reference only.

## Part 1 — Nav renames (shipped)

| Docs name | Former label | UI location | Code / route (unchanged) |
|-----------|--------------|-------------|---------------------------|
| **Multi-Agent Run** | Agent Swarm | Sidebar, `/agents/swarm` | `/agents/swarm`, `/api/agent-swarm` |
| **Multi-agent run** | Agent swarm / swarm run | Page body, toasts | Same |
| **AI Models** | Model Registry | Sidebar, `/models` | `/models`, `/api/ml` |
| **Workflows** | Automations | Sidebar | `/workflows` |
| **Connectors** | Apps | Sidebar | `/connectors` |
| **Sources** | Data | Sidebar | `/sources` |
| **Runs** | Tasks (nav) | Sidebar → `/runs` | `/runs` |
| **Metrics** | Dashboard | Sidebar | `/metrics` |
| **Environments** | Workspaces / System Topology | Settings nav, page h1 | `/environments` |

## Part 2 — Feature names (docs; UI may still show legacy labels)

| Docs name | Former / code label | Notes |
|-----------|----------------------|--------|
| **Meson** | Meson | **Brand name — do not rename** |
| **Partner Connections** | Federation | Settings route may still be `/settings/federation` |
| **Shared connector access** | Connector grants | Partner Connections sub-feature |
| **Org Learning** | Intelligence | Admin area `/admin/intelligence` |
| **Save to team knowledge** | Memory promotion | Org Learning action |
| **Expert Review** | Agent Council | Workflow builder node |
| **Simulation preview** | Digital twin | Workflow pre-run UI |
| **Integration health** | Command Center | Enterprise settings tab (CS dashboard) |
| **Security log export** | SIEM Export | Enterprise tab |
| **Failure predictions** | Failure Alerts | Nav → `/workflows/failure-predictions` |
| **Assistant** | Assistant | `/assistant`, `/api/assistant/*` |
| **Search** | Search (nav) | Route `/chat`, `/api/search` |
| **Assignments** | Assignments | `/assignments` |
| **Goals** | Goals | `/goals`, `/api/goals/*` |
| **History** | History / Audit | Route `/audit`, `/api/audit` |
| **Gravitre Lite** | Lite | `/lite/*`, `/api/lite/*` |
| **Settings** | Settings | `/settings/*` hub |

## Legacy / avoid in new docs

| Prefer | Legacy | Notes |
|--------|--------|--------|
| **Runs** | Tasks page (`/tasks`) | Document Runs only; Tasks is legacy assignments UI |
| **Environments** | Workspaces | Retired in nav and public docs |
| REST at `gravitre.app/api` | `api.gravitre.app/v1`, fake SDKs | No published Node/Python SDK yet |

## Open questions

- **Search** nav vs `/chat` route
- **Plan tier marketing names** (Node / Control / Command) — kept as-is in billing docs
- **Command palette “Dashboard”** → home (`/`), not Metrics

## Support migration

“Where did Agent Swarm go?” → **Multi-Agent Run**, same sidebar location (WORK).  
“Model Registry?” → **AI Models**, same `/models` route.
