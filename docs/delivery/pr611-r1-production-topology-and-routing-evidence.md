# PR #611 R1 — observed production hosting and frontend/backend routing

**Observation date:** 2026-11-07 (Vancouver). **Nature:** read-only connected Vercel and Railway resource inventory, Railway DNS and proxy logs, public website retrieval, and source review. This is not a complete authenticated E2E probe or an approval to delete infrastructure.

## Verified resource identities

| Chain | Observed evidence | Decision |
| --- | --- | --- |
| Customer website | `gravitre.app` is attached and verified on Vercel project **`gravitre-saas-backend`**, ID `prj_ZKQZcnavQ8UnQTWH85125nBgTVfO`, configured as Next.js. A successful public homepage fetch was observed. | **KEEP**; despite its project name this Vercel project serves the website, not the Railway Python backend. |
| Alternate Vercel web | Vercel project `web`, ID `prj_mH4HpIevws2u8jVpL0gpGcOC9KoE`, has only `web-drab-five-19.vercel.app` attached (no `gravitre.app`). Production READY deployments exist, alongside BLOCKED attempts. | **INVESTIGATE**; no proof of active external consumers or safe deletion. |
| Railway API | Project `spirited-communication`, ID `6017a555-f639-4b28-b538-031b5119e1e3`; production backend `20c41db0-3e3d-400e-95d5-eef57ba2bc0c`, one running replica, healthy; active deployment `78fb8af7-2c90-4a4f-9a34-180398ad20fb` (previously attributed to main `557be844...`). | **KEEP**; single shared API, no uncontrolled restart for testing. |
| Railway Redis | Service `f59baa77-47e3-460f-8437-3b79273317ae`, one running replica with attached volume, healthy. | **KEEP**, preserve durable queue and claims. |
| Railway generated origin | `gravitre-saas-backend-production.up.railway.app` attached to backend. | Canonical existing backend server-side URL in `apps/web/lib/public-urls.ts`. |
| Railway API custom domain | `api.gravitre.app` verified and attached to backend port 8080; CNAME `jj8n1lk3.up.railway.app` is **propagated**, TLS cert **VALID**. Railway proxy HTTP logs contain requests to this hostname; observed requests include unsolicited invalid-path probes returning 404. | **DNS/TLS bound**; a legitimate authenticated workflow across the domain still needs testing. |
| Old Railway frontend | Separate project `Gravitre front-end`, service `gravitre-saas-interface` ID `920ab289-304a-4a4f-8697-565b5490f78d`, is OFFLINE, with no attached custom or service domains, and warning notifications. | **RETIRE CANDIDATE — NOT APPROVED**: verify dependencies, usage, volumes, billing impact and owner approval before deleting. |

## Production deployment alignment and hold

- Vercel project serving `gravitre.app` has a recent **READY production** deployment `dpl_9UPDqCidmuCKYjLjXSGVuYxmFz9S` for main SHA `2e78e03a58e29e03019687b03ad90fd6ad420e84`, plus multiple older READY versions. **READY does not prove the current custom-domain alias points at that exact deployment.** A selected-domain routing/deployment alias attestation is still needed.
- Railway backend's healthy deployment precedes PR #611 and its planned SQL recovery migration; backend code and website frontend are **not proven same-SHA**. Roll forward only after exact-head full CI and controlled deployment.
- Vercel environment variable listing returned key metadata but was truncated. Never infer absence, presence, or effective production value of `FASTAPI_BASE_URL` from an incomplete list; this must be checked by a permissioned focused configuration readback without printing secrets.
- Observed `gravitre.app` publicly serves a homepage; the API health URL could not be fetched by the public web reader, despite Railway DNS/TLS and service health. This is **NOT a verified end-user /health 200**, nor proof of an outage. Need browser/HTTP probe with response status and hosting logs.
- No active customer tenancy or connected provider action was exercised; tenant forwarding has now been added to an offline regression test.

## Confirmed source defect and repair

- `DEC-017`: `apps/web/lib/voice-api-proxy.ts` previously returned `http://localhost:8000` whenever `FASTAPI_BASE_URL` was absent, including a production function. In a deployed Vercel function, that points at the function's own container, not Railway. This is a **real source-level invalid fallback**, not proof that current production requests hit it.
- **PR #611 repair**: production uses `backendBaseUrl()` (canonical Railway backend) if the setting is absent, preserving a local-only localhost default in development. Existing explicit backend URL and the `api.gravitre.app` alias normalization are preserved.
- `apps/web/lib/voice-api-proxy.audit.test.ts`: six targeted tests cover absent production setting, alias routing, explicit configured origin, dev-only localhost, real caller auth/org/env/accept header forwarding, and missing-identity negative case. Tests require exact-head CI; file committed does not establish a pass.
- `DEC-016`: the proxy code carries `authorization`, `x-org-id`, `x-environment` and NDJSON contract; offline positive/negative assertions are added. Actual browser-to-backend and authenticated tenant handling remain **NOT RUN**.

## Downstream execution and next defect queue

1. **R1 residual:** Verify live alias→deployment SHA, specific production `FASTAPI_BASE_URL` target (without exposing a secret), real `/health` response, authenticated proxy dispatch and actual browser voice WS path. Validate unused-host consumer/charges before any deprovisioning.
2. **R2:** Trace `chat_tool_bridge.build_dynamic_chat_tool_specs` → `connector_execution_matrix` → `chat_connector_execution_service._verify_plan_executable` → `connector_availability_service.find_integration_availability` → `tool_service._hubspot_connector_and_token`. Source edges show action-scoped availability and org OAuth; prove every active ingress uses them, especially direct tool aliases and fail-closed paths. Do not infer a real HubSpot provider action from static wiring.
3. **R3:** Use existing disposable real PostgreSQL acceptance to verify persisted run/step, approved/denied action, outbox relay and consumer; connect independently observed HubSpot provider receipts only after the restricted test workflow is manually approved. Keep tenant and lifecycle IDs consistent across hops.
4. **R4:** Opt-in child worker recovery in existing Railway after merge/release gate; no extra paid Railway staging. Isolated OS CI tests do not authorize a live PID kill.
5. **R5/R6:** PR #610 V0–V7 owns voice implementations, #611 ingests its exact-head QA30 results. Finish all audit findings, QA00–90 and full CI, no skipped-as-pass.
