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

**PASS** — LinkedIn-shaped enrich → staged `confirmationToken` → `hubspot.lists.create` → Outcomes DTO:

- run_id `fca91124-2ba5-4c9f-9897-2166b8d73aee`
- `execution_outcome_finalized` … `source=browser_extension` … `audit_written=True` @ ~2026-08-03T02:52:35Z
- BusinessOutcome DTO `source=browser_extension`, `lifecycleState=presented`
- Open: https://gravitre.app/outcomes/fca91124-2ba5-4c9f-9897-2166b8d73aee
- Org boundary: shared `get_org_context` returns 403 for non-member `x-org-id` (non-admin branch)

## v2+

Evidence-gated per roadmap. Do not expand hosts or agentic scope without usage data + (for v6) security review.
