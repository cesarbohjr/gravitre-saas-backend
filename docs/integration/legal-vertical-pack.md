# Legal vertical pack (STA-114)

Industry pack for law firms: Clio OAuth read tools, intake and conflict review agent templates, and an intake → conflict check → task assignment workflow.

## Prerequisites

- [Agent tool permissions (STA-11)](./agent-tool-permissions.md)
- [Connector OAuth (STA-10)](./connector-oauth.md)

## Install

```http
POST /api/verticals/legal/install
Authorization: Bearer <admin-token>
```

Installs:

| Asset | Description |
|-------|-------------|
| Clio Demo connector | Sample contacts/matters until OAuth is connected |
| Intake Coordinator Agent | Routes inquiries and launches conflict screening |
| Conflict Review Agent | Reviews Clio history for potential conflicts |
| Intake workflow | Contact/matter lookup → conflict review → checklist → tasks |

```http
GET /api/verticals/legal
```

Returns install status and stable resource IDs.

## Clio OAuth

Register a Clio Manage app and set:

| Variable | Description |
|----------|-------------|
| `CLIO_CLIENT_ID` | OAuth client id |
| `CLIO_CLIENT_SECRET` | OAuth client secret |

Redirect URI: `{API_PUBLIC_URL}/api/connectors/oauth/clio/callback`

Scopes: `contacts_read`, `matters_read`

Connect a production Clio connector via the Connectors UI or API (`vendor: clio`). The demo connector installed by the vertical pack uses `sandbox: true` and does not require OAuth.

## Clio tools

| Action | Description |
|--------|-------------|
| `clio.contacts.search` | Search contacts by name or email |
| `clio.contacts.get` | Read contact by id |
| `clio.matters.search` | Search matters by query or client id |
| `clio.conflict.checklist` | Generate conflict screening checklist |
| `clio.intake.tasks` | Generate intake task assignment template |

## Workflow parameters

Execute the intake workflow with:

| Parameter | Example |
|-----------|---------|
| `prospect_name` | `Acme Holdings LLC` |
| `matter_type` | `Corporate intake` |
| `matter_name` | `Acme Holdings — intake` |
| `client_id` | Clio contact id (after search) |

## Related

- STA-113 Healthcare vertical pack
- STA-115 Real estate vertical pack (next)
