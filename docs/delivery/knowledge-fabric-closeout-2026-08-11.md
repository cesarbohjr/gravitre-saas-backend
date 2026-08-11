# Knowledge Fabric closeout — Part A + Part B (2026-08-11)

## Part A.1 — Honest prior status

The isolation block in `knowledge-fabric-verify-live.json` was **schema/service-role only**:
it checked `namespace=platform_shared`, table presence, and that `rag_chunks` have `org_id`.
It was **not** a disposable-org JWT attempting read/write through exposed APIs.

A later standing-isolated-org probe (`knowledge-fabric-isolation-live.json`, org
`f07e57c0-…`) was live JWT/PostgREST, but was **not** create+cleanup disposable.

## Part A.2 — Disposable org live proof

Script: `scripts/verify-knowledge-fabric-isolation-disposable-live.py`  
Artifact: `docs/delivery/knowledge-fabric-isolation-disposable-live.json`

Probes:
- PostgREST INSERT/DELETE on `knowledge_*` with disposable JWT (must RLS-block)
- PostgREST SELECT shared packs (read-only allowed by design)
- Foreign-org `rag_sources` seed not readable
- API: `/packs`, `/classify`, `/retrieve`
- API: `/admin/register-sources`, `/admin/ingest` must **403** (platform-admin only)
- Internal `/refresh-due` without secret must **401**
- Disposable org+user deleted afterward

**Fix shipped with this closeout:** admin ingest/register now use `require_platform_admin`
(previously any org admin could mutate the shared corpus).

## Part B — Tokens / spot-checks / refresh

- CourtListener / OpenLaws / O*NET: see closeout JSON `pending_sources_tokens`
- Sales/Marketing: **untouched**
- Spot-checks + forced refresh cycle: `knowledge-fabric-closeout-live.json`
- Refresh cron path: `POST /api/internal/knowledge-fabric/refresh-due` (`X-Internal-Secret`)
