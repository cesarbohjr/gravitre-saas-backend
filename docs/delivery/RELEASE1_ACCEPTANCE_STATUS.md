# Release 1 authenticated acceptance — status

| Gate | Status | Blocker / notes |
|------|--------|-----------------|
| Anonymous `/api/sessions` controlled response | **NOT RUN** | Route implementation not located in this worktree; prod returns 500 on random org probe (fail-closed, wrong status). |
| Member/admin matrix | **NOT RUN** | Requires dedicated test orgs + protected workflow credentials (not in agent env). |
| MCP / watcher / retrieval +6m | **NOT RUN** | Same |

**Next:** Implement or locate `/api/sessions` route to return **401/403** without DB errors for anonymous probes; run `docs/delivery/release1-production-acceptance.md` matrix via GitHub production workflow when secrets available.
