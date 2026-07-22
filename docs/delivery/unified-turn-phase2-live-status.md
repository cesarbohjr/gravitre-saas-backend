# Unified turn Phase 2 — live verification status

Updated: 2026-07-22

## Verdict

**PASS** — classical batteries + shadow audits on prod tip `acb44e3b…`

| Step | Status | Evidence |
|------|--------|----------|
| Prod tip | **PASS** | `GET https://api.gravitre.app/health` @ `2026-07-22T09:46:09Z` → `git_sha=acb44e3b0fef44845897f96808ff562fcc5a032c` |
| Shadow enabled | **PASS** | `unified_turn.shadow.completed` rows written during battery |
| Pending-reply battery | **PASS** | 24/24 — [pending-reply-classifier-battery-live.json](pending-reply-classifier-battery-live.json) |
| Conversational-path battery | **PASS** | 20/20 — [conversational-path-battery-live.json](conversational-path-battery-live.json) |
| Unified-turn shadow battery | **PASS** | 4/4 — [unified-turn-phase2-battery-live.json](unified-turn-phase2-battery-live.json) |
| Workflow | **PASS** | [Actions run 29909107895](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29909107895) (9m42s) |

## Shadow audit pointers (examples)

| Case | Action | Timestamp (UTC) | `outcome_kind` | `latency_ms` |
|------|--------|-----------------|----------------|--------------|
| greeting_no_catalog_leak | `unified_turn.shadow.completed` | `2026-07-22T09:46:16.287442Z` | conversational_reply | 1572 |
| thanks_plain | `unified_turn.shadow.completed` | `2026-07-22T09:46:30.250849Z` | conversational_reply | 952 |
| email_intent_no_catalog_dump | `unified_turn.shadow.completed` | `2026-07-22T09:46:46.523885Z` | clarifying_question | 3705 |
| status_check_pending | `unified_turn.shadow.completed` | `2026-07-22T09:47:08.962893Z` | confirmation_request | 1991 |

## Notes

- Tip advanced after deleting pinned Railway `GIT_SHA`; health prefers `RAILWAY_GIT_COMMIT_SHA` then `GIT_SHA`.
- Phase 2 completion latency above is **non-streaming** (`first_token_proxy_ms` == full completion). Phase 3 upgrades to true streamed TTFT.
- Write authority / approval paths unchanged (shadow does not execute tools).
