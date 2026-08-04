# Extension v3 enhance — additional overlay workflows + named steps

Date: 2026-08-03

## Baseline (already proven)

- MSP NVD CVE Lookup — run [`139fd6cc-…`](https://gravitre.app/outcomes/139fd6cc-7d53-4dfd-ac1b-c59e902109ea)

## Additional live proof — PASS

Artifact: `docs/delivery/browser-extension-v3-extra-workflows-live.json`  
Smoke: `scripts/live-extension-v3-extra-workflows-smoke.py`

| Workflow | Named steps | Run | Outcomes |
|----------|-------------|-----|----------|
| Ext v3 HS Pipelines Deals Proof | List HubSpot Pipelines · List HubSpot Deals | [`54914197-…`](https://gravitre.app/outcomes/54914197-9516-48c3-90be-703980deb6ec) | `source=browser_extension` completed |
| Ext v3 Apollo Orgs HS Pipelines Proof | Search Apollo Organizations · List HubSpot Pipelines | [`6d314587-…`](https://gravitre.app/outcomes/6d314587-bafb-4b11-a78b-da6c4d5245d6) | `source=browser_extension` completed |

Tip workflows seeded with `required_approvals=0` (read-only invoke_tool). Write-heavy packs (Lead Scout / Clay→HubSpot) still hit policy `pending_approval` before steps — not used for this gate.

## UX

Overlay plan-bar keeps **real step names** through propose → running → completed (`label`/`name` + status classes). No regression to generic status-only text after Approve.
