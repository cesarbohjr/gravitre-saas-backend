# Jira agent tools (STA-36)

DevOps / Engineering agent tools for Jira Cloud (OAuth connector).

## v1 actions (write)

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

### Agent scopes (v1)

| Scope | Actions |
|-------|---------|
| `jira:issues:write` | create, assign, transition, comment, update |
| `jira:*` | All actions below |

## v2 actions (read + workflow helpers)

| Action | Params |
|--------|--------|
| `jira.issues.get` | `issue_id` or `issue_key`, optional `fields[]` |
| `jira.issues.search` | `jql` **or** `project_key` / `status` / `assignee`, optional `limit`, `fields[]` |
| `jira.issues.update` | `issue_id` or `issue_key`, `fields{}` or `summary` / `description` |
| `jira.issues.transitions.list` | `issue_id` or `issue_key` — use before `jira.issues.transition` |
| `jira.projects.list` | optional `query`, `limit` |
| `jira.users.search` | `query`, `email`, or `display_name`; optional `limit` (for assignee `account_id`) |

### Example: incident triage

```json
[
  {
    "action": "jira.issues.search",
    "params": { "project_key": "ENG", "status": "Open", "limit": 10 }
  },
  {
    "action": "jira.issues.transitions.list",
    "params": { "issue_key": "ENG-42" }
  },
  {
    "action": "jira.issues.transition",
    "params": { "issue_key": "ENG-42", "transition_id": "31" }
  }
]
```

### Agent scopes (v2)

| Scope | Actions |
|-------|---------|
| `jira:issues:read` | `jira.issues.get`, `.search`, `.transitions.list` |
| `jira:issues:write` | v1 + `jira.issues.update` |
| `jira:projects:read` | `jira.projects.list` |
| `jira:users:read` | `jira.users.search` |

## Code

- `backend/app/connectors/jira.py`
- `backend/app/services/tool_service.py`
