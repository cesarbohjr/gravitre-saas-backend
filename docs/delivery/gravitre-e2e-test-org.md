# Gravitre internal E2E test organization (2.0)

**Purpose:** non-customer, tenant-isolated acceptance tenant for Platform Execution 2.0.

| Field | Value |
|-------|--------|
| Organization ID | `f07e57c0-1501-4000-8000-c04e57a00001` |
| Slug | `gravitre-isolated-conversation-smoke` |
| Name | Gravitre Isolated Conversation Smoke |
| Test identity | `a9f1240f-910a-42ca-aebf-38caeac288c3` / `conversation-smoke-sa@gravitre.app` |
| Forbidden | operator org `cbbf993b-b22f-41ce-964b-1fc25e0dd9ea` |
| Test company fixture | Gravitre Test Customer Alpha (`alpha.test.gravitre.app`) |

**Providers attached today:** HubSpot (healthy). GA4 (`pending_auth`, no refresh token). GSC (row healthy, refresh token present, Google refresh returns reconnect-required / expired grant). No Gmail connector. Alpha entity persisted to `org_business_entities` as `a1fa0000-1501-4000-8000-c04e57a00001` (synthetic HubSpot/QBO/Zendesk bindings; QBO/Zendesk OAuth not connected).

**Test-data policy:** synthetic Alpha records and smoke conversations only. No customer PII. No operator-org kernel writes.

**Cleanup policy:** conversations created by the smoke SA; no production customer assets.

**OAuth:** interactive Google consent on this org only. Isolated reconnect uses `prompt=consent` so Google can reissue a refresh token. Default (non-isolated) Google connector OAuth stays `select_account` so login sessions are not rotated.

**Browser automation:** one legitimate login via `pnpm e2e:save-storage` (writes `e2e/.fixtures/gravitre-e2e-storage.json`, gitignored). Then `pnpm test:e2e:authenticated-2.0` or set `GRAVITRE_E2E_STORAGE_STATE`. Never commit the file. Spec: `e2e/gravitre-2.0-authenticated-ai.spec.ts`.
