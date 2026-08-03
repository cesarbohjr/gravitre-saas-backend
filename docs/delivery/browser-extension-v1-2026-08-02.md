# Browser extension v1 — overlay-and-approve

Date: 2026-08-02  
Status: scaffolded on `main` (load unpacked for local QA; Railway + Vercel for API/connect)

## Model

Overlay-and-approve only. No agentic browser control. Extension is a **front door** onto:

- Supabase JWT + `x-org-id` (same user/org as web)
- Catalog reads/writes via `invoke_tool`
- `catalog_write_authority` for write classification
- Module A `finalize_execution_outcome` (Runs / Outcomes)

## Permissions (minimal)

| Permission | Why |
|------------|-----|
| `activeTab` | Company-site overlay only when user invokes |
| `storage` | Session token + org id |
| `sidePanel` | Optional side panel |
| `scripting` | Inject company-site overlay under activeTab |
| Host allowlist | LinkedIn, Gmail, Outlook web, Gravitree/API origins |

**Not requested:** `debugger`, `<all_urls>`, `webNavigation`, background crawl.

## Surfaces

1. LinkedIn profiles (auto overlay on `/in/`)
2. Gmail (toolbar → Enrich)
3. Outlook web (toolbar → Enrich)
4. Company website via activeTab inject

## API

| Method | Path | Role |
|--------|------|------|
| GET | `/api/extension/session` | Session + connected integrations |
| POST | `/api/extension/enrich` | Catalog reads from page context |
| POST | `/api/extension/actions/execute` | Propose write → durable `awaiting_confirm` + `confirmationToken`; confirm turn executes with token only |

Allowlist in `extension_bridge_service.py` — unknown actions rejected.

### Write gate (parity with chat)

- Writes always stage an `approvals` row (`type=extension_write`, `context.status=awaiting_confirm`).
- Server returns `confirmationToken` (secrets.token_urlsafe) — **never** trust client `confirmed: true`.
- Confirm turn loads staged args from the approval row; client params are ignored.
- Module A `source` is `browser_extension`. Finalize failures emit `MODULE_A_FINALIZE_FAILED_FALLBACK_STATUS_STAMP` (Sentry + audit), not a silent warning.

### Org boundary

`get_org_context` returns **403** for non-member `x-org-id` (shared path — all API callers).

## Auth

`apps/web/app/extension/connect` → `chrome.runtime.sendMessage(extId, { type: GRAVITREE_AUTH, ... })`.

## Non-duplication

DOM is for **page context only**. Creates/list membership use Apollo/HubSpot catalog actions. No InMail automation, no CRM UI clicking.

## Load unpacked (local)

1. Deploy/restart API with `extension` router.
2. Deploy web with `/extension/connect`.
3. Chrome → Extensions → Load unpacked → `apps/extension`.
4. Popup → Connect Gravitree → Authorize.
5. Open a LinkedIn profile → overlay enrich → approve a write → check `/runs` / Outcomes.

## Live smoke (2026-08-03)

Script: `scripts/live-extension-v1-smoke.py` → `docs/delivery/browser-extension-v1-live.json`

### Close-out (UUID notify fix) — v1 CLOSED

**PASS** — HubSpot `list_id` no longer written to `notifications.entity_id` (uuid column).

Local pre-deploy: run `f693a774-2ec6-4b16-9c55-31ed4b40609a`, notification `1ff58694-…`

**Deployed tip** `git_sha=92fe0dde466344dcbc8529fad609126a0b0e8d01`:

- run_id `043a751c-c780-49e9-b39c-a5c66c98009e`
- notification `0d937d21-4a7b-46af-94b4-832d8256a878` `entity_id` = run UUID
- Outcomes: https://gravitre.app/outcomes/043a751c-c780-49e9-b39c-a5c66c98009e
- Evidence: `docs/delivery/browser-extension-v1-tip-verify.json`

### Prior smoke (durable confirm gate)

- run_id `fca91124-2ba5-4c9f-9897-2166b8d73aee` (had notify UUID warning — fixed above)

## v2+

Evidence-gated per roadmap. Do not expand hosts or agentic scope without usage data + (for v6) security review.
