# GitHub v1 (STA-22)

## Connector setup

1. Create connector `type=github` with config `{ "owner": "org", "repo": "repo" }` (defaults for tool calls).
2. Store secret `token` — fine-grained or classic PAT with `repo` scope.

## Tool actions

| Action | Description |
|--------|-------------|
| `github.pulls.list` | List open PRs |
| `github.issues.create` | Create issue |
| `github.issues.comment` | Comment on issue/PR |
| `github.pulls.request_reviewer` | Request PR reviewers |

Scopes: `github:pulls:read`, `github:issues:write`, `github:pulls:write`, or `github:*`.
