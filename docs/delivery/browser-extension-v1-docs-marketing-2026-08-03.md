# Extension v1 — docs & marketing (post live proof)

Date: 2026-08-03  
Build proof (already closed): tip verify `92fe0dde…`, run `043a751c-…`, notification `0d937d21-…`  
Outcomes: https://gravitre.app/outcomes/043a751c-c780-49e9-b39c-a5c66c98009e

## Shipped this update

| Deliverable | Location |
|-------------|----------|
| Setup guide | `/docs/guides/how-to/browser-extension` |
| FAQ | `/docs/faq` — Browser extension section |
| Product page (activation walk) | `/features/extension` |
| Homepage + nav | Extension card / nav link / features pill |
| Guides hub card | Install the Chrome browser extension |
| CWS package script | `scripts/package-extension-chrome-store.py` |
| CWS listing draft | `apps/extension/store/LISTING.md` |

## Claims discipline (v1 marketing only)

- Browser: **Chrome**
- Surfaces: LinkedIn, Gmail, Outlook, company site
- Capability: enrich + approve catalog write → Outcomes
- Explicitly not claimed here: Salesforce/Slack/careers, workflows, overlay chat, Edge/Brave (those land in v2–v5 marketing updates after their proofs)

## Chrome Web Store — BLOCKER for store CTA

No listing ID / published or unlisted beta URL exists yet.  
Install CTA falls back to the setup guide (load unpacked) until `NEXT_PUBLIC_CHROME_WEB_STORE_URL` is set to a real `chromewebstore.google.com` URL.

**Human action required:** create Developer Dashboard item, upload zip, publish or unlisted beta, paste URL into web env, redeploy web.
