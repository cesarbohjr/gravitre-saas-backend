# Jira agent tools (STA-36)

DevOps / Engineering agent tools for Jira Cloud (OAuth connector).

## v1 actions

| Action | Params |
|--------|--------|
| `jira.issues.create` | `project_key`, `summary`, optional `issue_type` (default `Task`), `description`, `fields` |
| `jira.issues.assign` | `issue_id` or `issue_key`, `account_id` (Atlassian accountId) |
| `jira.issues.transition` | `issue_id` or `issue_key`, `transition_id` |
| `jira.issues.comment` | `issue_id` or `issue_key`, `body` |

### Example

```json
{
  "action": "jira.issues.create",
  "params": {
    "project_key": "ENG",
    "summary": "Investigate PagerDuty incident",
    "issue_type": "Bug",
    "description": "Auto-created from Gravitre workflow"
  }
}
```

### Agent scopes

| Scope | Actions |
|-------|---------|
| `jira:issues:write` | All v1 issue actions |
| `jira:*` | All of the above |

## Code

- `backend/app/connectors/jira.py`
- `backend/app/services/tool_service.py`
