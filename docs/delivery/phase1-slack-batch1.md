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

## Live tip status: BLOCKED (external reconnect)

| Check | Result |
|-------|--------|
| Unit / executor wiring | Pass |
| Smoke org Slack connector | `fe7433c3-…` status=`error` |
| `auth.test` | Slack API **`token_expired`** (token prefix `xoxe.`) |
| Live invoke of new actions | **Blocked** — cannot tip green until Cesar reconnects Slack on smoke org |

This is the same class of external dependency as HubSpot Batch 1b app republish / Apollo plan-tier / FRED_API_KEY — **not an engineering defect in Batch 1 code**.

Re-run after reconnect: `python scripts/smoke-phase1-slack-batch1-live.py`

## HubSpot Batch 1b (cross-reference)

**Still PENDING** — repo hsmeta updated; last HubSpot deployed build **#5 (2026-06-23)**; no `hs project upload` after scope change. Do not schedule companies/owners/tickets tips until portal republish + smoke HubSpot re-auth.

## Governance

- Finance/HR live-activation **HOLD** — unchanged
- Chat access deferred until tip PASS after Slack reconnect
