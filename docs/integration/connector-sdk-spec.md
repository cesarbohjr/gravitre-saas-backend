# Gravitre Connector SDK Specification (STA-70)

**Version:** 1.0  
**Status:** Draft — Tier 3 marketplace foundation  
**Linear:** [STA-70](https://linear.app/staqbot/issue/STA-70)

This document defines how third-party partners package connectors for the Gravitre marketplace. First-party integrations (HubSpot, Salesforce, etc.) follow the same `invoke_tool` contract but ship in-repo.

---

## Package layout

```
acme-tools/
├── manifest.json          # Required — declarative connector metadata
├── handlers.py            # Python action implementations (hosted runtime)
└── README.md              # Partner setup notes
```

For marketplace submission (STA-71), partners upload a zip of this structure. Gravitre validates `manifest.json`, runs security review, and registers handlers in the partner registry.

**Example:** `docs/integration/examples/acme-tools/manifest.json`

---

## manifest.json

### Top-level fields

| Field | Required | Description |
|-------|----------|-------------|
| `manifestVersion` | yes | Must be `"1.0"` |
| `id` | yes | Reverse-DNS package id, e.g. `com.acme.tools` |
| `name` | yes | Display name |
| `version` | yes | Semver of this package |
| `vendor` | yes | Lowercase slug used in action keys and connector rows |
| `description` | no | Short summary |
| `auth` | yes | `oauth2` or `apiKey` (see below) |
| `capabilities` | no | `actions`, `triggers`, `sync`, `rag` |
| `actions` | if `actions` capability | Tool definitions |
| `triggers` | if `triggers` capability | Workflow trigger definitions |
| `minPlatformVersion` | no | Minimum Gravitre platform release |
| `homepageUrl` | no | Partner docs |
| `supportEmail` | no | Partner support contact |

### Auth: OAuth2

```json
{
  "type": "oauth2",
  "authorizationUrl": "https://provider.example/oauth/authorize",
  "tokenUrl": "https://provider.example/oauth/token",
  "scopes": ["read", "write"],
  "refreshSupported": true
}
```

OAuth connectors use the shared platform flow (`app/connectors/platform.py`). Partners register redirect URL:

`{API_PUBLIC_URL}/api/connectors/oauth/{vendor}/callback`

### Auth: API key

```json
{
  "type": "apiKey",
  "headerName": "X-Acme-Api-Key",
  "prefix": "Bearer"
}
```

API keys are stored in `connector_secrets` via `CONNECTOR_SECRETS_ENCRYPTION_KEY`.

---

## Actions

Each action becomes an `invoke_tool` entry at **`{vendor}.{action.id}`**.

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Lowercase id, e.g. `tickets.list` |
| `name` | yes | Human label |
| `description` | no | Agent/workflow UI hint |
| `scopes` | no | Permission scopes (defaults to `{vendor}:*`) |
| `inputSchema` | no | JSON Schema for params |
| `outputSchema` | no | JSON Schema for result `data` |
| `idempotent` | no | Safe to retry |
| `destructive` | no | Mutates external state |

**Example action key:** `acme_tools.tickets.list`

---

## Triggers

Triggers declare inbound events that can start workflows (webhook, poll, or push).

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | e.g. `ticket.created` |
| `name` | yes | Display label |
| `eventType` | no | `webhook` (default), `poll`, `push` |
| `scopes` | no | Required agent permissions |

Workflow binding uses the same execution path as Tier 1/2 triggers (`STA-12`).

---

## invoke_tool adapter contract

All actions — first-party and partner — execute through `invoke_tool(ctx, action, params)`:

### ToolContext

| Field | Description |
|-------|-------------|
| `settings` | App configuration |
| `client` | Supabase service client |
| `org_id` | Tenant org |
| `actor_id` | User or system actor |
| `environment_name` | `production`, `staging`, etc. |
| `agent_id` | Set when invoked from an agent (enables permission check) |
| `connector_id` | Optional bound connector |

### NormalizedResult

Handlers return:

```python
NormalizedResult(
    success=True,
    action="acme_tools.tickets.list",
    data={"tickets": [...]},
    connector_id="...",
)
```

On failure, set `success=False`, `error_code`, `error_message`. Prefer raising `ToolValidationError`, `ToolAuthExpiredError`, or `ToolRateLimitedError` for built-in classification.

### Python handler interface

```python
from app.connectors.sdk import BaseConnectorHandler, register_from_manifest, parse_manifest
from app.services.tool_types import NormalizedResult, ToolContext

class AcmeHandler(BaseConnectorHandler):
    def __init__(self) -> None:
        super().__init__("acme_tools")

    def tickets_list(self, ctx: ToolContext, params: dict) -> NormalizedResult:
        self.require_params(params, "connector_id")
        # ... call vendor API with decrypted secret ...
        return self.ok("acme_tools.tickets.list", {"tickets": []}, connector_id=params["connector_id"])

manifest = parse_manifest({...})
register_from_manifest(manifest, {
    "tickets.list": AcmeHandler().tickets_list,
})
```

**Modules:**

| Path | Role |
|------|------|
| `backend/app/connectors/sdk/manifest.py` | Pydantic validation |
| `backend/app/connectors/sdk/registry.py` | Partner registration |
| `backend/app/connectors/sdk/loader.py` | Load from `manifest.json` |
| `backend/app/services/tool_service.py` | Unified `invoke_tool` |

### TypeScript types (UI / marketplace)

`apps/web/lib/connector-sdk/types.ts` — use for marketplace admin UI and connector catalog generation.

---

## Versioning

| Layer | Rule |
|-------|------|
| `manifestVersion` | Bumped only for breaking manifest schema changes |
| Package `version` | Semver per partner release |
| `minPlatformVersion` | Gravitre release gate (e.g. `2026.06`) |
| Action `id` | Stable; add new ids instead of renaming |

Breaking changes to action input/output require a new action id or major package version.

---

## Capabilities

| Capability | Meaning |
|------------|---------|
| `actions` | Agent/workflow tools via `invoke_tool` |
| `triggers` | Inbound events → workflow runs |
| `sync` | Scheduled knowledge/entity sync |
| `rag` | Documents ingested into department RAG |

Declare only capabilities you implement. The platform rejects manifests that claim `actions` with an empty `actions` array.

---

## Security & permissions

- Agent invocations require scopes in `agent_tool_permissions` (`STA-11`).
- Manifest `scopes` are registered in `ACTION_REQUIRED_SCOPES` at load time.
- Secrets never appear in audit logs or `NormalizedResult.data`.
- Public marketplace packages run in the Gravitre backend process.
- **Private org bundles** (STA-98) run in an isolated subprocess sandbox — see `private-connector-runtime.md`.

---

## Related docs

- `CONNECTOR_PLATFORM.md` — first-party OAuth/API key connect flow
- `LINEAR_INTEGRATION_BACKLOG.md` — Tier 3 execution order
- STA-71 — Partner submission workflow (`/marketplace/submit`, `/marketplace/admin`)
- STA-72 — Partner sandbox org (`/marketplace/sandbox`) with Acme Tools demo handlers
- STA-97 — Certified partner program: automated static analysis + scope review on submit; **Gravitre Certified** badge in registry when scan passes
- STA-72 — Sandbox org for partner QA
- STA-73 — Marketplace demo
