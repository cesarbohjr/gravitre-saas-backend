# Knowledge Fabric closeout — Part A + Part B (2026-08-11)

## Part A.1 — Honest prior status

The isolation block in `knowledge-fabric-verify-live.json` was **schema/service-role only**:
it checked `namespace=platform_shared`, table presence, and that `rag_chunks` have `org_id`.
It was **not** a disposable-org JWT attempting read/write through exposed APIs.

A later standing-isolated-org probe (`knowledge-fabric-isolation-live.json`, org
`f07e57c0-…`) was live JWT/PostgREST, but was **not** create+cleanup disposable.

## Part A.2 — Disposable org live proof

**PASS** @ `2026-08-11T10:09:15Z` on tip `054d50e1`  
Script: `scripts/verify-knowledge-fabric-isolation-disposable-live.py`  
Artifact: `docs/delivery/knowledge-fabric-isolation-disposable-live.json`

| Probe | Result | Evidence |
| -- | -- | -- |
| Disposable org created | `e82b214f-8c04-41bc-9603-42b93f8d81fd` | user `6187a061-…` / `kf-isolation+1786442955@gravitre.app` |
| PostgREST INSERT `knowledge_*` | **403** RLS | `"new row violates row-level security policy"` |
| PostgREST DELETE `knowledge_*` | no rows deleted | http 200, `row_count: 0` |
| PostgREST SELECT shared | **200** read-only | 2 rows each table |
| Foreign `rag_sources` seed | **blocked** | `row_count: 0` for foreign org title |
| `GET /packs` | 200 | registry returned |
| `POST /retrieve` | 200 | NIST Govern; `customer_rag_tables_touched: false` |
| `POST /admin/ingest` | **403** | `"Platform admin required"` |
| `POST /admin/register-sources` | **403** | `"Platform admin required"` |
| Internal refresh no secret | **401** | `"Invalid internal secret"` |
| Cleanup | **cleaned** | org deleted, auth user deleted, foreign seed deleted |

**Fix shipped:** admin ingest/register now `require_platform_admin` (org admins can no longer mutate shared corpus).

## Part B — Tokens / spot-checks / refresh

| Source | Status |
| -- | -- |
| CourtListener | **WAITING_ON_CESAR** — no `COURTLISTENER_API_TOKEN` |
| OpenLaws | **WAITING_ON_CESAR** — no `OPENLAWS_API_KEY` |
| O*NET | **WAITING_ON_CESAR** — no `ONET_*` credentials |
| Sales / Marketing | **UNTOUCHED** |

Chunk counts (active packs): cyber 4 / finance 2 / legal 3 / hr 2 — all with authority scores.  
Spot-checks: 3 queries × 4 packs — all PASS (`knowledge-fabric-closeout-live.json`).

Refresh:
- Direct service force refresh: finance `last_refreshed` **09:30:35Z → 10:06:07Z** (`timestamps_advanced: true`)
- Live API cron: `POST /api/internal/knowledge-fabric/refresh-due` **http 200** @ tip `054d50e1`; finance **10:06:07Z → 10:09:50Z** (`knowledge-fabric-refresh-api-live.json`)

Deploy health: `git_sha=054d50e1002d35c14500b7113f72523b5264e0aa`