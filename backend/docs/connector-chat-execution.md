# Connector chat execution

Gravitre separates **cataloged actions** from **executable chat tools**.

## Layers

| Layer | Role |
|-------|------|
| `vendor_definitions.py` | Declares connector actions, scopes, read/write/destructive flags |
| `invoke_tool` (`tool_service.py`) | Executes vendor APIs with audit, credentials, and permissions |
| `connector_execution_matrix.py` | Maps catalog actions → registry keys → chat exposure |
| `chat_tool_bridge.py` | Builds dynamic `ToolRegistry` specs for all implemented actions |
| `chat_action_mapper.py` | Maps natural language → matrix action + params |
| `ChatConnectorExecutionService` | Governed single-action chat execution |
| `ChatOrchestrationService` | Multi-step plan + step approvals |

## Adding a new executable action

1. Implement the handler in `invoke_tool` (dedicated client module or `catalog_http`).
2. Register the action key in the tool registry dict (or vendor tool module).
3. Add/verify the action in `vendor_definitions.py` with correct `kind`, scopes, and `requires_approval`.
4. The execution matrix auto-detects implemented actions via `list_registered_actions()`.
5. Dynamic chat tools are generated automatically — no manual `ToolRegistry` entry required unless you need a custom param mapper.
6. Extend `chat_action_mapper.py` phrase/arg extraction for common NL patterns.
7. Add tests in `tests/services/test_connector_execution_matrix.py` and `tests/services/test_chat_action_mapper.py`.

## Approval rules

- **Read** actions may auto-run after orchestration plan approval.
- **Write**, **destructive**, and **customer-facing** actions require step approval.
- High-risk actions must never bypass `RiskApprovalEvaluator`.

## Action key naming

Use `{vendor}.{resource}.{verb}` in catalog (e.g. `monday.items.create`). Registry aliases exist for Google vendors (`google_drive.*` → `drive.*`).

## Chat mapping examples

| User phrase | Action |
|-------------|--------|
| Search HubSpot for Acme | `hubspot.contacts.search` |
| Create a task in Monday | `monday.items.create` |
| Notify Slack #sales | `slack.post_message` |
| List files in Drive | `drive.files.list` |
| Send Gmail follow-up | `gmail.messages.send` |
| Create Jira ticket | `jira.issues.create` |

## Unsupported actions

When an action is cataloged but not implemented, chat returns an honest skip reason (`not_implemented`). When a connector is not connected, chat returns `missing_credentials` guidance pointing to `/connectors`.

## Testing

```bash
cd backend
python -m pytest tests/services/test_connector_execution_matrix.py tests/services/test_chat_action_mapper.py tests/services/test_chat_connector_execution.py tests/services/test_chat_orchestration.py -q
```

Inspect coverage at `GET /api/connectors/catalog/execution-matrix`.
