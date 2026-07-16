# Phase 1 Batch 1 — Slack (2026-07-16)

## Scope

Third connector in approved Batch 1 order (after Apollo, HubSpot).

| Item | Detail |
|------|--------|
| API version | Slack Web API methods — **no bump** |
| New actions | `slack.conversations.join`, `slack.users.info` |
| Enriched | `conversations.list` / `history` / `users.list` / `post_message` now return `result_url` + summary |
| Deferred | `workflows.trigger` (needs `workflows:write`), `files.upload` (deprecated API path) |
| Chat / ReAct / canvas | **Not granted** |

## Live tip: PASS (after reconnect)

| Check | Result |
|-------|--------|
| Smoke Slack connector | `fe7433c3-…` status=`healthy` |
| `auth.test` | ok (team Gravitre) |
| Tip artifact | [`phase1-slack-batch1-live.json`](./phase1-slack-batch1-live.json) — **pass: true** |

Earlier tip was BLOCKED solely on `token_expired`; reconnect cleared it. Not a code defect.

## HubSpot Batch 1b (cross-reference)

**Still PENDING** — repo hsmeta updated; last HubSpot deployed build **#5 (2026-06-23)**; no portal upload after scope change.

## Governance

- Finance/HR live-activation **HOLD** — unchanged
- Chat access deferred until tip review
