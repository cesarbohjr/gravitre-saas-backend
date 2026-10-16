# Release 1 — production acceptance contract

Applies after migrations `20261013005000` through `20261013030000` (and recommended follow-ups `20261013040000`–`20261013060000`) are applied and backend/web SHAs match `main`.

## Principles

- Use **dedicated test organizations** only; do not mutate real customer memberships.
- **NOT RUN** stays **NOT RUN** until a row-level or HTTP artifact exists.
- Keep `DOMAIN_EVENT_RELAY_ENABLED=false` through this acceptance pass.

## Deploy alignment (before acceptance)

```bash
python3 scripts/verify-production-deploy-alignment.py \
  --expect-sha "$(git rev-parse main)" \
  --note-web-sha "<Vercel production commit from dashboard>"
```

Writes `docs/delivery/production-deploy-alignment.json`. Exit code **1** = backend ≠ expected main; **2** = backend ≠ reported web SHA.

## Automated (unauthenticated) smoke

Run after backend SHA is intentional:

```bash
python3 scripts/verify-release1-production-smoke.py \
  --web-base https://gravitre.app \
  --api-health https://api.gravitre.app/health \
  --expect-sha "<backend git_sha from /health>"
```

Writes `docs/delivery/release1-production-smoke.json` (safe to commit as evidence snapshot).

## Authenticated matrix (required for gate)

Requires isolated smoke org credentials (`scripts/mint_smoke_org_session.py`: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`) or operator SSO. **NOT RUN** in CI until GitHub `production` secrets exist.

## Manual matrix (authenticated)

| Actor | Action | Expected |
|-------|--------|----------|
| Anonymous | `GET /api/sessions?org_id=<test org>` | No protected rows **or** auth rejection (403/401); must not return real runs/approvals |
| Anonymous | Direct Supabase insert into `organization_members` | Refused by RLS/grants |
| Member | Add self to foreign org / raise role | Refused |
| Member | Direct governance table writes | Refused |
| Member | `PATCH` team role via web API | Refused unless admin |
| Admin | Change member role via backend | Success + audit event |
| Admin | MCP stdio row | Cannot execute |
| Admin | Approved public HTTP MCP | Works; private IP SSRF refused |
| Relay | Historical `execution.outcome_finalized` pending rows | Unchanged attempts while relay off |
| Retrieval | Deleted source / disconnected connector content | Not returned in chat/voice/cache paths |
| Watcher | Caller-supplied approval on write | Ignored; no provider write without real approval |

## Release 1 gate

**PASS** only when: six fixes **deployed**, follow-up authorization PRs **deployed**, migrations **applied** with preflight records, and both automated smoke + authenticated matrix are **PASS** with cited artifacts.
