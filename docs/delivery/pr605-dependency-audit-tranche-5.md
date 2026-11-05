# PR #605 — Audit tranche 5: production routing, database, event and infrastructure topology
Date: 2026-11-05 UTC. Production baseline source SHA `557be844f191767ea51c9f1d1d4958e5b046ca53`. Read-only hosting/DB metadata and source review. No customer data queried.

## Verified production topology
- Vercel project `gravitre-saas-backend` is a **Next.js** application; configured project domains include `gravitre.app`, `gravitre-saas-backend-gravitre-ai.vercel.app` and a main-branch alias. Latest READY production deployment inspected previously was `dpl_4E97DHDQJSRFPuRmARbSpHZoVVwC`, commit `557be844...`. Project's `latestDeployment` may point to a newer CANCELED preview; do not confuse that field with latest READY production. DNS reachability and alias-to-deployment verification still outstanding.
- Railway production `spirited-communication` has live backend `gravitre-saas-backend` on main, one replica, `us-east4-eqdc4a`, latest SUCCESS deployment `78fb8af7-2c90-4a4f-9a34-180398ad20fb`, same commit. Backend custom domain `api.gravitre.app` targets port 8080; Railway-generated domain also exists.
- Railway Redis is a separate one-replica `redis:8.2.9` service in same region with persistent 5000 MB `/data` volume. **Volume capacity is not usage**.
- Separate Railway `Gravitre front-end` project contains `gravitre-saas-interface` from repo `cesarbohjr/gravitre-saas-interface`, one replica, latest FAILED deployment dated 2026-04-27, and no configured service/custom domains. **RETIRE CANDIDATE only**, pending external references, jobs, cost and rollback verification.
- Railway backend project has no staged changes. Shared variable names include provider, Supabase, Stripe and VOICE_* flags; values and service-level overrides were **not** inspected. Presence of a variable name does not prove valid credentials or enabled behavior.
- Connected Supabase lists `supabase-green-flower` project `smyeexlrqdpymwjmgzqu` ACTIVE_HEALTHY (249 public tables), `gravitre-acceptance` `aadnwmjzrmbvadszroqt` ACTIVE_HEALTHY, and `supabase-violet-dog` `uxpqrtpgxmahzfuofnco` INACTIVE. **Production database binding is not yet proven**; never infer from names alone.

## Verified route and event code
- Source tree contains 122 `backend/app/routers/*.py` files and 283 `apps/web/app/api/**/route.ts` files. These are static file counts, **not** verified active mounted routes.
- Backend `backend/app/routers/assistant.py` defines `/api/assistant/chat`, stop/replay, conversation state and execute, preferences and feedback endpoints.
- `backend/app/routers/pipecat_voice.py` defines authenticated WebSocket `/api/voice/pipecat/ws`; `voice_gateway.py` separately exposes `/api/voice-gateway/sessions` and PSTN WebSocket media.
- `apps/web/app/api/voice/session/turn/route.ts` forwards voice session turns to FastAPI through `apps/web/lib/voice-api-proxy.ts`.
- `voice-api-proxy.ts` checks `FASTAPI_BASE_URL` but, when set, returns `backendBaseUrl()` rather than the value itself; when unset, falls back to localhost:8000. This may be intentional central URL resolution but is a **configuration divergence risk**, not a proven production defect. Verify Vercel env name and resolved backend URL without exposing values.
- `backend/app/services/outcome_event_bus.py` explicitly implements org-scoped **in-process** asyncio.Queue subscriber registry, with drop-oldest on queue overflow. It is not a cross-process durable event bus. Do not treat it as a guaranteed delivery mechanism.
- `backend/app/temporal/worker.py` only starts a Temporal worker when `TEMPORAL_HOST` is configured, using task queue `gravitre-main`; no standalone Temporal service was present in the inspected Railway production project. This does not prove Temporal is absent elsewhere. Verify startup wiring, external service and deployment before declaring dormant.

## Findings and proposed fixes
| ID | Severity | Finding | Engineering plan |
|---|---|---|---|
| ECO-029 | P0 | Browser↔backend topology and deployed SHA confirmed through host metadata; DNS/live route and auth remain untested. | Build canonical route map including Next.js proxies, FastAPI mounts, WS, headers, identity, tenant context, timeouts and tracing. Probe deployed health/read-only routes under approved credentials. |
| ECO-030 | P1 | Static route surface is broad (122 backend router files, 283 frontend API route files); no caller-level ownership inventory. | Generate route-to-handler-to-service graph, compare registered routes to source and observed production traffic; classify active/shadow/dead only after evidence. |
| ECO-031 | P0 | In-process outcome event bus has bounded, drop-oldest queues and no inter-instance durability. | Specify best-effort UI notifications versus durable business events. For critical outcomes use persisted outbox/idempotent consumer, replay cursor, delivery metrics and multi-instance tests. Do not force Redis for every event. |
| ECO-032 | P0 | Temporal worker is env-gated; actual production worker/service not yet established. | Verify deployed worker process, host/config, schedules, queue consumers and fallback semantics. Reconcile Temporal/asyncio ownership; prohibit orphaned durable jobs. |
| ECO-033 | P0 | Three Supabase projects visible, only two active; production DB binding and schema migration alignment unverified. | Match deployed Supabase URL to project by **non-secret project ref**; audit 249-table schema, RLS, FK, triggers, functions, outbox, state projections and acceptance isolation. Never expose keys or tenant rows. |
| ECO-034 | P1 | Separate Railway frontend project has failed latest deployment and no domains. | Investigate spend, DNS, external consumers, logs and recovery requirements; mark RETIRE only after owner signoff and safe rollback. |
| ECO-035 | P1 | Redis live with persistent volume; purpose, memory usage and recovery behavior unverified. | Inventory key namespaces, cache/session/lock/rate-limit consumers, eviction/persistence and failure fallback. Benchmark and retain only needed uses. |
| ECO-036 | P1 | Voice API proxy resolves base through env presence and separate URL helper; localhost fallback exists. | Test production and preview resolution, avoid silent localhost or wrong-target behavior, centralize typed backend origin selection and log sanitized route choice. |

## Next deep tracing tasks (not yet completed)
1. Read FastAPI application router mounting, Next.js rewrite/proxy config, backendBaseUrl and voice status/WS routing; produce exact inbound route graph.
2. Verify domain aliases, health/read-only production requests, Vercel project environment *names* and Railway service-level config *names* without reading secrets.
3. Establish actual Supabase project binding, schema relationships, RLS policies, triggers and durable outbox/approval/run table dependencies using metadata-only queries.
4. Inspect event publishers/subscribers, Redis clients, Temporal startup/schedulers and background job topology; verify no duplicate delivery or missing workers.
5. Correlate production trace IDs with actual customer journeys and deploy SHA. Static source review alone is not full primary-secondary-tertiary certification.

## Safety and status
No deployment, schema mutation, config change, secret disclosure, paid provider invocation or deletion performed. The 36-item register contains confirmed architecture facts **and** explicitly labeled risks; not 36 proven defects. PR #605 remains draft.
