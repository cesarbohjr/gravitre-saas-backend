# STA-303 — Distinct connector error codes (Option A)

**Decision (2026-07-16):** Split inactive/disconnected and related connector failures out of `validation_error`. Keep `validation_error` for true argument/schema mistakes only.

## Codes

| Code | When | User copy intent |
|------|------|------------------|
| `connector_not_connected` | No active connector row / not connected | Connect at `/connectors` |
| `channel_not_found` | Slack channel missing / bot not in channel | Fix channel or invite bot |
| `missing_scope` | Connected but OAuth scopes insufficient | Reconnect + approve scopes |
| `validation_error` | Bad/missing params for an otherwise available tool | Check required fields |
| `tool_not_available` | Agent/permission/availability short-circuit (legacy chip path) | Connect or switch mode |
| `auth_expired` | Token expired | Reconnect |

## Insert points (implemented)

- `tool_types.py` — `ToolConnectorNotConnectedError`, `ToolChannelNotFoundError`, `ToolMissingScopeError`
- `tool_error_messages.py` — short-circuit set + user templates
- `tool_service._classify_error` — message heuristics for vendor/API exceptions
- `tool_service._connector_by_type` + vendor session helpers — raise `connector_not_connected` on “No active …”
- `priority_connector_tools._vendor_api_error` / `_connector_by_type`
- `catalog_http.executor` — same raise
- `connector_availability_service.error_code_for_unavailable_integration` — `missing_scope` / `connector_not_connected`

## Cross-connector audit (write/read bodies)

Same ambiguity class (inactive → `validation_error`) previously affected HubSpot, Salesforce, QuickBooks, Stripe, PagerDuty, Jira, NetSuite, M365, Segment, Workday, Marketo, catalog HTTP vendors. All “No active … connector” raises in the tool layer now use `connector_not_connected`. Vendor SDK modules that raise vendor-specific API errors still rely on `_classify_error` message matching when wrapped.

## Tests

`backend/tests/services/test_sta303_connector_error_codes.py`
`backend/tests/operators/test_wave67_connector_unavailable_chip.py` (availability mapping)

## Live evidence bar

After deploy: produce a chat invoke with disconnected Slack and confirm `audit_events` / ToolChip `errorCode=connector_not_connected` (not `validation_error`). Until then: unit coverage only — do not mark production-closed without a live trace.
